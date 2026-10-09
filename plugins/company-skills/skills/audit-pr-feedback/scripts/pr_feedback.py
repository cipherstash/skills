#!/usr/bin/env python3
"""Fetch a GitHub pull request's review feedback as one JSON document.

Usage: pr_feedback.py <PR number | PR URL>

Requires the GitHub CLI (`gh`), authenticated for the PR's host. A bare
number resolves against the repository of the current directory.

Writes to stdout:
  pr        number, url, title, author, state, isDraft, headRefName,
            headRefOid, baseRefName
  threads   inline review threads: id (GraphQL node id, for resolving),
            path, line (null once outdated), originalLine and
            originalCommit (where the first comment was written), startLine,
            side (RIGHT: the PR's version; LEFT: a line the PR deleted, in
            the base), subject (LINE, or FILE for a whole-file comment with
            no line), diffHunk (the diff the first comment was written on,
            for when originalCommit is gone), resolved, resolvedBy,
            outdated, truncated (more than 100 comments; page the rest from
            REST pulls/<n>/comments by in_reply_to_id), comments
  reviews   submitted reviews with a non-empty body: id, author, state,
            body, url, submittedAt, commit, minimized
  comments  conversation comments: id, author, body, url, createdAt,
            minimized
  pendingReview  true when the viewer has an unsubmitted review; its
            body and comments are excluded everywhere above

Each thread comment carries id (REST id, for replies), author, body, url,
createdAt, minimized. A deleted account appears as author "ghost".

Exits 1 when a gh call fails, with gh's error on stderr, and 2 on bad usage.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys

URL_RE = re.compile(r"^https?://(?P<host>[^/]+)/(?P<owner>[^/]+)/(?P<name>[^/]+)/pull/(?P<number>\d+)")
PR_FIELDS = "number,url,title,author,state,isDraft,headRefName,headRefOid,baseRefName"
COMMENT = "databaseId author { login } body url createdAt isMinimized"
QUERIES = {
    "reviewThreads": f"""query($owner: String!, $name: String!, $number: Int!, $cursor: String) {{
  repository(owner: $owner, name: $name) {{ pullRequest(number: $number) {{
    reviewThreads(first: 50, after: $cursor) {{
      pageInfo {{ hasNextPage endCursor }}
      nodes {{
        id path line originalLine startLine diffSide subjectType isResolved isOutdated resolvedBy {{ login }}
        comments(first: 100) {{ totalCount nodes {{ {COMMENT} originalCommit {{ oid }} diffHunk pullRequestReview {{ state }} }} }}
      }}
    }}
  }} }}
}}""",
    "reviews": """query($owner: String!, $name: String!, $number: Int!, $cursor: String) {
  repository(owner: $owner, name: $name) { pullRequest(number: $number) {
    reviews(first: 100, after: $cursor) {
      pageInfo { hasNextPage endCursor }
      nodes { databaseId author { login } state body url submittedAt isMinimized commit { oid } }
    }
  } }
}""",
    "comments": f"""query($owner: String!, $name: String!, $number: Int!, $cursor: String) {{
  repository(owner: $owner, name: $name) {{ pullRequest(number: $number) {{
    comments(first: 100, after: $cursor) {{
      pageInfo {{ hasNextPage endCursor }}
      nodes {{ {COMMENT} }}
    }}
  }} }}
}}""",
}


class GhError(Exception):
    pass


def gh(*args: str) -> dict:
    try:
        result = subprocess.run(["gh", *args], capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise GhError("gh (GitHub CLI) is not installed") from exc
    if result.returncode != 0:
        raise GhError(result.stderr.strip() or f"gh {' '.join(args[:2])} failed")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise GhError(f"gh returned invalid JSON: {exc}") from exc


def paged(host: str, owner: str, name: str, number: int, connection: str) -> list[dict]:
    hostname = [] if host == "github.com" else ["--hostname", host]
    nodes: list[dict] = []
    cursor = None
    while True:
        args = ["api", "graphql", *hostname, "-f", f"query={QUERIES[connection]}",
                "-f", f"owner={owner}", "-f", f"name={name}", "-F", f"number={number}"]
        if cursor:
            args += ["-f", f"cursor={cursor}"]
        try:
            page = gh(*args)["data"]["repository"]["pullRequest"][connection]
        except (KeyError, TypeError) as exc:
            raise GhError(f"unexpected GraphQL response for {connection}") from exc
        nodes += page["nodes"]
        if not page["pageInfo"]["hasNextPage"]:
            return nodes
        cursor = page["pageInfo"]["endCursor"]


def login(actor: dict | None) -> str:
    return actor["login"] if actor else "ghost"


def pending(review: dict | None) -> bool:
    return bool(review) and review.get("state") == "PENDING"


def comment(node: dict) -> dict:
    return {
        "id": node["databaseId"],
        "author": login(node["author"]),
        "body": node["body"],
        "url": node["url"],
        "createdAt": node["createdAt"],
        "minimized": node["isMinimized"],
    }


def thread(node: dict) -> dict:
    comments = node["comments"]
    first = comments["nodes"][0] if comments["nodes"] else None
    submitted = [c for c in comments["nodes"] if not pending(c.get("pullRequestReview"))]
    return {
        "id": node["id"],
        "path": node["path"],
        "line": node["line"],
        "originalLine": node["originalLine"],
        "startLine": node["startLine"],
        "side": node["diffSide"],
        "subject": node["subjectType"],
        "diffHunk": first["diffHunk"] if first else None,
        "resolved": node["isResolved"],
        "resolvedBy": login(node["resolvedBy"]) if node["resolvedBy"] else None,
        "outdated": node["isOutdated"],
        "originalCommit": first["originalCommit"]["oid"] if first and first["originalCommit"] else None,
        "truncated": comments["totalCount"] > len(comments["nodes"]),
        "comments": [comment(c) for c in submitted],
    }


def review(node: dict) -> dict:
    return {
        "id": node["databaseId"],
        "author": login(node["author"]),
        "state": node["state"],
        "body": node["body"],
        "url": node["url"],
        "submittedAt": node["submittedAt"],
        "commit": node["commit"]["oid"] if node["commit"] else None,
        "minimized": node["isMinimized"],
    }


def fetch(target: str) -> dict:
    pr = gh("pr", "view", target, "--json", PR_FIELDS)
    match = URL_RE.match(pr.get("url", ""))
    if not match:
        raise GhError(f"cannot parse pull request URL: {pr.get('url')!r}")
    host, owner, name = match["host"], match["owner"], match["name"]
    number = int(match["number"])
    pr["author"] = login(pr.get("author"))
    reviews_raw = paged(host, owner, name, number, "reviews")
    return {
        "pr": pr,
        "threads": [t for t in (thread(n) for n in paged(host, owner, name, number, "reviewThreads")) if t["comments"]],
        "reviews": [review(n) for n in reviews_raw
                    if n["body"].strip() and n["state"] != "PENDING"],
        "pendingReview": any(n["state"] == "PENDING" for n in reviews_raw),
        "comments": [comment(n) for n in paged(host, owner, name, number, "comments")],
    }


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[1] in ("-h", "--help"):
        print(__doc__, file=sys.stderr)
        return 2
    try:
        data = fetch(argv[1])
    except GhError as exc:
        print(f"pr_feedback: {exc}", file=sys.stderr)
        return 1
    json.dump(data, sys.stdout, indent=2)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
