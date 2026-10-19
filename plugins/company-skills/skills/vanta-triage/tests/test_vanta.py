"""Tests for scripts/vanta.py. Run: python3 -m unittest discover -s tests (from the skill directory)."""

import contextlib
import io
import json
import os
import re
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


def digest(findings):
    [g] = vanta.group_findings(findings)
    return g["advisory_digest"]


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
        # One unrelated live finding: zero findings would trip the mass-resolve guard instead.
        plan = run_plan([finding()], [{"id": "CIP-9", "title": "[Vanta] Remediate gone to 1.0.0 (stack)", "status": "In Review"}])
        self.assertEqual(self.actions(plan), {("create", None), ("resolve", "CIP-9")})

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
                 "description": f"## Vulnerability\nx\nAdvisory set: `{digest([finding()])}`\nVanta key: `dependency:acme/stack:npm:left-pad`"}
        plan = run_plan([finding()], [issue])
        self.assertEqual(self.actions(plan), {("keep", "CIP-1")})
        issue["description"] = "## Vulnerability\nx\nVanta key: `dependency:acme/stack:npm:left-pad`"  # filed before the digest line
        self.assertEqual(self.actions(run_plan([finding()], [issue])), {("refresh", "CIP-1")})

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
        self.assertTrue(plan["actions"][0].get("fetch_description"))  # its Images line is checked by digest

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


class SecondReview(unittest.TestCase):
    def test_advisory_keeps_every_affected_range(self):
        fs = [finding(id="1", packageIdentifier="npm-left-pad >= 1.0.0, < 1.2.3", fixedVersion="1.2.3"),
              finding(id="2", packageIdentifier="npm-left-pad >= 2.0.0, < 2.0.5", fixedVersion="2.0.5",
                      externalURL="https://github.com/acme/stack/security/dependabot/8")]
        [g] = vanta.group_findings(fs)
        self.assertIn(">= 1.0.0, < 1.2.3", g["description"])
        self.assertIn(">= 2.0.0, < 2.0.5", g["description"])
        self.assertEqual(g["targets"], ["2.0.5", "1.2.3"])
        self.assertEqual(g["title"].count("CVE-2026-0001"), 0)  # remediate titles carry no advisory ids

    def test_assess_title_lists_each_advisory_once(self):
        fs = [finding(id=str(i), targetId="a-img", packageIdentifier=f"glibc:2.4{i}", fixedVersion="NotAvailable",
                      externalURL="https://aws/x") for i in (1, 2)]
        [g] = vanta.group_findings(fs)
        self.assertEqual(g["title"].count("CVE-2026-0001"), 1)

    def test_key_preserves_package_case(self):
        f = finding(packageIdentifier="go-github.com/BurntSushi/toml < 1.4.0", fixedVersion="1.4.0")
        [g] = vanta.group_findings([f])
        self.assertEqual(g["key"], "dependency:acme/stack:go:github.com/BurntSushi/toml")

    def test_lowercase_key_line_still_matches(self):
        f = finding(packageIdentifier="go-github.com/BurntSushi/toml < 1.4.0", fixedVersion="1.4.0")
        issue = {"id": "CIP-1", "title": "[Vanta] Remediate github.com/BurntSushi/toml to 1.4.0 (stack)", "status": "Todo",
                 "description": f"## Vulnerability\nAdvisory set: `{digest([f])}`\nVanta key: `dependency:acme/stack:go:github.com/burntsushi/toml`"}
        self.assertEqual([(a["action"], a.get("issue")) for a in run_plan([f], [issue])["actions"]], [("keep", "CIP-1")])


class ThirdReview(unittest.TestCase):
    def test_python_suffixes_order_against_release(self):
        k = vanta.version_key
        self.assertLess(k("1.2.3rc1"), k("1.2.3"))
        self.assertLess(k("1.2.3.dev1"), k("1.2.3"))
        self.assertLess(k("1.2.3"), k("1.2.3.post1"))
        self.assertLess(k("1.2.3.post1"), k("1.2.4"))
        self.assertLess(k("1.2.3-rc.1"), k("1.2.3"))  # semver pre-releases unchanged
        self.assertFalse(vanta.covers(["1.2.3rc1"], ["1.2.3"]))
        self.assertFalse(vanta.covers(["1.2.3.dev1"], ["1.2.3"]))
        self.assertEqual(vanta.max_per_line(["1.2.3rc1", "1.2.3"]), ["1.2.3"])

    def test_unknown_repo_dependency_keys_by_asset(self):
        assets = dict(ASSETS, **{"a-other": {"id": "a-other", "name": "other", "assetType": "CODE_REPOSITORY"}})
        fs = [vanta.normalise(vuln(id=str(i), targetId=t, externalURL="https://example.com/scanner/finding/1"), assets, CONFIG)
              for i, t in ((1, "a-repo"), (2, "a-other"))]
        groups = vanta.group_findings(fs)
        self.assertEqual(sorted(g["key"] for g in groups),
                         ["dependency:other:npm:left-pad", "dependency:stack:npm:left-pad"])


class FourthReview(unittest.TestCase):
    """G1: the advisory table must be refreshed when the advisory set changes but the target does not."""
    FIXED = finding(id="1")
    UNFIXED = finding(id="2", name="CVE-2026-0002", packageIdentifier="npm-left-pad < 2.0.0", fixedVersion=None,
                      externalURL="https://github.com/acme/stack/security/dependabot/8")

    def issue(self, findings, **kw):
        [g] = vanta.group_findings(findings)
        return {"id": "CIP-1", "title": g["title"], "status": "Todo", "description": g["description"], **kw}

    def test_new_unfixed_advisory_refreshes_unchanged_target(self):
        issue = self.issue([self.FIXED])
        self.assertEqual(issue["title"], "[Vanta] Remediate left-pad to 1.2.2 (stack)")
        plan = run_plan([self.FIXED, self.UNFIXED], [issue])
        [a] = plan["actions"]
        self.assertEqual((a["action"], a.get("issue")), ("refresh", "CIP-1"))
        self.assertEqual(a["title"], issue["title"])
        self.assertIn("< 2.0.0", plan["groups"][0]["description"])

    def test_removed_advisory_refreshes_unchanged_target(self):
        issue = self.issue([self.FIXED, self.UNFIXED])
        [a] = run_plan([self.FIXED], [issue])["actions"]
        self.assertEqual((a["action"], a.get("issue")), ("refresh", "CIP-1"))

    def test_unchanged_advisories_keep(self):
        issue = self.issue([self.FIXED, self.UNFIXED])
        [a] = run_plan([self.FIXED, self.UNFIXED], [issue])["actions"]
        self.assertEqual((a["action"], a.get("issue")), ("keep", "CIP-1"))
        self.assertFalse(a.get("fetch_description"))

    def test_keep_without_description_asks_for_it(self):
        issue = {"id": "CIP-1", "title": "[Vanta] Remediate left-pad to 1.2.2 (stack)", "status": "Todo"}
        [a] = run_plan([self.FIXED, self.UNFIXED], [issue])["actions"]
        self.assertEqual((a["action"], a.get("issue")), ("keep", "CIP-1"))
        self.assertTrue(a.get("fetch_description"))


def run_plan_files(findings, files, config=None):
    """Plan over several --issues files, as SKILL.md step 3 passes <scratch>/issues/*; files is {name: JSON}."""
    with tempfile.TemporaryDirectory() as d:
        fp, cp = Path(d, "f.json"), Path(d, "c.json")
        fp.write_text(json.dumps(findings))
        cp.write_text(json.dumps(config or {}))
        paths = []
        for name, data in sorted(files.items()):
            paths.append(str(Path(d, name)))
            Path(paths[-1]).write_text(json.dumps(data))
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = vanta.main(["plan", "--findings", str(fp), "--issues", *paths, "--config", str(cp), "--today", "2026-10-13"])
        assert code == 0
        return json.loads(out.getvalue())


def container(id, name, image="a-img", pkg="openssl:3.0.15"):
    return finding(id=id, name=name, targetId=image, packageIdentifier=pkg, fixedVersion="NotAvailable",
                   externalURL=f"https://aws/inspector/{id}")


class FifthReview(unittest.TestCase):
    """Every current advisory must reach the Linear issue that remediation reads."""
    FIXED = finding(id="1")
    UNFIXED = finding(id="2", name="CVE-2026-0002", packageIdentifier="npm-left-pad < 2.0.0", fixedVersion=None,
                      externalURL="https://github.com/acme/stack/security/dependabot/8")

    def described(self, findings, **kw):
        [g] = vanta.group_findings(findings)
        return {"id": "CIP-1", "title": g["title"], "status": "Todo", "description": g["description"], **kw}

    def test_h1_bare_get_issue_file_supplies_the_description(self):
        listed = {"issues": [{"id": "CIP-1", "title": "[Vanta] Remediate left-pad to 1.2.2 (stack)", "status": "Todo"}],
                  "hasNextPage": False}
        fetched = self.described([self.FIXED])  # get_issue returns the bare issue object
        plan = run_plan_files([self.FIXED, self.UNFIXED], {"unstarted.json": listed, "CIP-1.json": fetched})
        [a] = plan["actions"]
        self.assertEqual((a["action"], a.get("issue")), ("refresh", "CIP-1"))

    def test_h1_bare_get_issue_file_settles_ambiguity(self):
        key = "dependency:acme/stack:rust:tar"
        title = "[Vanta] Remediate tar to 9.9.9 (stack)"
        plan = run_plan_files(Regressions.TAR, {
            "unstarted.json": {"issues": [{"id": "CIP-1", "title": title, "status": "Todo"}]},
            "CIP-1.json": {"id": "CIP-1", "title": title, "status": "Todo", "description": f"...\n\nVanta key: `{key}`"}})
        [r] = [a for a in plan["actions"] if a.get("issue") == "CIP-1"]
        self.assertEqual((r["action"], r["key"]), ("retarget", key))
        self.assertNotIn("ambiguous", r)

    def test_h3_container_advisory_added_refreshes_and_keeps_title(self):
        issue = self.described([container("1", "CVE-A")])
        issue["title"] = "[Vanta] Assess openssl CVE-A — not affected (cts image)"
        plan = run_plan([container("1", "CVE-A"), container("2", "CVE-B")], [issue])
        [a] = plan["actions"]
        self.assertEqual((a["action"], a.get("issue")), ("refresh", "CIP-1"))
        self.assertEqual(a["title"], issue["title"])

    def test_h3_container_keep_without_description_asks_for_it(self):
        issue = {"id": "CIP-1", "title": "[Vanta] Assess openssl CVE-A (cts image)", "status": "Todo"}
        [a] = run_plan([container("1", "CVE-A")], [issue])["actions"]
        self.assertEqual((a["action"], a.get("issue")), ("keep", "CIP-1"))
        self.assertTrue(a.get("fetch_description"))

    def test_r2a_container_image_added_refreshes_images_line(self):
        assets = {**ASSETS, "a-img2": {"id": "a-img2", "name": "zerokms", "assetType": "CONTAINER_REPOSITORY"}}
        config = {"images": {"cts": {"repo": "acme/suite"}, "zerokms": {"repo": "acme/suite"}}}
        def f(id, target):
            return vanta.normalise(vuln(id=id, name="CVE-A", targetId=target, packageIdentifier="openssl:3.0.15",
                                        fixedVersion="NotAvailable", externalURL=f"https://aws/{id}"), assets, config)
        issue = self.described([f("1", "a-img")])  # tracked when only cts was affected
        plan = run_plan_files([f("1", "a-img"), f("2", "a-img2")], {"i.json": [issue]}, config)
        [a] = plan["actions"]
        self.assertEqual((a["action"], a.get("issue")), ("refresh", "CIP-1"))

    def test_r2b_recently_done_issue_does_not_swallow_a_new_advisory(self):
        done = {**self.described([self.FIXED]), "status": "Done", "statusType": "completed",
                "completedAt": "2026-10-10T01:00:00Z"}
        plan = run_plan([self.UNFIXED], [done])  # CVE-2026-0002 is new: CIP-1 never tracked it
        self.assertEqual({(a["action"], a.get("issue")) for a in plan["actions"]}, {("create", None)})

    def test_r2b_recently_done_issue_with_same_advisories_awaits_rescan(self):
        done = {**self.described([self.FIXED]), "status": "Done", "completedAt": "2026-10-10T01:00:00Z"}
        [a] = run_plan([self.FIXED], [done])["actions"]
        self.assertEqual((a["action"], a.get("issue"), a.get("fetch_description")), ("await-rescan", "CIP-1", None))

    def test_r2b_recently_done_issue_unseen_asks_for_description(self):
        done = {"id": "CIP-1", "title": "[Vanta] Remediate left-pad to 1.2.2 (stack)", "status": "Done",
                "completedAt": "2026-10-10T01:00:00Z"}
        [a] = run_plan([self.FIXED], [done])["actions"]
        self.assertEqual((a["action"], a.get("fetch_description")), ("await-rescan", True))

    def test_r2c_refresh_patch_replaces_only_the_generated_span(self):
        issue = self.described([self.FIXED])
        issue["description"] = "Owner: payments.\n\n" + issue["description"] + "\n\nNotes: pinned."
        plan = run_plan([self.FIXED, self.UNFIXED], [issue])
        [a], [g] = plan["actions"], plan["groups"]
        self.assertEqual(a["patch"], [{"op": "replace", "old_string": self.described([self.FIXED])["description"],
                                       "new_string": g["description"]}])

    def test_r2c_legacy_patch_prepends(self):
        issue = {"id": "CIP-1", "title": "[Vanta] Remediate left-pad to 1.2.0 (stack)", "status": "Todo",
                 "description": "## Vulnerability\n\nfiled by hand"}
        plan = run_plan_files([self.FIXED], {"CIP-1.json": issue})  # get_issue: a list's description may be truncated
        [a], [g] = plan["actions"], plan["groups"]
        self.assertEqual((a["action"], a["patch"]), ("retarget", [{"op": "prepend", "text": g["description"] + "\n\n---\n\n"}]))

    def test_r2c_retarget_without_description_asks_for_it(self):
        issue = {"id": "CIP-1", "title": "[Vanta] Remediate left-pad to 1.2.0 (stack)", "status": "Todo"}
        [a] = run_plan([self.FIXED], [issue])["actions"]
        self.assertEqual((a["action"], a.get("fetch_description"), a.get("patch")), ("retarget", True, None))

    def test_r2e_remediate_losing_every_fix_refreshes_and_keeps_title(self):
        issue = self.described([self.FIXED, self.UNFIXED])
        [a] = run_plan([self.UNFIXED], [issue])["actions"]
        self.assertEqual((a["action"], a["title"]), ("refresh", issue["title"]))

    def test_r2f_over_covering_title_refreshes_and_keeps_title(self):
        two = finding(id="3", name="CVE-2026-0003", packageIdentifier="npm-left-pad >= 2.0.0, < 2.0.5", fixedVersion="2.0.5",
                      externalURL="https://github.com/acme/stack/security/dependabot/9")
        issue = self.described([self.FIXED, two])
        self.assertIn("2.0.5 / 1.2.2", issue["title"])
        [a] = run_plan([self.FIXED], [issue])["actions"]
        self.assertEqual((a["action"], a["title"]), ("refresh", issue["title"]))

    def test_generated_span_contract(self):
        """vanta-remediate reads only the first "## Vulnerability" through the first "Vanta key:" line after it."""
        for g in vanta.group_findings([self.FIXED, self.UNFIXED, container("c1", "CVE-A")]):
            d = g["description"]
            self.assertEqual((d.count("## Vulnerability"), d.count("Vanta key:")), (1, 1))
            span = vanta.generated_span(d)
            self.assertEqual(span, d)
            for part in ("### Advisories", f"Advisory set: `{g['advisory_digest']}`"):
                self.assertIn(part, span)
            if g["kind"] == "assess-container":
                self.assertIn("**Images:** `cts`", span)

    def test_h1_unknown_shape_exits_2_naming_the_file(self):
        with tempfile.TemporaryDirectory() as d:
            fp, ip = Path(d, "f.json"), Path(d, "odd.json")
            fp.write_text("[]")
            ip.write_text(json.dumps({"data": {"something": 1}}))
            err = io.StringIO()
            with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
                code = vanta.main(["plan", "--findings", str(fp), "--issues", str(ip), "--today", "2026-10-13"])
        self.assertEqual(code, 2)
        self.assertIn("odd.json", err.getvalue())

    def test_h1_host_saved_text_blocks_and_issue_wrapper(self):
        fetched = self.described([self.FIXED])
        blocks = [{"type": "text", "text": json.dumps({"issue": fetched})}]
        plan = run_plan_files([self.FIXED, self.UNFIXED], {"a.json": {"issues": [], "hasNextPage": False}, "CIP-1.json": blocks})
        self.assertEqual([(a["action"], a.get("issue")) for a in plan["actions"]], [("refresh", "CIP-1")])

    def test_h1_fetched_description_wins_over_listed(self):
        listed = {**self.described([self.FIXED, self.UNFIXED]), "description": "truncated"}
        fetched = self.described([self.FIXED])
        plan = run_plan_files([self.FIXED], {"z-list.json": [listed], "CIP-1.json": fetched})
        self.assertEqual([a["action"] for a in plan["actions"]], ["keep"])


class SixthReview(unittest.TestCase):
    """J1: one Linear issue is one record, whichever of its ids (uuid or CIP identifier) each response carries.

    The connector observed on 2026-10-14 returns {"id": "CIP-4920", "uuid": "9b16d9ac-…"} from both list_issues
    and get_issue, but the plan's own contract accepts id or identifier, so every shape below must merge."""
    UUID = "9b16d9ac-46a0-4652-af85-1a59690e7e06"

    def shapes(self):
        [g] = vanta.group_findings([FifthReview.FIXED])
        row = {"title": g["title"], "status": "Todo", "statusType": "unstarted"}
        detail = {**row, "description": g["description"]}
        return {
            "list uuid id, get both (review's shape)": ({"id": self.UUID, **row},
                                                        {"id": self.UUID, "identifier": "CIP-1", **detail}),
            "list uuid id, get identifier as id": ({"id": self.UUID, **row}, {"id": "CIP-1", "uuid": self.UUID, **detail}),
            "list identifier+uuid, get uuid id": ({"id": "CIP-1", "uuid": self.UUID, **row},
                                                  {"id": self.UUID, "identifier": "CIP-1", **detail}),
            "connector shape (control)": ({"id": "CIP-1", "uuid": self.UUID, **row},
                                          {"id": "CIP-1", "uuid": self.UUID, **detail}),
        }

    def test_j1_list_and_get_records_of_one_issue_merge(self):
        for name, (listed, fetched) in self.shapes().items():
            with self.subTest(name):
                plan = run_plan_files([FifthReview.FIXED], {"a-list.json": {"issues": [listed], "hasNextPage": False},
                                                            "CIP-1.json": fetched})
                [g] = plan["groups"]
                self.assertIsNone(g.get("duplicates"), "an issue was marked as its own duplicate")
                self.assertEqual([(a["action"], a.get("issue")) for a in plan["actions"]], [("keep", "CIP-1")])


    def test_j4_issue_rendered_before_the_advisory_block_refreshes_once(self):
        # Issues filed before the JSON advisory block carry the old digest (rows only); the block's schema is in
        # the new digest, so each such issue is refreshed once and gains the block remediation reads.
        import hashlib
        [g] = vanta.group_findings([FifthReview.FIXED])
        rows = sorted([a["id"], a["affected"] or "", a["fixed_version"] or ""] for a in g["advisories"])
        old_digest = hashlib.sha256(json.dumps(rows).encode()).hexdigest()[:12]
        old = re.sub(r"\n\nThe table above.*?```\n", "\n", g["description"], flags=re.S)
        old = old.replace(g["advisory_digest"], old_digest)
        self.assertNotIn("```json", old)
        plan = run_plan_files([FifthReview.FIXED], {"CIP-1.json": {"id": "CIP-1", "title": g["title"], "status": "Todo",
                                                                   "description": old}})
        [a] = plan["actions"]
        self.assertEqual(a["action"], "refresh")
        self.assertIn("```json", a["patch"][0]["new_string"])


class SeventhReview(unittest.TestCase):
    """PR #6 review (coderdan): plans that close an issue whose finding is still active, or write a second section."""
    ZK_ASSETS = {**ASSETS, "a-zk": {"id": "a-zk", "name": "zerokms", "assetType": "CONTAINER_REPOSITORY"}}

    def test_f2_mapping_an_image_keeps_its_issue_open(self):
        # Run 1: zerokms is missing from the images map, so its issue is keyed by the image name.
        f = vanta.normalise(vuln(id="1", name="CVE-A", targetId="a-zk", packageIdentifier="openssl:3.0.15",
                                 fixedVersion="NotAvailable", externalURL="https://aws/1"), self.ZK_ASSETS, CONFIG)
        [g] = vanta.group_findings([dict(f)])
        self.assertEqual(g["key"], "container:zerokms:openssl")
        issue = {"id": "CIP-1", "title": g["title"], "status": "Todo", "description": g["description"]}
        # Run 2: the operator adds zerokms to the map, as the report asks; the finding is still active.
        mapped = {"images": {**CONFIG["images"], "zerokms": {"repo": "acme/suite"}}}
        plan = run_plan_files([f], {"CIP-1.json": issue}, mapped)
        acts = {(a["action"], a.get("issue")) for a in plan["actions"]}
        self.assertNotIn(("resolve", "CIP-1"), acts, "the issue was closed while its finding is still active")
        self.assertNotIn(("create", None), acts, "a duplicate issue was filed for a tracked finding")

    def test_f3_issue_fitting_two_groups_is_not_resolved(self):
        foo = [finding(id="1", packageIdentifier="npm-foo < 1.2.0", fixedVersion="1.2.0"),
               finding(id="2", packageIdentifier="rust-foo < 1.2.0", fixedVersion="1.2.0", name="CVE-2")]
        issues = [{"id": f"CIP-{n}", "title": "[Vanta] Remediate foo to 1.2.0 (stack)", "status": "Todo"} for n in (1, 2, 3)]
        plan = run_plan(foo, issues)
        acts = {(a["action"], a.get("issue")) for a in plan["actions"]}
        self.assertNotIn(("resolve", "CIP-3"), acts, "an issue for an active finding was closed as Done")

    def test_f8_truncated_list_description_does_not_prepend_a_second_section(self):
        [g] = vanta.group_findings([FifthReview.FIXED])
        full = g["description"]
        truncated = full[:full.index("Vanta key:")]  # connector ignored `fields` and truncated the description
        listed = {"id": "CIP-1", "title": g["title"], "status": "Todo", "description": truncated}
        [a] = run_plan_files([FifthReview.FIXED], {"a-list.json": {"issues": [listed], "hasNextPage": False}})["actions"]
        self.assertNotIn("prepend", [op["op"] for op in a.get("patch") or []],
                         "a second generated section would be written above the existing one")
        self.assertTrue(a.get("fetch_description"), "a truncated description must be fetched before it is judged")

    def test_f5_zero_findings_withholds_every_resolve(self):
        # A partial Vanta response (zero findings) looks exactly like everything being fixed.
        issues = [{"id": f"CIP-{n}", "title": f"[Vanta] Remediate pkg{n} to 1.0.0 (stack)", "status": "Todo"}
                  for n in range(10)]
        plan = run_plan([], issues)
        self.assertEqual([a for a in plan["actions"] if a["action"] == "resolve"], [])
        self.assertEqual({(a["action"], a["issue"]) for a in plan["actions"]}, {("guard", i["id"]) for i in issues})
        self.assertIn("zero findings", plan["guard"])

    def test_f5_mass_resolve_guard_threshold(self):
        # More than 5 resolves and more than half the open package issues trips it; either alone does not.
        def issues(n):
            return [{"id": f"CIP-{k}", "title": f"[Vanta] Remediate pkg{k} to 1.0.0 (stack)", "status": "Todo"}
                    for k in range(n)]
        live = [finding(id=str(k), packageIdentifier=f"npm-live{k} < 1.2.2", name=f"CVE-{k}") for k in range(7)]
        live_issues = [{"id": f"CIP-L{k}", "title": f"[Vanta] Remediate live{k} to 1.2.2 (stack)", "status": "Todo"}
                       for k in range(7)]
        for stale, tracked, tripped in ((6, 0, True), (5, 0, False), (6, 7, False), (7, 6, True)):
            with self.subTest(stale=stale, tracked=tracked):
                plan = run_plan(live, issues(stale) + live_issues[:tracked])
                kinds = [a["action"] for a in plan["actions"] if a.get("issue", "").startswith("CIP-") and
                         not a["issue"].startswith("CIP-L")]
                self.assertEqual(kinds, ["guard" if tripped else "resolve"] * stale)
                self.assertEqual(plan["guard"] is not None, tripped)


class Credentials(unittest.TestCase):
    def test_no_credentials_means_network_secret(self):
        env = {k: v for k, v in os.environ.items() if not k.startswith("VANTA_")}
        with unittest.mock.patch.dict(os.environ, env, clear=True):
            self.assertIsNone(vanta.load_credentials())

    def test_half_set_credentials_exit(self):
        env = {k: v for k, v in os.environ.items() if not k.startswith("VANTA_")}
        env["VANTA_CLIENT_ID"] = "id"
        with unittest.mock.patch.dict(os.environ, env, clear=True):
            with self.assertRaises(SystemExit) as cm:
                vanta.load_credentials()
        self.assertIn("VANTA_CLIENT_SECRET", str(cm.exception.code))

    def test_secret_alone_exits(self):
        env = {k: v for k, v in os.environ.items() if not k.startswith("VANTA_")}
        env["VANTA_CLIENT_SECRET"] = "s"
        with unittest.mock.patch.dict(os.environ, env, clear=True):
            with self.assertRaises(SystemExit) as cm:
                vanta.load_credentials()
        self.assertIn("VANTA_CLIENT_ID", str(cm.exception.code))

    def test_env_file_wins_over_a_stray_variable(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
            json.dump({"client_id": "id", "client_secret": "s"}, fh)
        env = {k: v for k, v in os.environ.items() if not k.startswith("VANTA_")}
        env.update(VANTA_ENV_FILE=fh.name, VANTA_CLIENT_ID="stray")
        with unittest.mock.patch.dict(os.environ, env, clear=True):
            self.assertEqual(vanta.load_credentials(), ("id", "s"))
        os.unlink(fh.name)

    def test_network_secret_403_names_the_scope(self):
        def urlopen(req, timeout):
            raise vanta.urllib.error.HTTPError(req.full_url, 403, "Forbidden", {}, io.BytesIO(b"{}"))

        with unittest.mock.patch.object(vanta.urllib.request, "urlopen", urlopen):
            with self.assertRaises(SystemExit) as cm:
                vanta.get_all("/v1/vulnerabilities", None)
        self.assertIn(vanta.SCOPE, str(cm.exception.code))

    def test_network_secret_sends_no_authorization(self):
        sent = []

        class Resp(io.BytesIO):
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

        def urlopen(req, timeout):
            sent.append(req)
            return Resp(json.dumps({"results": {"data": [{"id": "v1"}], "pageInfo": {"hasNextPage": False}}}).encode())

        with unittest.mock.patch.object(vanta.urllib.request, "urlopen", urlopen):
            self.assertEqual(vanta.get_all("/v1/vulnerabilities", None), [{"id": "v1"}])
        self.assertIsNone(sent[0].get_header("Authorization"))

    def test_network_secret_401_names_the_secret(self):
        def urlopen(req, timeout):
            raise vanta.urllib.error.HTTPError(req.full_url, 401, "Unauthorized", {}, io.BytesIO(b"{}"))

        with unittest.mock.patch.object(vanta.urllib.request, "urlopen", urlopen):
            with self.assertRaises(SystemExit) as cm:
                vanta.get_all("/v1/vulnerabilities", None)
        self.assertIn("network secret", str(cm.exception.code))

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
