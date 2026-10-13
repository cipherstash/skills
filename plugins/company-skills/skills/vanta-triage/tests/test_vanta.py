"""Tests for scripts/vanta.py. Run: python3 -m unittest discover -s tests (from the skill directory)."""

import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
import unittest.mock
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import vanta  # noqa: E402

CONFIG = {"images": {"cts": {"repo": "acme/suite"}}}
ASSETS = {
    "a-repo": {"id": "a-repo", "name": "stack", "assetType": "CODE_REPOSITORY"},
    "a-img": {"id": "a-img", "name": "cts", "assetType": "CONTAINER_REPOSITORY"},
}


def vuln(**kw):
    base = {
        "id": kw.pop("id", "v1"), "name": "CVE-2026-0001", "targetId": "a-repo", "severity": "HIGH",
        "cvssSeverityScore": 7.5, "fixedVersion": "1.2.2", "remediateByDate": "2026-11-05T00:00:00Z",
        "firstDetectedDate": "2026-10-05T00:00:00Z", "packageIdentifier": "npm-left-pad >= 1.0.0, < 1.2.2",
        "externalURL": "https://github.com/acme/stack/security/dependabot/7",
        "relatedUrls": ["https://nvd.nist.gov/x", "https://github.com/advisories/GHSA-abcd-efgh-ijkl"],
        "description": "Left pad pads wrongly. More detail here.", "deactivateMetadata": None,
    }
    base.update(kw)
    return base


def finding(**kw):
    return vanta.normalise(vuln(**kw), ASSETS, CONFIG)


def run_plan(findings, issues):
    with tempfile.TemporaryDirectory() as d:
        fp, ip = Path(d, "f.json"), Path(d, "i.json")
        fp.write_text(json.dumps(findings))
        ip.write_text(json.dumps(issues))
        cp = Path(d, "c.json")
        cp.write_text("{}")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = vanta.main(["plan", "--findings", str(fp), "--issues", str(ip), "--config", str(cp), "--today", "2026-10-13"])
        assert code == 0
        return json.loads(out.getvalue())


class Versions(unittest.TestCase):
    def test_ordering(self):
        k = vanta.version_key
        self.assertLess(k("1.2.9"), k("1.2.10"))
        self.assertLess(k("1.0.0-beta.1"), k("1.0.0"))
        self.assertLess(k("0.26.0-beta.1"), k("0.26.2"))
        self.assertEqual(k("v1.2"), k("1.2.0"))
        self.assertLess(k("1:1.3.dfsg"), k("1.4"))

    def test_lines(self):
        self.assertEqual(vanta.major_line("5.0.12"), "5")
        self.assertEqual(vanta.major_line("0.23.45"), "0.23")
        self.assertEqual(vanta.max_per_line(["5.0.7", "5.0.12", "2.1.7", "2.1.2"]), ["5.0.12", "2.1.7"])

    def test_covers(self):
        self.assertTrue(vanta.covers(["5.0.12", "2.1.7"], ["5.0.12"]))
        self.assertFalse(vanta.covers(["5.0.7"], ["5.0.12"]))
        self.assertFalse(vanta.covers(["5.0.12"], ["2.1.7"]))


class Normalise(unittest.TestCase):
    def test_dependency(self):
        f = finding()
        self.assertEqual((f["kind"], f["repo"], f["ecosystem"], f["package"]), ("dependency", "acme/stack", "npm", "left-pad"))
        self.assertEqual(f["affected"], ">= 1.0.0, < 1.2.2")
        self.assertEqual(f["sla"], "2026-11-05")
        self.assertEqual(f["advisory_url"], "https://github.com/advisories/GHSA-abcd-efgh-ijkl")

    def test_scoped_and_hyphenated_packages(self):
        self.assertEqual(finding(packageIdentifier="npm-@scope/some-pkg < 2.0.0")["package"], "@scope/some-pkg")
        self.assertEqual(finding(packageIdentifier="rust-aws-smithy-json <= 0.62.6")["package"], "aws-smithy-json")
        f = finding(packageIdentifier="npm-sprintf-js", fixedVersion=None)
        self.assertEqual((f["package"], f["affected"], f["fixed_version"]), ("sprintf-js", None, None))

    def test_container(self):
        f = finding(targetId="a-img", packageIdentifier="glibc:2.41", fixedVersion="NotAvailable",
                    externalURL="https://console.aws.amazon.com/inspector/x")
        self.assertEqual((f["kind"], f["target"], f["repo"], f["ecosystem"], f["package"], f["affected"], f["fixed_version"]),
                         ("container", "cts", "acme/suite", "os", "glibc", "2.41", None))


class Grouping(unittest.TestCase):
    def test_groups_by_repo_and_package_with_max_per_major(self):
        fs = [finding(id="1", fixedVersion="5.0.7"), finding(id="2", fixedVersion="5.0.12", name="CVE-2"),
              finding(id="3", fixedVersion="2.1.7", name="CVE-3"),
              finding(id="4", externalURL="https://github.com/acme/other/security/dependabot/1")]
        groups = vanta.group_findings(fs)
        self.assertEqual(len(groups), 2)
        g = next(g for g in groups if g["repo"] == "acme/stack")
        self.assertEqual(g["targets"], ["5.0.12", "2.1.7"])
        self.assertEqual(g["title"], "[Vanta] Remediate left-pad to 5.0.12 / 2.1.7 (stack)")
        self.assertIn("Vanta key: `dependency:acme/stack:npm:left-pad`", g["description"])
        self.assertIn("CVE-2026-0001 / GHSA-abcd-efgh-ijkl", g["description"])
        self.assertIn("| `>= 1.0.0, < 1.2.2` | 5.0.12 |", g["description"])

    def test_worst_severity_earliest_sla(self):
        fs = [finding(id="1", severity="MEDIUM", remediateByDate="2026-12-01T00:00:00Z"),
              finding(id="2", severity="CRITICAL", remediateByDate="2026-11-01T00:00:00Z", name="CVE-2")]
        [g] = vanta.group_findings(fs)
        self.assertEqual((g["severity"], g["priority"], g["sla"]), ("CRITICAL", 1, "2026-11-01"))

    def test_no_fix_is_track_upstream(self):
        [g] = vanta.group_findings([finding(fixedVersion=None)])
        self.assertEqual(g["kind"], "track-upstream")
        self.assertEqual(g["title"], "[Vanta] Track upstream fix for left-pad (stack)")

    def test_partial_fix_is_remediate_and_names_unfixed(self):
        [g] = vanta.group_findings([finding(id="1"), finding(id="2", fixedVersion=None, name="CVE-NOFIX")])
        self.assertEqual(g["kind"], "remediate")
        self.assertEqual(g["unfixed_advisories"], ["CVE-NOFIX"])
        self.assertIn("CVE-NOFIX", g["description"])

    def test_same_advisory_many_alerts_is_one_row(self):
        fs = [finding(id=str(i), externalURL=f"https://github.com/acme/stack/security/dependabot/{i}") for i in range(3)]
        [g] = vanta.group_findings(fs)
        self.assertEqual(len(g["advisories"]), 1)
        self.assertEqual(len(g["advisories"][0]["findings"]), 3)


class Plan(unittest.TestCase):
    def actions(self, plan):
        return {(a["action"], a.get("issue")) for a in plan["actions"]}

    def test_create_when_untracked(self):
        plan = run_plan([finding()], [])
        self.assertEqual(self.actions(plan), {("create", None)})

    def test_keep_when_tracked_by_title(self):
        plan = run_plan([finding()], [{"identifier": "CIP-1", "title": "[Vanta] Remediate left-pad to 1.2.2 (stack)",
                                       "state": {"name": "In Review"}}])
        self.assertEqual(self.actions(plan), {("keep", "CIP-1")})

    def test_retarget_when_vanta_needs_higher(self):
        plan = run_plan([finding(fixedVersion="1.2.5")], [{"id": "CIP-1", "title": "[Vanta] Remediate left-pad to 1.2.2 (stack)", "status": "Todo"}])
        self.assertEqual(self.actions(plan), {("retarget", "CIP-1")})

    def test_retarget_track_upstream_once_fix_exists(self):
        plan = run_plan([finding()], [{"id": "CIP-1", "title": "[Vanta] Track upstream fix for left-pad (stack)", "status": "Todo"}])
        self.assertEqual(self.actions(plan), {("retarget", "CIP-1")})

    def test_resolve_open_issue_without_finding(self):
        plan = run_plan([], [{"id": "CIP-9", "title": "[Vanta] Remediate gone to 1.0.0 (stack)", "status": "In Review"}])
        self.assertEqual(self.actions(plan), {("resolve", "CIP-9")})

    def test_recently_done_covering_issue_awaits_rescan(self):
        done = {"id": "CIP-1", "title": "[Vanta] Remediate left-pad to 1.2.2 (stack)", "status": "Done", "completedAt": "2026-10-10T01:00:00Z"}
        self.assertEqual(self.actions(run_plan([finding()], [done])), {("await-rescan", "CIP-1")})

    def test_old_or_insufficient_done_issue_creates(self):
        old = {"id": "CIP-1", "title": "[Vanta] Remediate left-pad to 1.2.2 (stack)", "status": "Done", "completedAt": "2026-09-01T01:00:00Z"}
        low = {"id": "CIP-2", "title": "[Vanta] Remediate left-pad to 1.2.0 (stack)", "status": "Done", "completedAt": "2026-10-10T01:00:00Z"}
        self.assertEqual(self.actions(run_plan([finding()], [old, low])), {("create", None)})

    def test_closed_issues_are_ignored(self):
        plan = run_plan([finding()], [{"id": "CIP-1", "title": "[Vanta] Remediate left-pad to 1.2.2 (stack)", "status": "Done"}])
        self.assertEqual(self.actions(plan), {("create", None)})

    def test_key_line_beats_title(self):
        issue = {"id": "CIP-1", "title": "[Vanta] Remediate left-pad to 1.2.2 (old-repo-name)", "status": "Todo",
                 "description": "x\nVanta key: `dependency:acme/stack:npm:left-pad`"}
        plan = run_plan([finding()], [issue])
        self.assertEqual(self.actions(plan), {("keep", "CIP-1")})

    def test_repo_name_must_match(self):
        plan = run_plan([finding()], [{"id": "CIP-1", "title": "[Vanta] Remediate left-pad to 1.2.2 (other)", "status": "Todo"}])
        self.assertEqual(self.actions(plan), {("create", None), ("resolve", "CIP-1")})

    def test_container_matches_assess_title(self):
        f = finding(targetId="a-img", packageIdentifier="zlib:1.3.1", fixedVersion="NotAvailable", externalURL="https://aws/x")
        plan = run_plan([f], [{"id": "CIP-5", "title": "[Vanta] Assess zlib CVE-2026-85091 — not affected (cts image)", "status": "Todo"}])
        self.assertEqual(self.actions(plan), {("keep", "CIP-5")})

    def test_container_groups_images_of_one_repo(self):
        assets = {**ASSETS, "a-img2": {"id": "a-img2", "name": "zerokms", "assetType": "CONTAINER_REPOSITORY"}}
        config = {"images": {"cts": {"repo": "acme/suite"}, "zerokms": {"repo": "acme/suite"}}}
        fs = [vanta.normalise(vuln(id=str(i), targetId=t, packageIdentifier="cyrus-sasl2:2.1.28", fixedVersion="NotAvailable",
                                   externalURL="https://aws/x"), assets, config) for i, t in enumerate(["a-img", "a-img2"])]
        [g] = vanta.group_findings(fs)
        self.assertEqual((g["key"], g["images"]), ("container:acme/suite:cyrus-sasl2", ["cts", "zerokms"]))
        self.assertEqual(g["title"], "[Vanta] Assess cyrus-sasl2 CVE-2026-0001 (cts + zerokms images)")
        issue = {"id": "CIP-4894", "title": "[Vanta] Track upstream fix for cyrus-sasl2 (zerokms + cts images)", "status": "Todo"}
        plan = run_plan(fs, [issue])
        self.assertEqual(self.actions(plan), {("keep", "CIP-4894")})
        single = {"id": "CIP-4895", "title": "[Vanta] Assess cyrus-sasl2 CVE-2026-0001 — not affected (cts image)", "status": "Todo"}
        plan = run_plan(fs, [single])
        self.assertEqual(self.actions(plan), {("keep", "CIP-4895")})
        self.assertIn("zerokms", plan["actions"][0]["reason"])

    def test_multiple_issue_files(self):
        with tempfile.TemporaryDirectory() as d:
            paths = []
            for n, issues in enumerate([[{"id": "CIP-1", "title": "[Vanta] Remediate left-pad to 1.2.2 (stack)", "status": "Todo"}],
                                        {"issues": [{"id": "CIP-9", "title": "[Vanta] Remediate gone to 1.0.0 (stack)", "status": "Todo"}]}]):
                paths.append(str(Path(d, f"i{n}.json")))
                Path(paths[-1]).write_text(json.dumps(issues))
            fp, cp = Path(d, "f.json"), Path(d, "c.json")
            fp.write_text(json.dumps([finding()]))
            cp.write_text("{}")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                vanta.main(["plan", "--findings", str(fp), "--issues", *paths, "--config", str(cp), "--today", "2026-10-13"])
        self.assertEqual(self.actions(json.loads(out.getvalue())), {("keep", "CIP-1"), ("resolve", "CIP-9")})

    def test_unrecognised_titles_are_unparsed_not_resolved(self):
        issues = [{"id": "CIP-2", "title": '[Vanta] Remediate "SQL database CPU monitored"', "status": "Todo"},
                  {"id": "CIP-3", "title": "[Vanta] Rebuild zerokms ECR image — 21 OS-package CVEs", "status": "In Review"}]
        plan = run_plan([], issues)
        self.assertEqual(plan["actions"], [])
        self.assertEqual({u["id"] for u in plan["unparsed"]}, {"CIP-2", "CIP-3"})

    def test_duplicates_reported(self):
        issues = [{"id": "CIP-1", "title": "[Vanta] Remediate left-pad to 1.2.2 (stack)", "status": "Todo"},
                  {"id": "CIP-2", "title": "[Vanta] Remediate left-pad to 1.2.2 (stack)", "status": "Todo"}]
        plan = run_plan([finding()], issues)
        self.assertEqual(plan["groups"][0]["duplicates"], ["CIP-2"])
        self.assertEqual(self.actions(plan), {("keep", "CIP-1")})

    def test_issues_wrapped_in_object(self):
        plan = run_plan([finding()], {"issues": [{"id": "CIP-1", "title": "[Vanta] Remediate left-pad to 1.2.2 (stack)", "status": "Todo"}]})
        self.assertEqual(self.actions(plan), {("keep", "CIP-1")})


class Regressions(unittest.TestCase):
    TAR = [finding(id="1", packageIdentifier="npm-tar < 6.2.1", fixedVersion="6.2.1"),
           finding(id="2", packageIdentifier="rust-tar < 0.4.40", fixedVersion="0.4.40", name="CVE-2")]

    def actions(self, plan):
        return {(a["action"], a.get("issue")) for a in plan["actions"]}

    def test_dependabot_bare_version_identifier_does_not_crash(self):
        [g] = vanta.group_findings([finding(packageIdentifier="npm-foo 1.2.3")])
        self.assertEqual(g["repo"], "acme/stack")
        self.assertIn("(stack)", g["title"])

    def test_non_dependabot_dependency_does_not_crash_plan(self):
        plan = run_plan([finding(externalURL="https://example.com/scanner/finding/1")], [])
        self.assertEqual(len(plan["groups"]), 1)
        self.assertIn("(stack)", plan["groups"][0]["title"])

    def test_null_advisory_name_with_unfixed_findings(self):
        fs = [finding(id="1", name=None, fixedVersion=None), finding(id="2", name="CVE-2", fixedVersion=None)]
        [g] = vanta.group_findings(fs)
        self.assertEqual(len(g["advisories"]), 2)

    def test_null_advisory_name_in_container_title(self):
        f = finding(targetId="a-img", packageIdentifier="glibc:2.41", fixedVersion="NotAvailable",
                    externalURL="https://aws/x", name=None)
        [g] = vanta.group_findings([f])
        self.assertTrue(g["title"].startswith("[Vanta] Assess glibc"))

    def test_custom_open_state_is_matched(self):
        issue = {"id": "CIP-1", "title": "[Vanta] Remediate left-pad to 1.2.2 (stack)", "status": "Blocked"}
        self.assertEqual(self.actions(run_plan([finding()], [issue])), {("keep", "CIP-1")})

    def test_canceled_issue_is_not_open(self):
        issue = {"id": "CIP-1", "title": "[Vanta] Remediate left-pad to 1.2.2 (stack)", "status": "Canceled",
                 "statusType": "canceled"}
        self.assertEqual(self.actions(run_plan([finding()], [issue])), {("create", None)})

    def test_one_issue_does_not_satisfy_two_ecosystems(self):
        issue = {"id": "CIP-1", "title": "[Vanta] Remediate tar to 6.2.1 (stack)", "status": "Todo"}
        self.assertEqual(self.actions(run_plan(self.TAR, [issue])), {("keep", "CIP-1"), ("create", None)})

    def test_two_ecosystem_issues_are_stable(self):
        issues = [{"id": "CIP-1", "title": "[Vanta] Remediate tar to 6.2.1 (stack)", "status": "Todo"},
                  {"id": "CIP-2", "title": "[Vanta] Remediate tar to 0.4.40 (stack)", "status": "Todo"}]
        self.assertEqual(self.actions(run_plan(self.TAR, issues)), {("keep", "CIP-1"), ("keep", "CIP-2")})

    def test_ambiguous_match_is_flagged(self):
        issue = {"id": "CIP-1", "title": "[Vanta] Remediate tar to 9.9.9 (stack)", "status": "Todo"}
        plan = run_plan(self.TAR, [issue])
        [a] = [a for a in plan["actions"] if a.get("issue") == "CIP-1"]
        self.assertEqual(len(a["ambiguous"]), 2)

    def test_fetched_description_resolves_ambiguity(self):
        key = "dependency:acme/stack:rust:tar"
        issues = [{"id": "CIP-1", "title": "[Vanta] Remediate tar to 9.9.9 (stack)", "status": "Todo"},
                  {"id": "CIP-1", "title": "[Vanta] Remediate tar to 9.9.9 (stack)", "status": "Todo",
                   "description": f"...\n\nVanta key: `{key}`"}]
        plan = run_plan(self.TAR, issues)
        self.assertEqual(self.actions(plan), {("retarget", "CIP-1"), ("create", None)})
        [r] = [a for a in plan["actions"] if a["action"] == "retarget"]
        self.assertEqual(r["key"], key)

    def test_track_upstream_retarget_reason(self):
        plan = run_plan([finding()], [{"id": "CIP-1", "title": "[Vanta] Track upstream fix for left-pad (stack)", "status": "Todo"}])
        [a] = plan["actions"]
        self.assertEqual(a["action"], "retarget")
        self.assertIn("a fix is now available", a["reason"])


class Credentials(unittest.TestCase):
    def test_missing_credentials_exit(self):
        env = {k: v for k, v in os.environ.items() if not k.startswith("VANTA_")}
        with unittest.mock.patch.dict(os.environ, env, clear=True):
            with self.assertRaises(SystemExit) as cm:
                vanta.load_credentials()
        self.assertIn("VANTA_CLIENT_ID", str(cm.exception.code))

    def test_env_file(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
            json.dump({"client_id": "id", "client_secret": "s"}, fh)
        env = {k: v for k, v in os.environ.items() if not k.startswith("VANTA_")}
        env["VANTA_ENV_FILE"] = fh.name
        with unittest.mock.patch.dict(os.environ, env, clear=True):
            self.assertEqual(vanta.load_credentials(), ("id", "s"))
        os.unlink(fh.name)



if __name__ == "__main__":
    unittest.main()
