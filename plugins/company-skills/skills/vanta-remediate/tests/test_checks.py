"""Tests for the advisory -> deps.py check conversion (SKILL.md step 1, scripts/checks.py).

Issues are rendered by vanta-triage's real vanta.py, measured with the real deps.py on fixture lockfiles, and
judged by the real gate.py. The requirements under test:
  - every current advisory must reach verification;
  - only trustworthy evidence can certify remediation.

step1() is the conversion under test: `checks.py --issue FILE`, as SKILL.md step 1 runs it. Its output fields used
here are status ("ok" or "skip"), fix_checks (deps.py argument lists; every one must exit 0), residual_check
(an argument list or null) and unfixed_advisories (ids for gate.py --unfixed-advisory).

Run: python3 -m unittest discover -s tests -p 'test_checks.py' (from the skill directory).
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILLS = Path(__file__).resolve().parents[2]
SCRIPTS = SKILLS / "vanta-remediate" / "scripts"
DEPS, GATE, CHECKS = SCRIPTS / "deps.py", SCRIPTS / "gate.py", SCRIPTS / "checks.py"
_spec = importlib.util.spec_from_file_location("vanta_triage", SKILLS / "vanta-triage" / "scripts" / "vanta.py")
vanta = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(vanta)

ASSETS = {"a-repo": {"id": "a-repo", "name": "stack", "assetType": "CODE_REPOSITORY"}}


def finding(id, advisory, ident, fixed):
    """A Dependabot finding as vanta.py fetch normalises it."""
    return vanta.normalise({
        "id": id, "name": advisory, "targetId": "a-repo", "severity": "HIGH", "cvssSeverityScore": 7.5,
        "fixedVersion": fixed, "remediateByDate": "2026-11-05T00:00:00Z", "firstDetectedDate": "2026-10-05T00:00:00Z",
        "packageIdentifier": ident, "externalURL": f"https://github.com/acme/stack/security/dependabot/{id}",
        "relatedUrls": [], "description": "Something is wrong with this package.", "deactivateMetadata": None,
    }, ASSETS, {})


def issue_for(findings, ident="CIP-1"):
    """The issue triage files for these findings, as get_issue returns it."""
    [g] = vanta.group_findings(findings)
    return {"id": ident, "title": g["title"], "status": "Todo", "description": g["description"]}


# ------------------------------------------------------------ the conversion under test

def step1(issue: dict) -> dict:
    """SKILL.md step 1: checks.py --issue on get_issue's saved result."""
    with tempfile.TemporaryDirectory() as d:
        path = Path(d, "issue.json")
        path.write_text(json.dumps(issue))
        proc = subprocess.run([sys.executable, "-I", str(CHECKS), "--issue", str(path)], capture_output=True, text=True)
    assert proc.returncode in (0, 1), (proc.returncode, proc.stderr)
    return json.loads(proc.stdout)


# ------------------------------------------------------------ measurement

def npm_repo(root: Path, version: str) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "package-lock.json").write_text(json.dumps({"lockfileVersion": 3, "packages": {
        "": {"name": "x"}, "node_modules/left-pad": {"version": version}}}))
    return root


def deps(repo: Path, args: list[str], out: Path) -> int:
    proc = subprocess.run([sys.executable, "-I", str(DEPS), str(repo), *args], capture_output=True, text=True)
    out.write_text(proc.stdout)
    return proc.returncode


def already_fixed(issue: dict, locked: str) -> dict:
    """Step 2 on a default branch locking left-pad@<locked>: step 1's checks, deps.py, then gate.py already-fixed.
    An issue step 1 skips never reaches the gate, so it is reported as not passing."""
    checks = step1(issue)
    if checks["status"] != "ok":
        return {"pass": False, "outcome": "skipped", "reasons": checks.get("reasons", [])}
    with tempfile.TemporaryDirectory() as d:
        repo = npm_repo(Path(d, "repo"), locked)
        argv = [sys.executable, "-I", str(GATE), "--claim", "already-fixed", "--ref-kind", "default"]
        for n, args in enumerate(checks["fix_checks"]):
            out = Path(d, f"fix{n}.json")
            argv += ["--fix", str(out), "--fix-exit", str(deps(repo, args, out))]
        if checks["residual_check"] is not None:
            out = Path(d, "residual.json")
            argv += ["--residual", str(out), "--residual-exit", str(deps(repo, checks["residual_check"], out))]
        for ident in checks["unfixed_advisories"]:
            argv += ["--unfixed-advisory", ident]
        proc = subprocess.run(argv, capture_output=True, text=True)
        result = json.loads(proc.stdout)
        result["checks"] = checks
        return result


class Conversion(unittest.TestCase):
    def assertNotCertified(self, result, why):
        self.assertFalse(result["pass"], f"{why}; step 1 produced {json.dumps(result.get('checks'))}")

    def test_j3_fixed_advisory_without_a_range_still_reaches_the_fix_check(self):
        # A: fixed in 1.2.2 for < 1.2.2. B: fixed in 2.1.0, Vanta gave no range (bare package identifier).
        # 2.0.0 is below B's fix on its own major line, so it is still vulnerable to B.
        issue = issue_for([finding("1", "CVE-2026-0001", "npm-left-pad < 1.2.2", "1.2.2"),
                           finding("2", "CVE-2026-0002", "npm-left-pad", "2.1.0")])
        self.assertIn("to 2.1.0 / 1.2.2 (stack)", issue["title"])
        self.assertNotCertified(already_fixed(issue, "2.0.0"), "locked 2.0.0 is below CVE-2026-0002's fix 2.1.0")

    def test_j3_rangeless_advisory_beside_a_ranged_one_on_the_same_line(self):
        # Red under either reading of where SKILL.md's n/a skip applies: the ranged CVE-2026-0004 alone already
        # makes 2.1.0 the highest "Fixed in" on line 2, so the table looks current with CVE-2026-0002's row skipped.
        issue = issue_for([finding("1", "CVE-2026-0001", "npm-left-pad < 1.2.2", "1.2.2"),
                           finding("4", "CVE-2026-0004", "npm-left-pad >= 2.0.5, < 2.1.0", "2.1.0"),
                           finding("2", "CVE-2026-0002", "npm-left-pad", "2.1.0")])
        self.assertNotCertified(already_fixed(issue, "2.0.0"), "locked 2.0.0 is below CVE-2026-0002's fix 2.1.0")

    def test_j3_control_complete_ranges_certify_a_fixed_lockfile(self):
        issue = issue_for([finding("1", "CVE-2026-0001", "npm-left-pad < 1.2.2", "1.2.2"),
                           finding("2", "CVE-2026-0002", "npm-left-pad >= 2.0.0, < 2.1.0", "2.1.0")])
        self.assertTrue(already_fixed(issue, "2.1.0")["pass"])
        self.assertFalse(already_fixed(issue, "2.0.0")["pass"])

    def test_r4a_unfixed_advisory_without_a_range_is_not_dropped(self):
        # A is fixed in 1.2.2; C has no fix and no range. Vanta still reports C against every installed version,
        # so a default branch at 1.2.2 is not "already fixed".
        issue = issue_for([finding("1", "CVE-2026-0001", "npm-left-pad < 1.2.2", "1.2.2"),
                           finding("3", "CVE-2026-0003", "npm-left-pad", None)])
        self.assertIn("CVE-2026-0003", issue["description"])
        self.assertNotCertified(already_fixed(issue, "1.2.2"), "CVE-2026-0003 has no fix and still applies")

    def test_r4b_issue_without_a_generated_section_cannot_certify_already_fixed(self):
        # A legacy issue: no generated section, so the issue does not say which advisories are current
        # (here Vanta's group also holds an unfixed advisory). Its title target alone is not trustworthy evidence.
        issue = {"id": "CIP-1", "title": "[Vanta] Remediate left-pad to 1.2.2 (stack)", "status": "Todo",
                 "description": "**Package:** `left-pad` (npm)\n**Repo:** `acme/stack`\n\nBump it, see Dependabot."}
        self.assertNotCertified(already_fixed(issue, "1.2.2"), "the issue does not list its current advisories")


class ChecksCli(unittest.TestCase):
    PLAIN = [finding("1", "CVE-2026-0001", "npm-left-pad < 1.2.2", "1.2.2")]

    def run_cli(self, data):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d, "issue.json")
            path.write_text(data if isinstance(data, str) else json.dumps(data))
            return subprocess.run([sys.executable, "-I", str(CHECKS), "--issue", str(path)], capture_output=True,
                                  text=True)

    def test_exit_codes(self):
        ok = self.run_cli({"issue": issue_for(self.PLAIN)})
        self.assertEqual(ok.returncode, 0, ok.stdout)
        self.assertEqual(json.loads(ok.stdout)["fix_checks"],
                         [["--ecosystem", "npm", "--package", "left-pad", "--target", "1.2.2", "--affected", "< 1.2.2"]])
        self.assertEqual(self.run_cli("not json").returncode, 2)
        self.assertEqual(self.run_cli({"nothing": 1}).returncode, 2)
        legacy = self.run_cli({"title": "[Vanta] Remediate left-pad to 1.2.2 (stack)", "description": "old"})
        self.assertEqual(legacy.returncode, 1)
        self.assertIn("needs a triage refresh", json.loads(legacy.stdout)["reasons"][0])

    def test_hand_retargeted_title_adds_the_target_only_check(self):
        issue = issue_for(self.PLAIN)
        issue["title"] = "[Vanta] Remediate left-pad to 1.3.0 (stack)"
        out = step1(issue)
        self.assertTrue(out["stale"])
        self.assertIn(["--ecosystem", "npm", "--package", "left-pad", "--target", "1.3.0"], out["fix_checks"])
        self.assertFalse(already_fixed(issue, "1.2.2")["pass"])

    def test_f1_title_retargeted_below_the_block_cannot_certify_a_rangeless_fix(self):
        # The block says CVE-2026-0005 is fixed in 1.2.5 with no affected range; the title was hand-edited down to
        # 1.2.4. The title is not integrity-checked, so a lockfile at 1.2.4 must not pass as already fixed.
        issue = issue_for([finding("5", "CVE-2026-0005", "npm-left-pad", "1.2.5")])
        self.assertIn("to 1.2.5 (stack)", issue["title"])
        issue["title"] = "[Vanta] Remediate left-pad to 1.2.4 (stack)"
        self.assertEqual(step1(issue)["block_targets"], ["1.2.5"])
        result = already_fixed(issue, "1.2.4")
        self.assertFalse(result["pass"], f"locked 1.2.4 is below the block's fix 1.2.5; step 1 produced "
                                         f"{json.dumps(result['checks']['fix_checks'])}")

    def test_unfixed_rangeless_advisory_is_named_on_a_pr(self):
        issue = issue_for(self.PLAIN + [finding("3", "CVE-2026-0003", "npm-left-pad", None)])
        out = step1(issue)
        self.assertEqual(out["unfixed_advisories"], ["CVE-2026-0003"])
        with tempfile.TemporaryDirectory() as d:
            repo = npm_repo(Path(d, "repo"), "1.2.2")
            self.assertEqual(deps(repo, out["residual_check"], Path(d, "r.json")), 1)

    def test_track_upstream_and_asset_issues_are_skipped(self):
        upstream = issue_for([finding("3", "CVE-2026-0003", "npm-left-pad < 2.0.0", None)])
        self.assertEqual(step1(upstream)["status"], "skip")
        asset = vanta.normalise({"id": "9", "name": "CVE-9", "targetId": "x", "severity": "HIGH", "fixedVersion": "1.2.2",
                                 "packageIdentifier": "npm-left-pad < 1.2.2", "externalURL": None}, {}, {})
        [g] = vanta.group_findings([asset])
        out = step1({"title": g["title"], "description": g["description"]})
        self.assertEqual(out["status"], "skip")
        self.assertIn("asset", out["reasons"][0])


IMAGE_ASSETS = {"a-cts": {"id": "a-cts", "name": "cts", "assetType": "CONTAINER_REPOSITORY"},
                "a-zerokms": {"id": "a-zerokms", "name": "zerokms", "assetType": "CONTAINER_REPOSITORY"}}
IMAGE_CONFIG = {"images": {"cts": {"repo": "acme/suite"}, "zerokms": {"repo": "acme/suite"}}}


def container_finding(id, advisory, image):
    """An Inspector finding on an ECR image as vanta.py fetch normalises it."""
    return vanta.normalise({
        "id": id, "name": advisory, "targetId": image, "severity": "HIGH", "cvssSeverityScore": 7.5,
        "fixedVersion": "NotAvailable", "remediateByDate": "2026-11-05T00:00:00Z",
        "firstDetectedDate": "2026-10-05T00:00:00Z", "packageIdentifier": "cyrus-sasl2:2.1.28",
        "externalURL": f"https://aws/inspector/{id}", "relatedUrls": [], "description": "Something is wrong.",
        "deactivateMetadata": None}, IMAGE_ASSETS, IMAGE_CONFIG)


def container_gate(issue: dict, determinations: dict, diff_files: list[str]) -> dict:
    """SKILL.md step 1 then references/containers.md's evidence gate, as documented, on the agent's determinations."""
    checks = step1(issue)
    with tempfile.TemporaryDirectory() as d:
        path, checks_path = Path(d, "determinations.json"), Path(d, "checks.json")
        path.write_text(json.dumps(determinations))
        checks_path.write_text(json.dumps(checks))
        proc = subprocess.run([sys.executable, "-I", str(GATE), "--claim", "container", "--ref-kind", "fix-branch",
                               "--determinations", str(path), "--checks", str(checks_path),
                               "--diff-files", *diff_files],
                              capture_output=True, text=True)
    result = json.loads(proc.stdout)
    result["checks"] = checks
    return result


class ContainerGate(unittest.TestCase):
    def test_f4_determinations_that_omit_an_image_and_an_advisory_cannot_reach_in_review(self):
        issue = issue_for([container_finding("1", "CVE-2026-0001", "a-zerokms"),
                           container_finding("2", "CVE-2026-0002", "a-zerokms"),
                           container_finding("3", "CVE-2026-0001", "a-cts"),
                           container_finding("4", "CVE-2026-0002", "a-cts")])
        checks = step1(issue)
        self.assertEqual(checks["kind"], "container")
        self.assertEqual(sorted(checks["images"]), ["cts", "zerokms"])
        self.assertEqual(sorted(a["id"] for a in checks["advisories"]), ["CVE-2026-0001", "CVE-2026-0002"])
        # The agent leaves cts and CVE-2026-0002 out of its determinations: cts was never rebuilt and
        # CVE-2026-0002 was never assessed, so the issue must not move to In Review.
        result = container_gate(issue, {"images": ["zerokms"], "advisories": [
            {"id": "CVE-2026-0001", "status": "fixed", "source": "https://security-tracker.debian.org/x",
             "verified_images": ["zerokms"]}]}, ["Dockerfile"])
        self.assertNotEqual(result["outcome"], "pr-in-review", result["reasons"])
        self.assertFalse(result["pass"])

if __name__ == "__main__":
    unittest.main()
