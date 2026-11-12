#!/usr/bin/env python3
"""Build a scheduled run's Remediate queue from every saved page of Todo issues.

Usage:
  remediate_queue.py --pages FILE [FILE ...] [--include-assessments]

Standard library only. Python 3.9+. Reads only the files named; writes nothing.

Input: each FILE is one list_issues response saved as the Linear connector returned it, from a listing by
state Todo in the AppSec project with fields id, title, status, statusType, priority, and dueDate (SKILL.md,
Inputs). A page is an object with an "issues" array and a boolean "hasNextPage"; every issue carries every
field in FIELDS (null when empty); priority is an integer or {"value", "name"}. A host-saved list of
{"type": "text"} blocks is unwrapped first. Name files page-1.json, page-2.json, and so on in fetch order,
without gaps or duplicate numbers. Argument order does not matter; only the highest numbered page may
report hasNextPage false. Host-saved responses must be copied unchanged to these numbered filenames.

Selection: Todo issues whose title has the full Remediate shape, "[Vanta] Remediate {package} to {versions}
({repo})". With --include-assessments, Todo "[Vanta] Assess ..." issues as well. AWS configuration issues,
titled '[Vanta] Remediate "{test name}"', are never selected and are listed by id. Track-upstream, other
[Vanta] titles, and non-Vanta issues are not selected.

Order: highest priority first (1 Urgent .. 4 Low, then 0 No priority), then earliest due date (none last),
then issue number.

Output: JSON on stdout,
  {"queue": [{"id", "title", "kind" (remediate | assess), "priority", "dueDate"}],
   "issues_read", "pages_read", "selected", "aws_configuration": [ids], "unrecognised": [ids]}
where unrecognised lists "[Vanta] Remediate" titles of neither shape. A one-line summary of the counts,
AWS configuration issues, and unrecognised issue ids goes to stderr; the run report carries all three.

Exit 0 on success, including an empty queue. Exit 2, naming the file and the reason on stderr, when a file
is unreadable or is not a connector page as returned (a bare array, a missing field or "hasNextPage"), or
when the numbered sequence is incomplete or duplicated, every page still reports a next page, or a page
other than the final numbered page reports none: the listing is incomplete or mixed,
so the fetch is redone, never repaired by hand.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

FIELDS = ("id", "title", "status", "statusType", "priority", "dueDate")
REMEDIATE_RE = re.compile(r"^\[Vanta\] Remediate (?P<pkg>[^\s\"]+) to (?P<ver>\S.*?) \((?P<repo>[^()]+)\)\s*$")
AWS_RE = re.compile(r'^\[Vanta\] Remediate "')
ASSESS_RE = re.compile(r"^\[Vanta\] Assess \S")


class InputError(Exception):
    pass


def load_page(path: str) -> dict:
    try:
        data = json.loads(Path(path).read_text())
    except (OSError, ValueError) as exc:
        raise InputError(f"unreadable: {exc}")
    if isinstance(data, list) and data and all(isinstance(b, dict) and b.get("type") == "text" for b in data):
        try:
            data = json.loads("".join(b.get("text") or "" for b in data))
        except ValueError:
            raise InputError("host-saved text blocks do not hold JSON")
    if isinstance(data, list):
        raise InputError("a bare array is not a list_issues result; save the response as returned")
    if not isinstance(data, dict) or not isinstance(data.get("issues"), list):
        raise InputError('not a list_issues result: no "issues" array')
    if not isinstance(data.get("hasNextPage"), bool):
        raise InputError('no boolean "hasNextPage": not a list_issues result as returned')
    for issue in data["issues"]:
        if not isinstance(issue, dict):
            raise InputError('"issues" holds a non-object')
        missing = [f for f in FIELDS if f not in issue]
        if missing:
            raise InputError(f"issue {issue.get('id', '?')} lacks requested field(s) {', '.join(missing)}")
    return data


def priority(issue: dict) -> int:
    p = issue["priority"]
    p = p.get("value") if isinstance(p, dict) else p
    return p if isinstance(p, int) and 0 <= p <= 4 else 0


def number(ident: str) -> int:
    m = re.search(r"(\d+)$", ident or "")
    return int(m.group(1)) if m else 0


def order(item: dict) -> tuple:
    p = item["priority"]
    return (p if p else 5, item["dueDate"] or "9999-99-99", number(item["id"]), item["id"])


def build(pages: list[dict], include_assessments: bool) -> dict:
    queue, aws, unrecognised, read = [], [], [], 0
    for page in pages:
        for issue in page["issues"]:
            read += 1
            title = issue["title"] or ""
            if str(issue["status"]).lower() != "todo":
                continue
            if AWS_RE.match(title):
                aws.append(issue["id"])
                continue
            if REMEDIATE_RE.match(title):
                kind = "remediate"
            elif include_assessments and ASSESS_RE.match(title):
                kind = "assess"
            else:
                if title.startswith("[Vanta] Remediate"):
                    unrecognised.append(issue["id"])
                continue
            queue.append({"id": issue["id"], "title": title, "kind": kind, "priority": priority(issue),
                          "dueDate": (issue["dueDate"] or "")[:10] or None})
    queue.sort(key=order)
    return {"queue": queue, "issues_read": read, "pages_read": len(pages), "selected": len(queue),
            "aws_configuration": sorted(aws, key=number), "unrecognised": sorted(unrecognised, key=number)}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--pages", required=True, nargs="+", help="saved list_issues responses, one per page")
    parser.add_argument("--include-assessments", action="store_true", help="also select Todo Assess issues")
    args = parser.parse_args(argv)
    pages = []
    numbered_paths = {}
    for path in args.pages:
        try:
            match = re.fullmatch(r"page-([1-9][0-9]*)\.json", Path(path).name)
            if not match:
                raise InputError("name each response page-<n>.json, starting at page-1.json")
            index = int(match.group(1))
            if index in numbered_paths:
                raise InputError(f"duplicate page number {index}: also supplied as {numbered_paths[index]}")
            numbered_paths[index] = path
            pages.append(load_page(path))
        except InputError as exc:
            print(f"error: {path}: {exc}. Redo the fetch and save each response as returned; never repair it by hand.",
                  file=sys.stderr)
            return 2
    for expected, index in enumerate(sorted(numbered_paths), start=1):
        if expected != index:
            print(f"error: {', '.join(args.pages)}: missing page-{expected}.json. Redo the fetch and save every "
                  "response in fetch order, starting at page-1.json; never renumber an incomplete listing.",
                  file=sys.stderr)
            return 2
    final = [path for path, page in zip(args.pages, pages) if not page["hasNextPage"]]
    if len(final) != 1:
        why = ("every page reports hasNextPage true: the last page was not fetched" if not final
               else f"{len(final)} pages report hasNextPage false: pages from more than one listing")
        print(f"error: {', '.join(args.pages)}: {why}. Follow the cursor until hasNextPage is false, and save only "
              "that listing's pages.", file=sys.stderr)
        return 2
    if final[0] != numbered_paths[len(pages)]:
        print(f"error: {final[0]}: hasNextPage false before the final numbered page "
              f"{numbered_paths[len(pages)]}. Redo the fetch and save only that listing's pages in fetch order.",
              file=sys.stderr)
        return 2
    result = build(pages, args.include_assessments)
    print(f"{result['issues_read']} issues read, {result['pages_read']} pages read, {result['selected']} selected; "
          f"AWS configuration issues left out: {', '.join(result['aws_configuration']) or 'none'}; "
          f"unrecognised Remediate titles needing correction: {', '.join(result['unrecognised']) or 'none'}",
          file=sys.stderr)
    json.dump(result, sys.stdout, indent=2)
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
