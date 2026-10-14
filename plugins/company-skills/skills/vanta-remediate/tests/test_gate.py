"""Tests for scripts/gate.py, fed real deps.py output from fixture repos.

Run: python3 -m unittest discover -s tests -p 'test_gate.py' (from the skill directory)."""

import contextlib
import io
import itertools
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
GATE, DEPS = SCRIPTS / "gate.py", SCRIPTS / "deps.py"
sys.path.insert(0, str(SCRIPTS))
import gate  # noqa: E402


def lock(version):
    body = {"name": "x"} if version is None else {"version": version}
    return json.dumps({"lockfileVersion": 3, "packages": {"": {"name": "x"}, "node_modules/lodash": body}})


# name: (files, expected deps.py exit, has unsupported)
FIXTURES = {
    "clean": ({"package-lock.json": lock("4.17.21")}, 0, False),
    "clean_bun": ({"package-lock.json": lock("4.17.21"), "bun.lockb": "bin"}, 0, True),
    "bun_only": ({"bun.lockb": "bin"}, 0, True),
    "vuln": ({"package-lock.json": lock("4.17.20")}, 1, False),
    "vuln_bun": ({"package-lock.json": lock("4.17.20"), "bun.lockb": "bin"}, 1, True),
    "unreadable": ({"package-lock.json": "not json"}, 2, True),
    "no_version": ({"package-lock.json": lock(None)}, 2, True),
}


class GateCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        cls.out = {}
        for name, (files, want, unsupported) in FIXTURES.items():
            repo = cls.tmp / name
            repo.mkdir()
            for fname, text in files.items():
                (repo / fname).write_text(text)
            proc = subprocess.run([sys.executable, "-I", str(DEPS), str(repo), "--ecosystem", "npm",
                                   "--package", "lodash", "--target", "4.17.21", "--affected", "< 4.17.21"],
                                  capture_output=True, text=True)
            path = cls.tmp / f"{name}.json"
            path.write_text(proc.stdout)
            data = json.loads(proc.stdout)
            assert proc.returncode == want, (name, proc.returncode, proc.stderr)
            assert bool(data["unsupported"]) == unsupported, (name, data["unsupported"])
            cls.out[name] = (str(path), proc.returncode)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def gate(self, *args):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = gate.main(list(args))
        result = json.loads(buf.getvalue())
        self.assertEqual(code, 0 if result["pass"] else 1)
        return result

    def deps_args(self, flag, name):
        path, code = self.out[name]
        return [f"--{flag}", path, f"--{flag}-exit", str(code)]


CLAIMS = ("already-fixed", "linked", "opened")
REFS = ("default", "merge", "head", "fix-branch")
PAIRS = {"already-fixed": {"default"}, "linked": {"merge", "head"}, "opened": {"fix-branch"}}
FIX = {(0, False): "clean", (0, True): "clean_bun", (1, False): "vuln", (1, True): "vuln_bun", (2, True): "unreadable"}
RESIDUAL = {None: None, 0: "clean", 1: "vuln", 2: "unreadable"}
SCOPES = {"absent": [], "ok": ["--scope-ok"], "bad": ["--scope-bad"],
          "manifests": ["--diff-files", "package.json", "web/package-lock.json"],
          "source": ["--diff-files", "package-lock.json", "src/index.js"],
          "dockerfile": ["--diff-files", "Dockerfile"], "empty": ["--diff-files"]}
BASES = {"match": ["--pr-base", "main", "--default-branch", "main"],
         "mismatch": ["--pr-base", "release/1.x", "--default-branch", "main"], "absent": []}


def expected(claim, ref, fix, unsupported, residual, scope, base):
    """The allowed set, stated independently of gate.py."""
    scope_bad = scope in ("bad", "source", "dockerfile")
    passed = (ref in PAIRS[claim] and fix == 0 and not unsupported and residual != 2
              and not (claim == "already-fixed" and residual == 1) and not scope_bad
              and not (claim == "opened" and scope in ("absent", "empty"))
              and not (claim == "linked" and base != "match"))
    if passed:
        outcome = claim
    elif claim == "linked":
        outcome = "not-linked"
    elif (claim == "already-fixed" and ref == "default" and fix == 1 and not unsupported and residual != 2
          and not scope_bad):
        outcome = "patch"
    else:
        outcome = "blocked"
    return passed, outcome


class TestGateProperty(GateCase):
    def test_no_combination_outside_the_allowed_set_passes(self):
        fixes = [None, *FIX]
        checked = 0
        for claim, ref, fix_key, residual, scope, base in itertools.product(
                CLAIMS, REFS, fixes, RESIDUAL, SCOPES, BASES):
            args = ["--claim", claim, "--ref-kind", ref, *SCOPES[scope], *BASES[base]]
            if fix_key is not None:
                args += self.deps_args("fix", FIX[fix_key])
            if residual is not None:
                args += self.deps_args("residual", RESIDUAL[residual]) + ["--unfixed-advisory", "GHSA-none"]
            fix, unsupported = fix_key if fix_key else ("missing", False)
            want_pass, want_outcome = expected(claim, ref, fix, unsupported, residual, scope, base)
            with self.subTest(claim=claim, ref=ref, fix=fix_key, residual=residual, scope=scope, base=base):
                result = self.gate(*args)
                self.assertEqual(result["pass"], want_pass, result["reasons"])
                self.assertEqual(result["outcome"], want_outcome, result["reasons"])
                self.assertEqual(bool(result["must_name_unfixed"]), want_pass and residual == 1)
                if result["pass"]:
                    self.assertEqual(result["reasons"], [])
                else:
                    self.assertTrue(result["reasons"])
            checked += 1
        self.assertEqual(checked, 3 * 4 * 6 * 4 * 7 * 3)


class TestGateEntries(GateCase):
    def test_r3f_unsupported_lockfile_never_already_fixed(self):
        result = self.gate("--claim", "already-fixed", "--ref-kind", "default", *self.deps_args("fix", "bun_only"))
        self.assertEqual(result["outcome"], "blocked")
        self.assertIn("bun.lockb", result["reasons"][0])

    def test_r3f_package_without_version_blocks(self):
        result = self.gate("--claim", "already-fixed", "--ref-kind", "default", *self.deps_args("fix", "no_version"))
        self.assertEqual(result["outcome"], "blocked")
        self.assertTrue(any("no version" in r for r in result["reasons"]), result["reasons"])

    def test_r3f_pr_head_exit_2_is_not_linked(self):
        result = self.gate("--claim", "linked", "--ref-kind", "merge", *self.deps_args("fix", "unreadable"),
                           *BASES["match"])
        self.assertEqual(result["outcome"], "not-linked")

    def test_r3f_residual_exit_2_blocks_every_claim(self):
        for claim, ref in (("already-fixed", "default"), ("linked", "merge"), ("opened", "fix-branch")):
            result = self.gate("--claim", claim, "--ref-kind", ref, *self.deps_args("fix", "clean"),
                               *self.deps_args("residual", "unreadable"), "--unfixed-advisory", "GHSA-none",
                               "--scope-ok", *BASES["match"])
            self.assertFalse(result["pass"], claim)

    def test_residual_missing_when_unfixed_advisories_exist_fails(self):
        result = self.gate("--claim", "already-fixed", "--ref-kind", "default", *self.deps_args("fix", "clean"),
                           "--unfixed-advisory", "GHSA-none")
        self.assertEqual(result["outcome"], "blocked")
        self.assertIn("residual check: missing", result["reasons"][0])

    def test_r3i_residual_exit_1_allows_pr_but_names_every_unfixed_advisory(self):
        result = self.gate("--claim", "opened", "--ref-kind", "fix-branch", *self.deps_args("fix", "clean"),
                           *self.deps_args("residual", "vuln"), "--unfixed-advisory", "GHSA-a",
                           "--unfixed-advisory", "GHSA-b", "--diff-files", "package-lock.json")
        self.assertTrue(result["pass"])
        self.assertEqual(result["must_name_unfixed"], ["GHSA-a", "GHSA-b"])

    def test_r3i_residual_exit_1_never_allows_done(self):
        result = self.gate("--claim", "already-fixed", "--ref-kind", "default", *self.deps_args("fix", "clean"),
                           *self.deps_args("residual", "vuln"), "--unfixed-advisory", "GHSA-a")
        self.assertEqual(result["outcome"], "blocked")

    def test_r3e_pr_into_another_branch_is_not_linked(self):
        result = self.gate("--claim", "linked", "--ref-kind", "merge", *self.deps_args("fix", "clean"),
                           *BASES["mismatch"])
        self.assertEqual(result["outcome"], "not-linked")
        self.assertIn("release/1.x", result["reasons"][0])

    def test_r3m_head_fallback_is_noted(self):
        result = self.gate("--claim", "linked", "--ref-kind", "head", *self.deps_args("fix", "clean"),
                           *BASES["match"])
        self.assertTrue(result["pass"])
        self.assertIn("merge ref", result["notes"][0])

    def test_r3d_source_change_on_resumed_branch_blocks(self):
        result = self.gate("--claim", "opened", "--ref-kind", "fix-branch", *self.deps_args("fix", "clean"),
                           "--diff-files", "Cargo.lock", "src/lib.rs")
        self.assertEqual(result["outcome"], "blocked")
        self.assertIn("src/lib.rs", result["reasons"][0])

    def test_exit_code_that_contradicts_the_json_fails(self):
        path, _ = self.out["vuln"]
        result = self.gate("--claim", "already-fixed", "--ref-kind", "default", "--fix", path, "--fix-exit", "0")
        self.assertFalse(result["pass"])

    def test_unreadable_evidence_file_fails(self):
        result = self.gate("--claim", "already-fixed", "--ref-kind", "default",
                           "--fix", str(self.tmp / "missing.json"), "--fix-exit", "0")
        self.assertEqual(result["outcome"], "blocked")

    def test_wrong_ref_for_already_fixed_fails(self):
        # A resumed fix branch is never evidence that the default branch is fixed.
        result = self.gate("--claim", "already-fixed", "--ref-kind", "fix-branch", *self.deps_args("fix", "clean"))
        self.assertEqual(result["outcome"], "blocked")


class TestGateCli(GateCase):
    def test_cli_exit_codes(self):
        path, code = self.out["clean"]
        ok = subprocess.run([sys.executable, "-I", str(GATE), "--claim", "already-fixed", "--ref-kind", "default",
                             "--fix", path, "--fix-exit", str(code)], capture_output=True, text=True)
        self.assertEqual(ok.returncode, 0, ok.stderr)
        self.assertTrue(json.loads(ok.stdout)["pass"])
        usage = subprocess.run([sys.executable, "-I", str(GATE), "--claim", "done"], capture_output=True, text=True)
        self.assertEqual(usage.returncode, 2)


class TestContainerGate(GateCase):
    def container(self, determinations, *diff):
        path = self.tmp / "determinations.json"
        path.write_text(json.dumps(determinations))
        return self.gate("--claim", "container", "--ref-kind", "fix-branch", "--determinations", str(path), *diff)

    @staticmethod
    def adv(ident, status, verified=("zerokms", "cts"), source="https://security-tracker.debian.org/x"):
        return {"id": ident, "status": status, "source": source, "verified_images": list(verified)}

    def test_r3k_mixed_advisories_stay_in_todo(self):
        result = self.container({"images": ["zerokms", "cts"], "advisories": [
            self.adv("CVE-1", "fixed"), self.adv("CVE-2", "not-affected", ()), self.adv("CVE-3", "unfixed", ())]},
            "--diff-files", "Dockerfile")
        self.assertEqual(result["outcome"], "pr-todo")
        self.assertEqual(result["must_name_unfixed"], ["CVE-2", "CVE-3"])

    def test_r3k_fix_verified_in_one_image_only_is_a_draft(self):
        result = self.container({"images": ["zerokms", "cts"], "advisories": [self.adv("CVE-1", "fixed", ["zerokms"])]},
                                "--diff-files", "Dockerfile")
        self.assertEqual(result["outcome"], "draft-todo")
        self.assertFalse(result["pass"])

    def test_r3k_every_advisory_cleared_and_verified_moves_to_in_review(self):
        result = self.container({"images": ["zerokms", "cts"], "advisories": [
            self.adv("CVE-1", "fixed"), self.adv("CVE-2", "removed")]}, "--diff-files", "deploy/Dockerfile")
        self.assertTrue(result["pass"])
        self.assertEqual(result["outcome"], "pr-in-review")

    def test_container_claim_without_source_or_with_other_files_blocks(self):
        no_source = self.container({"images": ["zerokms"], "advisories": [self.adv("CVE-1", "fixed", source="")]},
                                   "--diff-files", "Dockerfile")
        self.assertEqual(no_source["outcome"], "blocked")
        other = self.container({"images": ["zerokms"], "advisories": [self.adv("CVE-1", "fixed", ["zerokms"])]},
                               "--diff-files", "Dockerfile", "package-lock.json")
        self.assertEqual(other["outcome"], "blocked")
        no_diff = self.container({"images": ["zerokms"], "advisories": [self.adv("CVE-1", "fixed", ["zerokms"])]})
        self.assertEqual(no_diff["outcome"], "blocked")

    def test_container_with_nothing_fixed_is_comment_only(self):
        result = self.container({"images": ["zerokms"], "advisories": [self.adv("CVE-1", "staged", ())]})
        self.assertEqual(result["outcome"], "comment-only")


if __name__ == "__main__":
    unittest.main()
