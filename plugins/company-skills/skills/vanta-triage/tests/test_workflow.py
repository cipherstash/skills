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
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import vanta  # noqa: E402

TODAY = "2026-10-13"
STATE_TYPES = {"Triage": "triage", "Backlog": "backlog", "Todo": "unstarted", "In Progress": "started",
               "In Review": "started", "Done": "completed", "Duplicate": "canceled"}
WRITES = {"create", "retarget", "refresh", "resolve"}
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
            if stype == "canceled":
                continue
            row = {"id": issue["id"], "title": issue["title"], "status": issue["status"], "statusType": stype,
                   "completedAt": issue.get("completedAt")}
            pages.setdefault(stype, []).append(row)
        return {f"{t}.json": {"issues": rows, "hasNextPage": False} for t, rows in pages.items()}

    def get_issue(self, ident):
        issue = self.issues[ident]
        return {**issue, "statusType": STATE_TYPES[issue["status"]]}

    def create(self, title, description):
        ident = f"CIP-{100 + len(self.issues)}"
        self.issues[ident] = {"id": ident, "title": title, "description": description, "status": "Todo"}
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
                store.create(g["title"], g["description"])
            elif a["action"] in ("retarget", "refresh"):
                if "patch" not in a:
                    raise PatchError(f"{a['action']} without a patch")
                desc = apply_patch(store.issues[a["issue"]]["description"], a["patch"])
                store.issues[a["issue"]]["description"] = desc
                if a["action"] == "retarget":
                    store.issues[a["issue"]]["title"] = a["title"]
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
