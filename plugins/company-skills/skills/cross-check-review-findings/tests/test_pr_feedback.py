"""Tests for scripts/pr_feedback.py against a fake `gh` on PATH.

Run: python3 -m unittest discover -s <skill>/tests
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "pr_feedback.py"

FAKE_GH = textwrap.dedent(
    r'''
    #!/usr/bin/env python3
    import json, os, sys
    args = sys.argv[1:]
    with open(os.environ["FAKE_GH_LOG"], "a") as log:
        log.write(json.dumps(args) + "\n")
    if os.environ.get("FAKE_GH_FAIL"):
        sys.stderr.write("HTTP 404: Not Found\n")
        sys.exit(1)
    if args[:2] == ["pr", "view"]:
        print(json.dumps({"number": 7, "url": os.environ["FAKE_GH_URL"], "title": "T",
                          "author": None, "state": "OPEN", "isDraft": False,
                          "headRefName": "feat", "headRefOid": "abc123", "baseRefName": "main"}))
        sys.exit(0)
    query = next(a[6:] for a in args if a.startswith("query="))
    cursor = next((a[7:] for a in args if a.startswith("cursor=")), None)
    def page(conn, nodes, nxt=None):
        return {"data": {"repository": {"pullRequest": {conn: {
            "pageInfo": {"hasNextPage": nxt is not None, "endCursor": nxt}, "nodes": nodes}}}}}
    def c(i, login="alice"):
        return {"databaseId": i, "author": {"login": login} if login else None, "body": f"c{i}",
                "url": f"u{i}", "createdAt": "2026-01-01T00:00:00Z", "isMinimized": False}
    def t(i, total=1):
        return {"id": f"T{i}", "path": "a.py", "line": i, "originalLine": i, "startLine": None,
                "diffSide": "RIGHT", "subjectType": "LINE",
                "isResolved": i == 2, "isOutdated": False,
                "resolvedBy": {"login": "bob"} if i == 2 else None,
                "comments": {"totalCount": total, "nodes": [{**c(i), "originalCommit": {"oid": f"orig{i}"}, "diffHunk": "@@ -1 +1 @@",
                                                    "pullRequestReview": {"state": "PENDING" if i == 3 else "COMMENTED"}}]}}
    if "reviewThreads(" in query:
        out = page("reviewThreads", [t(1, total=3)], "CUR1") if cursor is None else page("reviewThreads", [t(2), t(3)])
    elif "reviews(" in query:
        out = page("reviews", [
            {"databaseId": 10, "author": {"login": "coderabbitai"}, "state": "COMMENTED", "body": "Nitpicks",
             "url": "r10", "submittedAt": "2026-01-01T00:00:00Z", "isMinimized": False, "commit": {"oid": "abc123"}},
            {"databaseId": 11, "author": {"login": "bob"}, "state": "APPROVED", "body": "  ",
             "url": "r11", "submittedAt": "2026-01-01T00:00:00Z", "isMinimized": False, "commit": None},
            {"databaseId": 12, "author": {"login": "me"}, "state": "PENDING", "body": "draft",
             "url": "r12", "submittedAt": None, "isMinimized": False, "commit": None}])
    else:
        out = page("comments", [c(20, login=None)])
    print(json.dumps(out))
    '''
).lstrip()


class PrFeedbackTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        bin_dir = Path(self.tmp.name)
        gh = bin_dir / "gh"
        gh.write_text(FAKE_GH)
        gh.chmod(0o755)
        self.log = bin_dir / "log"
        self.env = {**os.environ, "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
                    "FAKE_GH_LOG": str(self.log), "FAKE_GH_URL": "https://github.com/o/r/pull/7"}

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def run_script(self, *args: str, **env: str) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, "-I", str(SCRIPT), *args], capture_output=True,
                              text=True, env={**self.env, **env})

    def calls(self) -> list[list[str]]:
        return [json.loads(line) for line in self.log.read_text().splitlines()]

    def test_collates_all_feedback(self) -> None:
        result = self.run_script("7")
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data["pr"]["headRefOid"], "abc123")
        self.assertEqual(data["pr"]["author"], "ghost")
        self.assertEqual([t["id"] for t in data["threads"]], ["T1", "T2"])
        first, second = data["threads"]
        self.assertTrue(first["truncated"])
        self.assertEqual(first["originalCommit"], "orig1")
        self.assertEqual((first["side"], first["subject"], first["diffHunk"]), ("RIGHT", "LINE", "@@ -1 +1 @@"))
        self.assertEqual((first["resolved"], first["resolvedBy"]), (False, None))
        self.assertEqual((second["resolved"], second["resolvedBy"]), (True, "bob"))
        self.assertEqual(first["comments"][0]["id"], 1)
        self.assertEqual([r["id"] for r in data["reviews"]], [10])
        self.assertTrue(data["pendingReview"])
        self.assertEqual(data["reviews"][0]["commit"], "abc123")
        self.assertEqual(data["comments"][0]["author"], "ghost")

    def test_passes_owner_and_name_as_strings_and_follows_cursor(self) -> None:
        self.run_script("https://github.com/o/r/pull/7")
        graphql = [c for c in self.calls() if c[:2] == ["api", "graphql"]]
        self.assertTrue(all("-F" in c and "number=7" in c and "owner=o" in c for c in graphql))
        self.assertTrue(all(c[c.index("owner=o") - 1] == "-f" for c in graphql))
        self.assertTrue(any("cursor=CUR1" in c for c in graphql))
        self.assertFalse(any("--hostname" in c for c in graphql))

    def test_enterprise_host_passes_hostname(self) -> None:
        result = self.run_script("7", FAKE_GH_URL="https://git.example.com/o/r/pull/7")
        self.assertEqual(result.returncode, 0, result.stderr)
        graphql = [c for c in self.calls() if c[:2] == ["api", "graphql"]]
        self.assertTrue(all(c[c.index("--hostname") + 1] == "git.example.com" for c in graphql))

    def test_gh_failure_exits_1_with_message(self) -> None:
        result = self.run_script("7", FAKE_GH_FAIL="1")
        self.assertEqual(result.returncode, 1)
        self.assertIn("HTTP 404", result.stderr)
        self.assertEqual(result.stdout, "")

    def test_bad_usage_exits_2(self) -> None:
        self.assertEqual(self.run_script().returncode, 2)


if __name__ == "__main__":
    unittest.main()
