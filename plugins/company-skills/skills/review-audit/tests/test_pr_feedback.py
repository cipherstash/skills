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
    if os.environ.get("FAKE_GH_PROXY"):
        if args[:2] in (["pr", "view"], ["api", "graphql"]):
            sys.stderr.write("HTTP 403: GitHub GraphQL is not available from Claude Code sessions; use the REST API\n")
            sys.exit(1)
        path = next(a for a in args[1:] if not a.startswith("-") and a != os.environ.get("FAKE_GH_HOST"))
        route, _, qs = path.partition("?")
        page = int(dict(p.split("=") for p in qs.split("&")).get("page", 1)) if qs else 1
        def u(login):
            return {"login": login} if login else None
        def rc(i, reply_to=None, review=100, line=5, login="alice"):
            return {"id": i, "in_reply_to_id": reply_to, "pull_request_review_id": review,
                    "path": "a.py", "line": line, "original_line": 5, "start_line": None,
                    "side": "RIGHT", "subject_type": "line", "diff_hunk": "@@ -1 +1 @@",
                    "original_commit_id": f"orig{i}", "user": u(login), "body": f"c{i}",
                    "html_url": f"u{i}", "created_at": f"2026-01-0{i % 9 + 1}T00:00:00Z"}
        if route.endswith("/pulls/7"):
            out = {"number": 7, "html_url": os.environ["FAKE_GH_URL"], "title": "T", "user": None,
                   "state": "open", "draft": True, "merged_at": None,
                   "head": {"ref": "feat", "sha": "abc123"}, "base": {"ref": "main"}}
        elif route.endswith("/pulls/7/comments"):
            full = [rc(1000 + i, review=101) for i in range(100)]
            out = full if page == 1 else [rc(1), rc(2, reply_to=1, login=None), rc(3, line=None),
                                          rc(4, review=999), rc(5, reply_to=2)]
        elif route.endswith("/pulls/7/ccr/review_threads"):
            out = {"review_threads": [
                {"id": "PRRT_1", "is_resolved": True, "resolved_by": {"login": "bob"},
                 "comments": [{"id": 1}, {"id": 2}]},
                {"id": "PRRT_3", "is_resolved": False, "comments": [{"id": 3}]}]}
        elif route.endswith("/pulls/7/reviews"):
            out = [{"id": 10, "user": u("coderabbitai"), "state": "COMMENTED", "body": "Nitpicks",
                    "html_url": "r10", "submitted_at": "2026-01-01T00:00:00Z", "commit_id": "abc123"},
                   {"id": 11, "user": u("bob"), "state": "APPROVED", "body": "",
                    "html_url": "r11", "submitted_at": "2026-01-01T00:00:00Z", "commit_id": "abc123"},
                   {"id": 999, "user": u("me"), "state": "PENDING", "body": "draft",
                    "html_url": "r999", "submitted_at": None, "commit_id": None}]
        elif route.endswith("/issues/7/comments"):
            out = [{"id": 20, "user": None, "body": "hi", "html_url": "u20",
                    "created_at": "2026-01-01T00:00:00Z"}]
        else:
            sys.stderr.write(f"HTTP 404: Not Found ({route})\n")
            sys.exit(1)
        print(json.dumps(out))
        sys.exit(0)
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

    def test_graphql_path_reports_api(self) -> None:
        data = json.loads(self.run_script("7").stdout)
        self.assertEqual(data["api"], "graphql")
        self.assertFalse(any(c[:1] == ["api"] and "graphql" not in c for c in self.calls()))

    def test_falls_back_to_rest_when_graphql_refused(self) -> None:
        result = self.run_script("7", FAKE_GH_PROXY="1")
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data["api"], "rest")
        pr = data["pr"]
        self.assertEqual((pr["headRefOid"], pr["author"], pr["state"], pr["isDraft"]), ("abc123", "ghost", "OPEN", True))
        threads = {t["id"]: t for t in data["threads"]}
        self.assertNotIn(4, threads, "a pending review's comment must be excluded")
        one = threads[1]
        self.assertEqual([c["id"] for c in one["comments"]], [1, 2, 5], "replies, including nested, join the root thread")
        self.assertEqual((one["resolved"], one["resolvedBy"]), (True, "bob"))
        self.assertEqual(one["comments"][1]["author"], "ghost")
        self.assertIsNone(one["comments"][0]["minimized"])
        self.assertEqual((one["originalCommit"], one["side"], one["subject"]), ("orig1", "RIGHT", "LINE"))
        self.assertFalse(one["truncated"])
        three = threads[3]
        self.assertEqual((three["resolved"], three["resolvedBy"], three["outdated"]), (False, None, True))
        self.assertIsNone(threads[1000]["resolved"], "a thread the CCR route omits has unknown resolution")
        self.assertEqual(len(data["threads"]), 102, "comments page past the first 100")
        self.assertEqual([r["id"] for r in data["reviews"]], [10])
        self.assertTrue(data["pendingReview"])
        self.assertEqual(data["comments"][0]["author"], "ghost")
        rest = [c for c in self.calls() if c[:1] == ["api"] and "graphql" not in c]
        self.assertTrue(any("repos/{owner}/{repo}/pulls/7" in c for c in rest))

    def test_rest_fallback_from_url_on_enterprise_host(self) -> None:
        url = "https://git.example.com/o/r/pull/7"
        result = self.run_script(url, FAKE_GH_PROXY="1", FAKE_GH_URL=url, FAKE_GH_HOST="git.example.com")
        self.assertEqual(result.returncode, 0, result.stderr)
        rest = [c for c in self.calls() if c[:1] == ["api"] and "graphql" not in c]
        self.assertTrue(all(c[c.index("--hostname") + 1] == "git.example.com" for c in rest))
        self.assertTrue(any(c[-1] == "repos/o/r/pulls/7/ccr/review_threads" for c in rest))

    def test_rest_fallback_rejects_branch_target(self) -> None:
        result = self.run_script("feat", FAKE_GH_PROXY="1")
        self.assertEqual(result.returncode, 1)
        self.assertIn("PR number or URL", result.stderr)

    def test_bad_usage_exits_2(self) -> None:
        self.assertEqual(self.run_script().returncode, 2)


if __name__ == "__main__":
    unittest.main()
