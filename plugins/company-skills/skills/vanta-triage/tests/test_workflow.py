"""End-to-end tests of SKILL.md's triage loop against a fake Linear store.

Each run follows the documented steps: list issues per state type into a scratch dir (step 2), plan (step 3),
get_issue every not-yet-fetched issue an action marks fetch_description or ambiguous and rerun the plan, until
none is left (step 4), then apply every write as step 5 describes, passing each action's `patch` to save_issue
verbatim, with patch semantics as the Linear connector defines them (each anchor matching exactly once).

The invariant: after one run, each group Vanta reports has an open issue whose description carries a row for
every current advisory (and, for containers, every affected image), and a second run makes no writes.
Run: python3 -m unittest discover -s tests (from the skill directory).
"""

import contextlib
import io
import json
import re
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import vanta  # noqa: E402

TODAY = "2026-10-13"
STATE_TYPES = {"Triage": "triage", "Backlog": "backlog", "Todo": "unstarted", "In Progress": "started",
               "In Review": "started", "Done": "completed", "Canceled": "canceled", "Duplicate": "canceled"}
WRITES = {"create", "retarget", "refresh", "resolve", "reopen", "realign"}
ASSETS = {
    "a-repo": {"id": "a-repo", "name": "stack", "assetType": "CODE_REPOSITORY"},
    "a-cts": {"id": "a-cts", "name": "cts", "assetType": "CONTAINER_REPOSITORY"},
    "a-zk": {"id": "a-zk", "name": "zerokms", "assetType": "CONTAINER_REPOSITORY"},
}
CONFIG = {"images": {"cts": {"repo": "acme/suite"}, "zerokms": {"repo": "acme/suite"}}}


def dep(id, advisory, ident, fixed):
    return vanta.normalise({
        "id": id, "name": advisory, "targetId": "a-repo", "severity": "HIGH", "cvssSeverityScore": 7.5,
        "fixedVersion": fixed, "remediateByDate": "2026-11-05T00:00:00Z", "firstDetectedDate": "2026-10-05T00:00:00Z",
        "packageIdentifier": ident, "externalURL": f"https://github.com/acme/stack/security/dependabot/{id}",
        "relatedUrls": [], "description": "Something is wrong with this package.", "deactivateMetadata": None,
    }, ASSETS, CONFIG)


def os_pkg(id, advisory, image="a-cts", pkg="openssl:3.0.15"):
    return vanta.normalise({
        "id": id, "name": advisory, "targetId": image, "severity": "MEDIUM", "cvssSeverityScore": 5.0,
        "fixedVersion": "NotAvailable", "remediateByDate": "2026-12-01T00:00:00Z", "firstDetectedDate": "2026-10-01T00:00:00Z",
        "packageIdentifier": pkg, "externalURL": f"https://console.aws.amazon.com/inspector/{id}",
        "relatedUrls": [], "description": "A flaw in an OS package.", "deactivateMetadata": None,
    }, ASSETS, CONFIG)


# An issue a test writes without priority or due date stands for one a human made stricter than Vanta's values.
STRICT = {"priority": {"value": 1, "name": "Urgent"}, "dueDate": "2026-01-01"}
PRIORITY_NAMES = {0: "No priority", 1: "Urgent", 2: "High", 3: "Medium", 4: "Low"}


class PatchError(Exception):
    pass


def apply_patch(text, ops):
    """save_issue patch: ops apply in order, atomically; an anchor must match exactly once."""
    for op in ops:
        if op["op"] == "replace":
            if text.count(op["old_string"]) != 1:
                raise PatchError(f"old_string matches {text.count(op['old_string'])} times")
            text = text.replace(op["old_string"], op["new_string"])
        elif op["op"] == "prepend":
            text = op["text"] + text
        else:
            raise PatchError(f"unexpected op {op['op']}")
    return text


class FakeLinear:
    def __init__(self, issues=()):
        self.issues = {i["id"]: dict(i) for i in issues}
        self.comments, self.failures = [], []

    def list_pages(self):
        """One list_issues response per state type, with step 2's fields (no description)."""
        pages = {}
        for issue in self.issues.values():
            stype = STATE_TYPES[issue["status"]]
            row = {"id": issue["id"], "title": issue["title"], "status": issue["status"], "statusType": stype,
                   "completedAt": issue.get("completedAt"), "canceledAt": issue.get("canceledAt"),
                   "priority": issue.get("priority", STRICT["priority"]), "dueDate": issue.get("dueDate", STRICT["dueDate"])}
            pages.setdefault(stype, []).append(row)
        return {f"{t}.json": {"issues": rows, "hasNextPage": False} for t, rows in pages.items()}

    def get_issue(self, ident):
        issue = self.issues[ident]
        return {"description": None, **issue, "statusType": STATE_TYPES[issue["status"]]}

    def create(self, title, description, priority, due, related_to=None):
        ident = f"CIP-{100 + len(self.issues)}"
        self.issues[ident] = {"id": ident, "title": title, "description": description, "status": "Todo",
                              "priority": {"value": priority, "name": PRIORITY_NAMES[priority]}, "dueDate": due}
        if related_to:
            self.issues[ident]["relatedTo"] = related_to
        return ident


def plan(findings, files):
    with tempfile.TemporaryDirectory() as d:
        Path(d, "findings.json").write_text(json.dumps(findings))
        Path(d, "config.json").write_text(json.dumps(CONFIG))
        Path(d, "issues").mkdir()
        for name, data in files.items():
            Path(d, "issues", name).write_text(json.dumps(data))
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = vanta.main(["plan", "--findings", str(Path(d, "findings.json")),
                               "--issues", *sorted(str(p) for p in Path(d, "issues").iterdir()),
                               "--config", str(Path(d, "config.json")), "--today", TODAY])
        assert code == 0, code
        return json.loads(out.getvalue())


def triage(store, findings):
    """One documented run; returns the applied plan's write actions."""
    files = store.list_pages()
    p = plan(findings, files)
    fetched = set()
    while True:  # step 4: fetch and rerun until no unfetched issue is asked for; each issue at most once
        fetch = {a["issue"] for a in p["actions"] if (a.get("fetch_description") or a.get("ambiguous"))} - fetched
        if not fetch:
            break
        for ident in fetch:
            files[f"{ident}.json"] = store.get_issue(ident)
        fetched |= fetch
        p = plan(findings, files)
    groups = {g["key"]: g for g in p["groups"]}
    assert not any(a.get("fetch_description") for a in p["actions"]), "step 4 left a description unfetched"
    writes = []
    for a in p["actions"]:
        try:
            if a["action"] == "create":
                g = groups[a["key"]]
                store.create(g["title"], g["description"], g["priority"], g["sla"], a.get("relatedTo"))
            elif a["action"] in ("retarget", "refresh"):
                if "patch" not in a:
                    raise PatchError(f"{a['action']} without a patch")
                desc = apply_patch(store.issues[a["issue"]]["description"], a["patch"])
                store.issues[a["issue"]]["description"] = desc
                if a["action"] == "retarget":
                    store.issues[a["issue"]]["title"] = a["title"]
                store.comments.append((a["issue"], a["reason"]))
            elif a["action"] == "reopen":  # step 5: Todo, the plan's title, its patch when it carries one, a comment
                issue = store.issues[a["issue"]]
                if "patch" in a:
                    issue["description"] = apply_patch(issue["description"], a["patch"])
                issue.update(status="Todo", title=a["title"], completedAt=None)
                store.comments.append((a["issue"], a["reason"]))
            elif a["action"] == "realign":  # step 5: reread, tighten each field independently, then comment
                current = store.get_issue(a["issue"])
                fields = {field for field in ("priority", "dueDate") if field in a}
                if not fields <= current.keys() or not current.get("statusType"):
                    raise PatchError("realign reread omitted a required field")
                if current["statusType"] in ("completed", "canceled"):
                    continue
                fresh = vanta.realign(groups[a["key"]], {
                    "id": a["issue"],
                    "urgency": {field: value for field, value in vanta.urgency(current).items() if field in fields},
                })
                if fresh is None:
                    continue
                a = fresh
                issue = store.issues[a["issue"]]
                if "priority" in a:
                    issue["priority"] = {"value": a["priority"], "name": PRIORITY_NAMES[a["priority"]]}
                if "dueDate" in a:
                    issue["dueDate"] = a["dueDate"]
                store.comments.append((a["issue"], a["reason"]))
            elif a["action"] == "resolve":
                store.issues[a["issue"]]["status"] = "Done"
                store.issues[a["issue"]]["completedAt"] = TODAY
        except PatchError as exc:
            store.failures.append((a["issue"], str(exc)))
        if a["action"] in WRITES:
            writes.append(a)
    for g in p["groups"]:
        for dup in g.get("duplicates", []):
            store.issues[dup]["status"] = "Duplicate"
            writes.append({"action": "duplicate", "issue": dup})
    return writes


class Workflow(unittest.TestCase):
    def assertCurrent(self, store, findings):
        """Every group has one open issue whose description lists each current advisory row and image."""
        self.assertEqual(store.failures, [])
        for g in vanta.group_findings(findings):
            owners = [i for i in store.issues.values() if STATE_TYPES[i["status"]] not in ("completed", "canceled")
                      and (m := vanta.KEY_LINE_RE.search(i.get("description") or "")) and vanta.same_key(m.group(1), g["key"])]
            self.assertEqual(len(owners), 1, f"{g['key']}: open issues carrying its key: {[i['id'] for i in owners]}")
            desc = owners[0]["description"]
            for a in g["advisories"]:
                affected = f"`{a['affected']}`" if a["affected"] else "n/a"
                rows = [line for line in desc.splitlines() if line.startswith("| ") and a["id"] in line
                        and f"| {affected} | {a['fixed_version'] or 'none'} |" in line]
                self.assertTrue(rows, f"{owners[0]['id']} has no row for {a['id']} {affected}")
            if g["images"]:
                images = re.search(r"^\*\*Images:\*\* (.*)$", desc, re.M)
                self.assertTrue(images, f"{owners[0]['id']} has no Images line")
                for image in g["images"]:
                    self.assertIn(f"`{image}`", images.group(1), f"{owners[0]['id']} does not list image {image}")

    def converge(self, store, findings):
        triage(store, findings)
        self.assertCurrent(store, findings)
        self.assertEqual(triage(store, findings), [], "second run still writes")

    def generated(self, findings, ident, **kw):
        [g] = vanta.group_findings(findings)
        return {"id": ident, "title": g["title"], "description": g["description"], "status": "Todo", **kw}

    # ---- remediate

    def test_remediate_new_unfixed_advisory_same_target(self):
        old = [dep("1", "CVE-1", "npm-left-pad < 1.2.2", "1.2.2")]
        new = old + [dep("2", "CVE-2", "npm-left-pad < 2.0.0", None)]
        issue = self.generated(old, "CIP-1")
        issue["description"] = "Owner: payments team.\n\n" + issue["description"] + "\n\nNotes: pinned by foo."
        store = FakeLinear([issue])
        self.converge(store, new)
        desc = store.issues["CIP-1"]["description"]
        self.assertTrue(desc.startswith("Owner: payments team."))
        self.assertTrue(desc.endswith("Notes: pinned by foo."))

    def test_remediate_retarget_from_list_only(self):
        old = [dep("1", "CVE-1", "npm-left-pad < 1.2.2", "1.2.2")]
        new = old + [dep("2", "CVE-2", "npm-left-pad < 1.2.5", "1.2.5")]
        store = FakeLinear([self.generated(old, "CIP-1")])
        self.converge(store, new)
        self.assertEqual(store.issues["CIP-1"]["title"], "[Vanta] Remediate left-pad to 1.2.5 (stack)")

    def test_legacy_issue_without_key_or_digest(self):
        findings = [dep("1", "CVE-1", "npm-left-pad < 1.2.2", "1.2.2"), dep("2", "CVE-2", "npm-left-pad < 2.0.0", None)]
        store = FakeLinear([{"id": "CIP-1", "title": "[Vanta] Remediate left-pad to 1.2.2 (stack)", "status": "Todo",
                             "description": "Dependabot says bump left-pad. CVE-1 only."}])
        self.converge(store, findings)
        self.assertTrue(store.issues["CIP-1"]["description"].endswith("Dependabot says bump left-pad. CVE-1 only."))

    def test_legacy_vulnerability_heading_survives_two_changes(self):
        """A legacy issue with a "## Vulnerability" heading but no key line is prepended, then refreshed later."""
        store = FakeLinear([{"id": "CIP-1", "title": "[Vanta] Remediate left-pad to 1.2.0 (stack)", "status": "Todo",
                             "description": "## Vulnerability\n\nleft-pad < 1.2.0 (CVE-0), filed by hand."}])
        first = [dep("1", "CVE-1", "npm-left-pad < 1.2.2", "1.2.2")]
        self.converge(store, first)  # retarget: prepends the generated section
        self.converge(store, first + [dep("2", "CVE-2", "npm-left-pad < 2.0.0", None)])  # refresh: replaces the prepended span

    # ---- track-upstream

    def test_track_upstream_new_advisory(self):
        old = [dep("1", "CVE-1", "npm-left-pad < 3.0.0", None)]
        new = old + [dep("2", "CVE-2", "npm-left-pad < 3.1.0", None)]
        store = FakeLinear([self.generated(old, "CIP-1")])
        self.converge(store, new)

    def test_track_upstream_gains_fix(self):
        old = [dep("1", "CVE-1", "npm-left-pad < 3.0.0", None)]
        new = [dep("1", "CVE-1", "npm-left-pad < 3.0.0", "3.0.0")]
        store = FakeLinear([self.generated(old, "CIP-1")])
        self.converge(store, new)

    def test_recently_done_issue_with_new_advisory(self):
        store = FakeLinear([{**self.generated([dep("1", "CVE-1", "npm-left-pad < 1.2.2", "1.2.2")], "CIP-1"),
                             "status": "Done", "completedAt": "2026-10-10T01:00:00Z"}])
        self.converge(store, [dep("2", "CVE-2", "npm-left-pad < 2.0.0", None)])
        self.assertEqual((store.issues["CIP-1"]["status"], len(store.issues)), ("Todo", 1), "CIP-1 was not reopened")

    def test_done_issue_whose_finding_returns_is_reopened(self):
        """#22: CIP-1 was resolved ten days ago while the repo was still vulnerable; Vanta reports it again."""
        findings = [dep("1", "CVE-1", "npm-left-pad < 1.2.2", "1.2.2")]
        store = FakeLinear([{**self.generated(findings, "CIP-1"), "status": "Done", "completedAt": "2026-10-03T01:00:00Z"}])
        self.converge(store, findings)
        self.assertEqual((store.issues["CIP-1"]["status"], len(store.issues)), ("Todo", 1))
        self.assertIn("2026-10-03", store.comments[-1][1])

    def test_canceled_npm_does_not_claim_open_cargo_issue_with_identical_title(self):
        npm = dep("1", "CVE-1", "npm-left-pad < 1.2.2", "1.2.2")
        cargo = dep("2", "CVE-2", "rust-left-pad < 1.2.2", "1.2.2")
        store = FakeLinear([self.generated([npm], "CIP-1", status="Canceled", canceledAt="2026-10-08"),
                            self.generated([cargo], "CIP-2")])
        self.assertEqual(store.issues["CIP-1"]["title"], store.issues["CIP-2"]["title"])
        writes = triage(store, [npm, cargo])
        self.assertEqual(set(store.issues), {"CIP-1", "CIP-2"}, "ambiguous open issue must be fetched before creating")
        self.assertEqual(writes, [])
        self.assertCurrent(store, [cargo])

    def test_canceled_group_fetches_every_ambiguous_open_candidate(self):
        npm = dep("1", "CVE-1", "npm-left-pad < 1.2.2", "1.2.2")
        cargo = dep("2", "CVE-2", "rust-left-pad < 1.2.2", "1.2.2")
        golang = dep("3", "CVE-3", "go-left-pad < 1.2.2", "1.2.2")
        store = FakeLinear([self.generated([npm], "CIP-1", status="Canceled", canceledAt="2026-10-08"),
                            self.generated([cargo], "CIP-2"), self.generated([golang], "CIP-3")])
        self.assertEqual(triage(store, [npm, cargo, golang]), [])
        self.assertEqual(set(store.issues), {"CIP-1", "CIP-2", "CIP-3"})
        self.assertCurrent(store, [cargo, golang])

    def test_damaged_issue_preserves_notes_while_unrelated_group_progresses(self):
        damaged = dep("1", "CVE-1", "npm-left-pad < 1.2.2", "1.2.2")
        unrelated = dep("2", "CVE-2", "npm-other < 2.0.0", "2.0.0")
        issue = self.generated([damaged], "CIP-1")
        issue["description"] = "Human notes before\n" + issue["description"].split("Vanta key:")[0] + "Human notes after"
        store = FakeLinear([issue])
        writes = triage(store, [damaged, unrelated])
        self.assertEqual(store.issues["CIP-1"], issue, "damaged issue text must stay intact")
        self.assertEqual([a["action"] for a in writes], ["create"])
        self.assertEqual(len(store.issues), 2)
        self.assertCurrent(store, [unrelated])

    def test_realign_skips_issue_closed_after_planning(self):
        for status in ("Done", "Canceled"):
            with self.subTest(status=status):
                findings = [dep("1", "CVE-1", "npm-left-pad < 1.2.2", "1.2.2")]
                store = FakeLinear([self.generated(findings, "CIP-1", priority={"value": 3}, dueDate="2026-12-20")])
                original_plan = plan

                def close_after_plan(*args):
                    result = original_plan(*args)
                    if any(a["action"] == "realign" for a in result["actions"]):
                        store.issues["CIP-1"]["status"] = status
                    return result

                with patch(__name__ + ".plan", side_effect=close_after_plan):
                    writes = triage(store, findings)
                self.assertEqual((writes, store.comments), ([], []), "closed issue must not be updated or commented on")
                self.assertEqual(store.issues["CIP-1"]["priority"], {"value": 3})
                self.assertEqual(store.issues["CIP-1"]["dueDate"], "2026-12-20")

    def test_new_risk_creates_linked_issue_and_preserves_cancellation(self):
        old = [dep("1", "CVE-1", "npm-left-pad < 1.2.2", "1.2.2")]
        current = old + [dep("2", "CVE-2", "npm-left-pad < 1.2.2", "1.2.2")]
        canceled = self.generated(old, "CIP-1", status="Canceled", canceledAt="2026-10-08")
        store = FakeLinear([canceled])
        self.assertEqual([a["action"] for a in triage(store, current)], ["create"])
        self.assertEqual(store.issues["CIP-1"], canceled)
        self.assertEqual(store.issues["CIP-101"]["relatedTo"], ["CIP-1"])
        self.assertCurrent(store, current)
        self.assertEqual(triage(store, current), [], "the linked replacement must prevent another create")
        self.assertEqual(store.comments, [])

    def test_canceled_issue_is_reported_not_refiled(self):
        """#23: a human cancelled CIP-1 to accept the risk; Vanta still reports the finding."""
        findings = [dep("1", "CVE-1", "npm-left-pad < 1.2.2", "1.2.2")]
        store = FakeLinear([{**self.generated(findings, "CIP-1"), "status": "Canceled", "canceledAt": "2026-10-08T01:00:00Z"}])
        for _ in range(2):
            self.assertEqual(triage(store, findings), [])
        self.assertEqual((store.issues["CIP-1"]["status"], len(store.issues), store.comments), ("Canceled", 1, []))

    def test_drifted_priority_and_due_date_are_realigned_once(self):
        """#25: Vanta raised the severity to HIGH and brought the SLA forward after CIP-1 was filed."""
        findings = [dep("1", "CVE-1", "npm-left-pad < 1.2.2", "1.2.2")]
        store = FakeLinear([{**self.generated(findings, "CIP-1"), "priority": {"value": 3, "name": "Medium"},
                             "dueDate": "2026-12-20"}])
        self.converge(store, findings)
        self.assertEqual((store.issues["CIP-1"]["priority"]["value"], store.issues["CIP-1"]["dueDate"]), (2, "2026-11-05"))

    def test_human_escalation_is_never_relaxed(self):
        findings = [dep("1", "CVE-1", "npm-left-pad < 1.2.2", "1.2.2")]
        store = FakeLinear([{**self.generated(findings, "CIP-1"), "priority": {"value": 1, "name": "Urgent"},
                             "dueDate": "2026-10-20"}])
        self.assertEqual(triage(store, findings), [])

    def test_human_escalation_after_planning_is_preserved(self):
        findings = [dep("1", "CVE-1", "npm-left-pad < 1.2.2", "1.2.2")]
        store = FakeLinear([{**self.generated(findings, "CIP-1"),
                             "priority": {"value": 3, "name": "Medium"}, "dueDate": "2026-12-20"}])
        original_plan = plan

        def escalate_after_plan(*args):
            result = original_plan(*args)
            if any(a["action"] == "realign" for a in result["actions"]):
                store.issues["CIP-1"].update(priority={"value": 1, "name": "Urgent"}, dueDate="2026-10-20")
            return result

        with patch(__name__ + ".plan", side_effect=escalate_after_plan):
            writes = triage(store, findings)
        self.assertEqual(store.issues["CIP-1"]["priority"]["value"], 1, "realign relaxed a human priority escalation")
        self.assertEqual(store.issues["CIP-1"]["dueDate"], "2026-10-20", "realign postponed a human deadline")
        self.assertEqual((writes, store.comments), ([], []), "skipped realign should not write or comment")

    def test_human_priority_escalation_still_allows_due_date_tightening(self):
        findings = [dep("1", "CVE-1", "npm-left-pad < 1.2.2", "1.2.2")]
        store = FakeLinear([{**self.generated(findings, "CIP-1"),
                             "priority": {"value": 3, "name": "Medium"}, "dueDate": "2026-12-20"}])
        original_plan = plan

        def escalate_after_plan(*args):
            result = original_plan(*args)
            if any(a["action"] == "realign" for a in result["actions"]):
                store.issues["CIP-1"]["priority"] = {"value": 1, "name": "Urgent"}
            return result

        with patch(__name__ + ".plan", side_effect=escalate_after_plan):
            triage(store, findings)
        self.assertEqual(store.issues["CIP-1"]["priority"]["value"], 1, "realign relaxed a human priority escalation")
        self.assertEqual(store.issues["CIP-1"]["dueDate"], "2026-11-05")
        self.assertNotIn("priority", store.comments[-1][1], "comment claimed a priority change that was skipped")

    def test_failed_reopen_does_not_realign_closed_issue(self):
        old = [dep("1", "CVE-1", "npm-left-pad < 1.2.2", "1.2.2")]
        findings = old + [dep("2", "CVE-2", "npm-left-pad < 1.2.2", "1.2.2")]
        store = FakeLinear([self.generated(old, "CIP-1", status="Done", completedAt="2026-10-08",
                                           priority={"value": 3}, dueDate="2026-12-20")])
        with patch(__name__ + ".apply_patch", side_effect=PatchError("reopen update failed")):
            writes = triage(store, findings)
        self.assertEqual(store.issues["CIP-1"]["status"], "Done")
        self.assertFalse(any(a["action"] == "realign" for a in writes))
        self.assertEqual(store.issues["CIP-1"]["priority"], {"value": 3})
        self.assertEqual(store.issues["CIP-1"]["dueDate"], "2026-12-20")
        self.assertEqual(store.comments, [])
        self.assertEqual(store.failures, [("CIP-1", "reopen update failed")])

    def test_realign_reread_failure_leaves_the_issue_unchanged(self):
        for failure in ("connector failure", "missing field", "missing statusType", "null statusType"):
            with self.subTest(failure=failure):
                findings = [dep("1", "CVE-1", "npm-left-pad < 1.2.2", "1.2.2")]
                store = FakeLinear([{**self.generated(findings, "CIP-1"),
                                     "priority": {"value": 3, "name": "Medium"}, "dueDate": "2026-12-20"}])
                original_get = store.get_issue
                calls = 0

                def fail_on_reread(ident):
                    nonlocal calls
                    calls += 1
                    result = original_get(ident)
                    if calls > 1:
                        if failure == "connector failure":
                            raise PatchError("get_issue failed")
                        if failure == "missing statusType":
                            result.pop("statusType")
                        elif failure == "null statusType":
                            result["statusType"] = None
                        else:
                            result.pop("dueDate")
                    return result

                with patch.object(store, "get_issue", side_effect=fail_on_reread):
                    triage(store, findings)
                self.assertEqual(store.issues["CIP-1"]["priority"]["value"], 3)
                self.assertEqual(store.issues["CIP-1"]["dueDate"], "2026-12-20")
                self.assertEqual(store.comments, [])
                self.assertEqual(len(store.failures), 1, "failed reread must be reported")

    def test_done_issue_outside_the_window_is_not_reopened(self):
        findings = [dep("1", "CVE-1", "npm-left-pad < 1.2.2", "1.2.2")]
        store = FakeLinear([{**self.generated(findings, "CIP-1"), "status": "Done", "completedAt": "2026-09-20T01:00:00Z"}])
        self.converge(store, findings)
        self.assertEqual((store.issues["CIP-1"]["status"], len(store.issues)), ("Done", 2))

    # ---- containers

    def test_container_new_advisory_keeps_verdict_title_and_notes(self):
        old = [os_pkg("1", "CVE-A")]
        issue = self.generated(old, "CIP-1")
        issue["title"] = "[Vanta] Assess openssl CVE-A — not affected (cts image)"
        issue["description"] += "\n\nAssessment: CVE-A needs a TLS 1.0 peer; not reachable."
        store = FakeLinear([issue])
        self.converge(store, old + [os_pkg("2", "CVE-B")])
        self.assertEqual(store.issues["CIP-1"]["title"], issue["title"])
        self.assertTrue(store.issues["CIP-1"]["description"].endswith("not reachable."))

    def test_container_spreads_to_another_image(self):
        old = [os_pkg("1", "CVE-A")]
        store = FakeLinear([self.generated(old, "CIP-1")])
        self.converge(store, old + [os_pkg("2", "CVE-A", image="a-zk")])

    def test_image_dropping_out_and_back_never_rewrites(self):
        """#24: Vanta alternates between reporting the cts and zerokms images; CIP-1 is written once at most."""
        both = [os_pkg("1", "CVE-A"), os_pkg("2", "CVE-A", image="a-zk")]
        store = FakeLinear([self.generated(both, "CIP-1")])
        for findings in (both[:1], both, both[1:], both):
            self.assertEqual(triage(store, findings), [], "a dropped or returning image rewrote the issue")

    def test_alternating_single_images_settle_after_one_refresh(self):
        cts, zk = [os_pkg("1", "CVE-A")], [os_pkg("2", "CVE-A", image="a-zk")]
        store = FakeLinear([self.generated(cts, "CIP-1")])
        self.assertEqual([a["action"] for a in triage(store, zk)], ["refresh"])
        for findings in (cts, zk, cts):
            self.assertEqual(triage(store, findings), [], "alternating images rewrote the issue again")

    def test_track_upstream_legacy_with_notes(self):
        findings = [dep("1", "CVE-1", "npm-left-pad < 3.0.0", None)]
        store = FakeLinear([{"id": "CIP-1", "title": "[Vanta] Track upstream fix for left-pad (stack)", "status": "Backlog",
                             "description": "Waiting on upstream; see their issue #12."}])
        self.converge(store, findings)
        self.assertEqual(store.issues["CIP-1"]["title"], "[Vanta] Track upstream fix for left-pad (stack)")
        self.assertTrue(store.issues["CIP-1"]["description"].endswith("see their issue #12."))

    def test_remediate_losing_every_fix_keeps_title(self):
        old = [dep("1", "CVE-1", "npm-left-pad < 1.2.2", "1.2.2"), dep("2", "CVE-2", "npm-left-pad < 2.0.0", None)]
        store = FakeLinear([self.generated(old, "CIP-1")])
        self.converge(store, old[1:])
        self.assertEqual(store.issues["CIP-1"]["title"], "[Vanta] Remediate left-pad to 1.2.2 (stack)")

    # ---- containers (legacy)

    def test_container_legacy_umbrella_text_and_verdict_title(self):
        findings = [os_pkg("1", "CVE-A"), os_pkg("2", "CVE-A", image="a-zk")]
        title = "[Vanta] Assess openssl CVE-A — not affected (cts image)"
        store = FakeLinear([{"id": "CIP-1", "title": title, "status": "In Progress",
                             "description": "Assessed by hand: needs a TLS 1.0 peer."}])
        self.converge(store, findings)
        self.assertEqual(store.issues["CIP-1"]["title"], title)
        self.assertTrue(store.issues["CIP-1"]["description"].endswith("needs a TLS 1.0 peer."))

    # ---- reruns

    def test_rerun_hands_group_an_unfetched_issue(self):
        """Fetching CIP-1 shows it belongs elsewhere; the rerun hands its group CIP-2, which was never fetched."""
        findings = [dep("1", "CVE-1", "npm-left-pad < 1.2.2", "1.2.2"), dep("2", "CVE-2", "npm-left-pad < 2.0.0", None)]
        store = FakeLinear([
            {"id": "CIP-1", "title": "[Vanta] Remediate left-pad to 1.2.2 (stack)", "status": "Todo",
             "description": "## Vulnerability\n\nAdvisory set: `000000000000`\nVanta key: `dependency:acme/old-stack:npm:left-pad`"},
            self.generated(findings[:1], "CIP-2")])
        self.converge(store, findings)


if __name__ == "__main__":
    unittest.main()
