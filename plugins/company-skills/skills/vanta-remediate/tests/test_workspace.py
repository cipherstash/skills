"""Tests for scripts/workspace.py against real throwaway git repos.

Run: python3 -m unittest discover -s tests -p 'test_workspace.py' (from the skill directory)."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "workspace.py"
GIT = ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "init.defaultBranch=main",
       "-c", "commit.gpgsign=false", "-c", "core.hooksPath=/dev/null"]
BRANCH = "fix/cip-1-lodash"


def git(cwd, *args):
    return subprocess.run([*GIT, "-C", str(cwd), *args], check=True, capture_output=True, text=True).stdout.strip()


class Repo:
    """A bare origin, a clone of it, and helpers to put either into a starting state."""

    def __init__(self, root: Path):
        self.root = root
        self.origin = root / "origin.git"
        self.clone = root / "clone"
        self.path = root / "clone-cip-1"
        subprocess.run([*GIT, "init", "-q", "--bare", str(self.origin)], check=True)
        subprocess.run([*GIT, "clone", "-q", str(self.origin), str(self.clone)], check=True, capture_output=True)
        (self.clone / "package-lock.json").write_text("{}\n")
        (self.clone / ".gitignore").write_text("*.env\n")
        git(self.clone, "add", ".")
        git(self.clone, "commit", "-qm", "init")
        git(self.clone, "push", "-q", "origin", "HEAD:main")
        git(self.clone, "fetch", "-q", "origin")

    def commit_on(self, branch, filename, text, push=False, base="origin/main"):
        """Commit on `branch` in a scratch worktree, then remove that worktree."""
        tmp = self.root / f"wt-{abs(hash((branch, filename, text)))}"
        exists = git(self.clone, "branch", "--list", branch)
        if exists:
            git(self.clone, "worktree", "add", "-q", str(tmp), branch)
        else:
            git(self.clone, "worktree", "add", "-q", "-b", branch, str(tmp), base)
        (tmp / filename).write_text(text)
        git(tmp, "add", filename)
        git(tmp, "commit", "-qm", f"{filename}: {text.strip()}")
        if push:
            git(tmp, "push", "-q", "origin", f"HEAD:{branch}")
            git(self.clone, "fetch", "-q", "origin")
        git(self.clone, "worktree", "remove", "--force", str(tmp))
        return git(self.clone, "rev-parse", branch)

    def run(self, *extra, branch=BRANCH, prs=None, path=None):
        args = [sys.executable, "-I", str(SCRIPT), "--clone", str(self.clone), "--path", str(path or self.path)]
        if branch:
            args += ["--branch", branch, "--default", "main"]
        if prs is not None:
            pr_file = self.root / "prs.json"
            pr_file.write_text(json.dumps(prs))
            args += ["--pr-json", str(pr_file)]
        proc = subprocess.run([*args, *extra], capture_output=True, text=True)
        out = json.loads(proc.stdout) if proc.stdout.strip() else None
        return proc.returncode, out, proc.stderr

    def snapshot(self):
        """Every commit reachable from any ref, and every file under every worktree."""
        reachable = set(git(self.clone, "rev-list", "--all").split())
        files = {}
        for p in self.root.rglob("*"):
            if {".git", "origin.git"} & set(p.parts) or p.is_dir() or p.name == "prs.json":
                continue
            files[str(p)] = p.read_bytes()
        return reachable, files


class WorkspaceCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.repo = Repo(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def assert_nothing_lost(self, before):
        """No commit becomes unreachable and no pre-existing file changes."""
        reach_before, files_before = before
        reach_after, files_after = self.repo.snapshot()
        self.assertTrue(reach_before <= reach_after, "a commit became unreachable")
        for path, data in files_before.items():
            self.assertEqual(files_after.get(path), data, f"{path} was changed or deleted")

    def inspect_then_create(self, expect_action, prs=None, branch=BRANCH):
        before = self.repo.snapshot()
        code, out, err = self.repo.run(branch=branch, prs=prs)
        self.assertEqual(out["action"], expect_action, (out, err))
        self.assertEqual(code, 1 if expect_action == "blocked" else 0)
        code, created, err = self.repo.run("--create", "--run-id", "r1", branch=branch, prs=prs)
        self.assertEqual(created["action"], expect_action, err)
        self.assert_nothing_lost(before)
        if expect_action == "blocked":
            self.assertNotIn("created", created)
        else:
            self.assertEqual(created["created"], os.path.abspath(self.repo.path))
        return out


class TestStartingStates(WorkspaceCase):
    def test_fresh_issue_creates_from_default(self):
        out = self.inspect_then_create("create")
        self.assertEqual(out["base"], "origin/main")

    def test_leftover_clean_worktree_blocks(self):
        # R3c: a clean leftover still blocks; the run cannot tell a dry run from a human's.
        self.repo.run("--create", "--run-id", "dry")
        out = self.inspect_then_create("blocked")
        self.assertTrue(out["evidence"]["leftover"]["registered"])
        self.assertTrue(self.repo.path.is_dir())

    def test_leftover_with_ignored_file_only_blocks_and_keeps_it(self):
        # R3c: `status --porcelain` hides ignored files and `worktree remove` would delete them.
        self.repo.run("--create", "--run-id", "dry")
        (self.repo.path / ".env").write_text("SECRET=1\n")
        out = self.inspect_then_create("blocked")
        self.assertIn("!! .env", out["evidence"]["leftover"]["status"])
        self.assertEqual((self.repo.path / ".env").read_text(), "SECRET=1\n")

    def test_leftover_dirty_worktree_blocks(self):
        self.repo.run("--create", "--run-id", "dry")
        (self.repo.path / "package-lock.json").write_text('{"patched": true}\n')
        out = self.inspect_then_create("blocked")
        self.assertIn(" M package-lock.json", out["evidence"]["leftover"]["status"])

    def test_unregistered_directory_at_path_blocks(self):
        self.repo.path.mkdir()
        (self.repo.path / "notes.txt").write_text("mine\n")
        out = self.inspect_then_create("blocked")
        self.assertFalse(out["evidence"]["leftover"]["registered"])

    def test_local_branch_with_human_commit_blocks(self):
        # R3b: `worktree add -B` would silently reset this branch.
        sha = self.repo.commit_on(BRANCH, "notes.txt", "human\n")
        out = self.inspect_then_create("blocked")
        self.assertEqual(len(out["evidence"]["local_commits_beyond_base"]), 1)
        self.assertEqual(git(self.repo.clone, "rev-parse", BRANCH), sha)

    def test_local_branch_with_no_extra_commits_is_reused(self):
        git(self.repo.clone, "branch", BRANCH, "origin/main")
        self.inspect_then_create("create")

    def test_branch_checked_out_elsewhere_blocks(self):
        other = self.tmp / "elsewhere"
        git(self.repo.clone, "worktree", "add", "-q", "-b", BRANCH, str(other), "origin/main")
        out = self.inspect_then_create("blocked")
        self.assertIn("checked_out_in", out["evidence"])

    def test_remote_branch_without_pr_resumes(self):
        self.repo.commit_on(BRANCH, "package-lock.json", '{"v": 2}\n', push=True)
        git(self.repo.clone, "branch", "-D", BRANCH)
        out = self.inspect_then_create("resume", prs=[])
        self.assertEqual(out["base"], f"origin/{BRANCH}")
        self.assertIsNone(out["pr"])

    def test_remote_branch_with_human_commit_resumes_with_evidence(self):
        # R3d: resumed on top of the human's commit; gate.py's scope check judges what it changed.
        self.repo.commit_on(BRANCH, "package-lock.json", '{"v": 2}\n', push=True)
        self.repo.commit_on(BRANCH, "lib.rs", "human\n", push=True)
        git(self.repo.clone, "branch", "-D", BRANCH)
        human = git(self.repo.clone, "rev-parse", f"origin/{BRANCH}")
        out = self.inspect_then_create("resume")
        self.assertEqual(len(out["evidence"]["remote_commits_beyond_default"]), 2)
        self.assertEqual(git(self.repo.path, "rev-parse", "HEAD"), human)

    def test_own_open_pr_resumes_and_names_it(self):
        # R3a: the incomplete own PR is updated, never duplicated.
        self.repo.commit_on(BRANCH, "package-lock.json", '{"v": 2}\n', push=True)
        git(self.repo.clone, "branch", "-D", BRANCH)
        out = self.inspect_then_create("resume", prs=[{"number": 40, "state": "open", "merged_at": None}])
        self.assertEqual(out["pr"], 40)
        self.assertEqual(out["base"], f"origin/{BRANCH}")

    def test_closed_unmerged_pr_blocks(self):
        self.repo.commit_on(BRANCH, "package-lock.json", '{"v": 2}\n', push=True)
        git(self.repo.clone, "branch", "-D", BRANCH)
        out = self.inspect_then_create("blocked", prs=[{"number": 41, "state": "closed", "merged_at": None}])
        self.assertIn("rejected", out["reasons"][0])

    def test_closed_unmerged_pr_with_branch_deleted_blocks(self):
        self.inspect_then_create("blocked", prs=[{"number": 41, "state": "closed", "merged_at": None}])

    def test_squash_merged_pr_with_remote_branch_left_blocks(self):
        self.repo.commit_on(BRANCH, "package-lock.json", '{"v": 2}\n', push=True)
        git(self.repo.clone, "branch", "-D", BRANCH)
        self.inspect_then_create("blocked", prs=[{"number": 42, "state": "closed", "merged_at": "2026-01-01"}])

    def test_remote_branch_already_in_default_creates(self):
        git(self.repo.clone, "push", "-q", "origin", f"origin/main:refs/heads/{BRANCH}")
        git(self.repo.clone, "fetch", "-q", "origin")
        out = self.inspect_then_create("create", prs=[{"number": 43, "state": "closed", "merged_at": "2026-01-01"}])
        self.assertEqual(out["base"], "origin/main")

    def test_closed_unmerged_pr_with_remote_branch_in_default_blocks(self):
        # A rejected PR blocks even when its branch holds nothing beyond the default branch.
        git(self.repo.clone, "push", "-q", "origin", f"origin/main:refs/heads/{BRANCH}")
        git(self.repo.clone, "fetch", "-q", "origin")
        out = self.inspect_then_create("blocked", prs=[{"number": 45, "state": "closed", "merged_at": None}])
        self.assertIn("rejected", out["reasons"][0])

    def test_mixed_case_package_slug_is_accepted(self):
        # SKILL.md step 4 keeps the package name's case: PyPI Jinja2, PyYAML, Go BurntSushi.
        for branch in ("fix/cip-1-Jinja2", "fix/vanta-PyYAML", "fix/cip-1-github.com-BurntSushi-toml"):
            with self.subTest(branch=branch):
                code, out, err = self.repo.run(branch=branch)
                self.assertEqual(code, 0, err)
                self.assertEqual(out["action"], "create")

    def test_human_branch_name_is_never_adopted(self):
        # R3l: a no-id request uses fix/vanta-<slug>; a human's fix/lodash is left alone.
        human = self.repo.commit_on("fix/lodash", "lib.rs", "human\n", push=True)
        out = self.inspect_then_create("create", branch="fix/vanta-lodash")
        self.assertEqual(out["base"], "origin/main")
        self.assertEqual(git(self.repo.clone, "rev-parse", "origin/fix/lodash"), human)
        code, _, err = self.repo.run(branch="fix/lodash")
        self.assertEqual(code, 2)
        self.assertIn("fix/vanta-", err)

    def test_open_pr_without_remote_branch_blocks(self):
        self.inspect_then_create("blocked", prs=[{"number": 44, "state": "open", "merged_at": None}])


class TestCleanup(WorkspaceCase):
    def test_markerless_worktree_is_never_removed(self):
        git(self.repo.clone, "worktree", "add", "-q", "-b", BRANCH, str(self.repo.path), "origin/main")
        (self.repo.path / "notes.txt").write_text("mine\n")
        code, out, _ = self.repo.run("--cleanup", "--run-id", "r1", branch=None)
        self.assertEqual(code, 1)
        self.assertFalse(out["removed"])
        self.assertTrue((self.repo.path / "notes.txt").exists())

    def test_other_runs_worktree_is_never_removed(self):
        self.repo.run("--create", "--run-id", "earlier")
        code, out, _ = self.repo.run("--cleanup", "--run-id", "r1", branch=None)
        self.assertEqual(code, 1)
        self.assertIn("another run", out["reasons"][0])
        self.assertTrue(self.repo.path.is_dir())

    def test_unregistered_directory_is_never_removed(self):
        self.repo.path.mkdir()
        code, out, _ = self.repo.run("--cleanup", "--run-id", "r1", branch=None)
        self.assertEqual(code, 1)
        self.assertTrue(self.repo.path.is_dir())

    def test_own_worktree_is_removed_and_unpushed_empty_branch_deleted(self):
        self.repo.run("--create", "--run-id", "r1")
        (self.repo.path / "package-lock.json").write_text('{"patched": true}\n')
        code, out, _ = self.repo.run("--cleanup", "--run-id", "r1", branch=None)
        self.assertEqual(code, 0, out)
        self.assertTrue(out["removed"] and out["branch_deleted"])
        self.assertFalse(self.repo.path.exists())

    def test_own_worktree_branch_with_commit_is_kept(self):
        self.repo.run("--create", "--run-id", "r1")
        (self.repo.path / "package-lock.json").write_text('{"patched": true}\n')
        git(self.repo.path, "commit", "-qam", "patch")
        sha = git(self.repo.clone, "rev-parse", BRANCH)
        code, out, _ = self.repo.run("--cleanup", "--run-id", "r1", branch=None)
        self.assertTrue(out["removed"])
        self.assertFalse(out["branch_deleted"])
        self.assertEqual(git(self.repo.clone, "rev-parse", BRANCH), sha)

    def test_own_worktree_pushed_branch_is_kept(self):
        self.repo.run("--create", "--run-id", "r1")
        git(self.repo.path, "push", "-q", "origin", f"HEAD:{BRANCH}")
        git(self.repo.clone, "fetch", "-q", "origin")
        code, out, _ = self.repo.run("--cleanup", "--run-id", "r1", branch=None)
        self.assertTrue(out["removed"])
        self.assertFalse(out["branch_deleted"])

    def test_detached_measurement_worktree_round_trip(self):
        scratch = self.tmp / "measure"
        args = ["--detach", "origin/main", "--create", "--run-id", "r1"]
        code, out, err = self.repo.run(*args, branch=None, path=scratch)
        self.assertEqual(code, 0, err)
        code, out, _ = self.repo.run("--cleanup", "--run-id", "r1", branch=None, path=scratch)
        self.assertTrue(out["removed"])
        self.assertFalse(scratch.exists())


if __name__ == "__main__":
    unittest.main()
