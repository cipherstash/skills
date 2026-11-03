#!/usr/bin/env python3
"""Fetch a GitHub pull request's review feedback as one JSON document.

Usage: pr_feedback.py <PR number | PR URL>

Requires the GitHub CLI (`gh`), authenticated for the PR's host. A bare
number resolves against the repository of the current directory.

Fetches over GraphQL. Where GraphQL is refused — Claude Code cloud
sessions and scheduled tasks proxy GitHub and allow REST only — it falls
back to REST, plus the proxy's CCR route
pulls/<n>/ccr/review_threads for thread resolution.

Writes to stdout:
  api       "graphql", or "rest" after the fallback; it decides how a
            thread is resolved (see id)
  pr        number, url, title, author, state, isDraft, headRefName,
            headRefOid, baseRefName
  threads   inline review threads: id (for resolving — under graphql the
            thread's node id, for the resolveReviewThread mutation; under
            rest the first comment's REST id, for POST
            pulls/<n>/ccr/comments/<id>/resolve),
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
createdAt, minimized. A deleted account appears as author "ghost". REST
does not report minimized, so under rest it is null; truncated is always
false, since REST pages every comment.

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


GRAPHQL_REFUSED = "GraphQL is not available"
PER_PAGE = 100


class GhError(Exception):
    pass


class GraphQLRefused(GhError):
    pass


def gh(*args: str) -> dict:
    try:
        result = subprocess.run(["gh", *args], capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise GhError("gh (GitHub CLI) is not installed") from exc
    if result.returncode != 0:
        message = result.stderr.strip() or f"gh {' '.join(args[:2])} failed"
        if GRAPHQL_REFUSED in message:
            raise GraphQLRefused(message)
        raise GhError(message)
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


def rest_paged(host: str, path: str) -> list[dict]:
    hostname = [] if host == "github.com" else ["--hostname", host]
    items: list[dict] = []
    page = 1
    while True:
        batch = gh("api", *hostname, f"{path}?per_page={PER_PAGE}&page={page}")
        if not isinstance(batch, list):
            raise GhError(f"unexpected REST response for {path}")
        items += batch
        if len(batch) < PER_PAGE:
            return items
        page += 1


def first_key(obj: dict, *keys: str):
    return next((obj[k] for k in keys if k in obj), None)


def ccr_resolution(data) -> dict[int, tuple[bool, str | None]]:
    """Map every comment id the CCR review_threads response names to its
    thread's (resolved, resolvedBy)."""
    if isinstance(data, dict):
        data = first_key(data, "review_threads", "reviewThreads", "threads", "nodes") or []
    if not isinstance(data, list):
        raise GhError("unexpected CCR review_threads response")
    status: dict[int, tuple[bool, str | None]] = {}
    for t in data:
        resolved = first_key(t, "is_resolved", "isResolved", "resolved")
        if resolved is None:
            continue
        by = first_key(t, "resolved_by", "resolvedBy")
        by = by.get("login") if isinstance(by, dict) else by
        comments = first_key(t, "comments") or []
        if isinstance(comments, dict):
            comments = first_key(comments, "nodes") or []
        ids = [first_key(c, "id", "database_id", "databaseId") for c in comments if isinstance(c, dict)]
        ids += first_key(t, "comment_ids", "commentIds") or []
        ids.append(first_key(t, "comment_id", "first_comment_id", "root_comment_id", "databaseId"))
        for i in ids:
            if isinstance(i, int):
                status[i] = (bool(resolved), by)
    return status


def rest_user(user: dict | None) -> str:
    return user["login"] if user else "ghost"


def rest_comment(node: dict) -> dict:
    return {
        "id": node["id"],
        "author": rest_user(node.get("user")),
        "body": node.get("body") or "",
        "url": node.get("html_url"),
        "createdAt": node.get("created_at"),
        "minimized": None,
    }


def rest_threads(host: str, base: str, pending_ids: set[int]) -> list[dict]:
    raw = [c for c in rest_paged(host, f"{base}/comments")
           if c.get("pull_request_review_id") not in pending_ids]
    status = ccr_resolution(gh("api", *([] if host == "github.com" else ["--hostname", host]),
                               f"{base}/ccr/review_threads"))
    by_id = {c["id"]: c for c in raw}

    def root(c: dict) -> int:
        seen = set()
        while c.get("in_reply_to_id") in by_id and c["id"] not in seen:
            seen.add(c["id"])
            c = by_id[c["in_reply_to_id"]]
        return c.get("in_reply_to_id") or c["id"]

    groups: dict[int, list[dict]] = {}
    for c in raw:
        groups.setdefault(root(c), []).append(c)
    threads = []
    for root_id, comments in groups.items():
        comments.sort(key=lambda c: (c.get("created_at") or "", c["id"]))
        first = by_id.get(root_id, comments[0])
        subject = (first.get("subject_type") or "line").upper()
        resolved, by = next((status[c["id"]] for c in [first, *comments] if c["id"] in status),
                            (None, None))
        threads.append({
            "id": root_id,
            "path": first.get("path"),
            "line": first.get("line"),
            "originalLine": first.get("original_line"),
            "startLine": first.get("start_line"),
            "side": first.get("side"),
            "subject": subject,
            "diffHunk": first.get("diff_hunk"),
            "resolved": resolved,
            "resolvedBy": by if resolved else None,
            "outdated": first.get("line") is None and subject != "FILE",
            "originalCommit": first.get("original_commit_id"),
            "truncated": False,
            "comments": [rest_comment(c) for c in comments],
        })
    return threads


def rest_review(node: dict) -> dict:
    return {
        "id": node["id"],
        "author": rest_user(node.get("user")),
        "state": node["state"],
        "body": node.get("body") or "",
        "url": node.get("html_url"),
        "submittedAt": node.get("submitted_at"),
        "commit": node.get("commit_id"),
        "minimized": None,
    }


def fetch_rest(pr: dict, host: str, owner: str, name: str, number: int) -> dict:
    base = f"repos/{owner}/{name}/pulls/{number}"
    reviews_raw = rest_paged(host, f"{base}/reviews")
    pending_ids = {r["id"] for r in reviews_raw if r["state"] == "PENDING"}
    return {
        "api": "rest",
        "pr": pr,
        "threads": rest_threads(host, base, pending_ids),
        "reviews": [rest_review(n) for n in reviews_raw
                    if (n.get("body") or "").strip() and n["state"] != "PENDING"],
        "pendingReview": bool(pending_ids),
        "comments": [rest_comment(n) for n in rest_paged(host, f"repos/{owner}/{name}/issues/{number}/comments")],
    }


def rest_pr(target: str) -> dict:
    """`gh pr view` over REST, for a PR number or URL."""
    match = URL_RE.match(target)
    if match:
        hostname = [] if match["host"] == "github.com" else ["--hostname", match["host"]]
        path = f"repos/{match['owner']}/{match['name']}/pulls/{match['number']}"
    elif target.isdigit():
        hostname, path = [], f"repos/{{owner}}/{{repo}}/pulls/{target}"
    else:
        raise GhError(f"GitHub GraphQL is unavailable here; pass a PR number or URL, not {target!r}")
    node = gh("api", *hostname, path)
    state = "MERGED" if node.get("merged_at") else str(node.get("state", "")).upper()
    return {
        "number": node["number"],
        "url": node["html_url"],
        "title": node.get("title"),
        "author": node.get("user"),
        "state": state,
        "isDraft": bool(node.get("draft")),
        "headRefName": node["head"]["ref"],
        "headRefOid": node["head"]["sha"],
        "baseRefName": node["base"]["ref"],
    }


def fetch(target: str) -> dict:
    try:
        pr = gh("pr", "view", target, "--json", PR_FIELDS)
        api = "graphql"
    except GraphQLRefused:
        pr, api = rest_pr(target), "rest"
    match = URL_RE.match(pr.get("url", ""))
    if not match:
        raise GhError(f"cannot parse pull request URL: {pr.get('url')!r}")
    host, owner, name = match["host"], match["owner"], match["name"]
    number = int(match["number"])
    pr["author"] = login(pr.get("author"))
    if api == "rest":
        return fetch_rest(pr, host, owner, name, number)
    try:
        reviews_raw = paged(host, owner, name, number, "reviews")
    except GraphQLRefused:
        return fetch_rest(pr, host, owner, name, number)
    return {
        "api": "graphql",
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
