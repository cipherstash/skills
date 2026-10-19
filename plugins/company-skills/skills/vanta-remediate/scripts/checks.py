#!/usr/bin/env python3
"""Turn a Vanta Linear issue into the exact deps.py checks that verify it.

Usage:
  checks.py --issue FILE

Standard library only. Python 3.9+. Reads only FILE; writes nothing; runs nothing.

FILE is get_issue's result saved as returned: a bare issue, {"issue": {...}}, or a host-saved list of
{"type": "text", "text": "<json>"} blocks. It needs title and description.

The issue's generated section (from the first "## Vulnerability" to the end of the first "Vanta key:" line after
it) holds a fenced ```json advisory block written by vanta-triage. Only that block is read: the Markdown table
beside it is for people. The block is trusted only when it passes the integrity check: valid JSON, a known schema,
its key equal to the section's "Vanta key:" line and to its own repo/asset, ecosystem and package, and the advisory
digest recomputed from it (vanta-triage's algorithm, duplicated here) equal to the section's "Advisory set:" value.

Conversion, with every advisory represented:
  fix_checks      the range check: --affected for each fixed advisory's range. Plus a --target-only check when
                  a fixed advisory has no range, the title's targets differ from the block's (a stale or
                  hand-retargeted title), or no fixed advisory has a range. When the title's targets differ from
                  the block's, a second --target-only check carries the block's targets: the title is outside the
                  integrity check, so a title retargeted below the block can never be the only fix check.
                  Every one must exit 0.
  residual_check  for advisories with no fix: --affected for each one's range, or a range matching every version
                  when it has none (Vanta still reports it, so no locked version clears it). null when none.
  unfixed_advisories  every advisory id with no fix, for gate.py --unfixed-advisory.
Each check is a deps.py argument list to run after <dir>; every one carries --target for each title target,
except the block-targets check above.

Prints JSON: status ("ok" or "skip"), reasons, kind, key, repo, asset, ecosystem, package, images, targets
(the title's), block_targets, stale, digest, advisories [{id, affected, fixed_version}], fix_checks,
residual_check, unfixed_advisories. A skip carries whatever fields were read before the reason was found.
  skip  no generated section or advisory block, or the block failed its integrity check ("needs a triage
        refresh"); an Assess (container) issue (follow references/containers.md with images and advisories);
        no GitHub repo (an asset name only); a title that is not "[Vanta] Remediate <pkg> to <versions> (...)".
Exit codes: 0 ok, 1 skip, 2 bad usage or an unreadable FILE.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

SCHEMA = 1
MATCH_ALL = "< 0.0.0 || >= 0.0.0"
BLOCK_RE = re.compile(r"^```json\n(.*?)\n```$", re.S | re.M)
DIGEST_LINE_RE = re.compile(r"Advisory set:\s*`([0-9a-f]+)`")
KEY_LINE_RE = re.compile(r"Vanta key:\s*`([^`]+)`")
TITLE_RE = re.compile(r"^\[Vanta\] Remediate (?P<pkg>[^\s\"]+) to (?P<ver>.+?) \((?P<where>[^()]+)\)\s*$")
REFRESH = "needs a triage refresh"


def generated_span(description: str) -> str | None:
    """Same span as vanta-triage's generated_span()."""
    start = description.find("## Vulnerability")
    if start < 0:
        return None
    key = description.find("Vanta key:", start)
    if key < 0:
        return None
    end = description.find("\n", key)
    return description[start:end if end >= 0 else len(description)]


def advisory_digest(block: dict) -> str:
    """vanta-triage's advisory_digest(), over the block's fields. Keep the payload and algorithm identical."""
    rows = sorted([a["id"] or "", a["affected"] or "", a["fixed_version"] or ""] for a in block["advisories"])
    payload = {"schema": block["schema"], "key": block["key"], "targets": list(block["targets"]),
               "images": sorted(block["images"]), "rows": rows}
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:12]


def load_issue(data) -> dict | None:
    if isinstance(data, list) and data and all(isinstance(b, dict) and b.get("type") == "text" for b in data):
        try:
            data = json.loads("".join(b.get("text") or "" for b in data))
        except ValueError:
            return None
    if isinstance(data, dict) and isinstance(data.get("issue"), dict):
        data = data["issue"]
    if isinstance(data, dict) and isinstance(data.get("title"), str):
        return data
    return None


def _str(v) -> bool:
    return isinstance(v, str) and bool(v)


def _opt(v) -> bool:
    return v is None or _str(v)


def block_problem(block) -> str | None:
    """Why the parsed block is not a well-formed schema-1 block, or None."""
    if not isinstance(block, dict):
        return "not a JSON object"
    if block.get("schema") != SCHEMA:
        return f"unknown schema {block.get('schema')!r}"
    if block.get("kind") not in ("dependency", "container"):
        return "kind must be dependency or container"
    if not all(_str(block.get(k)) for k in ("key", "ecosystem", "package")):
        return "key, ecosystem and package must be non-empty strings"
    if not _opt(block.get("repo")) or not _opt(block.get("asset")):
        return "repo and asset must be strings or null"
    for k in ("targets", "images"):
        if not isinstance(block.get(k), list) or not all(_str(v) for v in block[k]):
            return f"{k} must be a list of strings"
    advisories = block.get("advisories")
    if not isinstance(advisories, list) or not advisories:
        return "advisories must be a non-empty list"
    for a in advisories:
        if not isinstance(a, dict) or set(a) != {"id", "affected", "fixed_version"}:
            return "each advisory must have exactly id, affected and fixed_version"
        if not _str(a["id"]) or not _opt(a["affected"]) or not _opt(a["fixed_version"]):
            return "advisory id must be a string; affected and fixed_version strings or null"
    if block["kind"] == "dependency":
        ok = block["key"] == f"dependency:{block['repo'] or block['asset']}:{block['ecosystem']}:{block['package']}"
    elif block["repo"]:
        ok = block["key"] == f"container:{block['repo']}:{block['package']}"
    else:  # keyed by one of its images
        ok = any(block["key"] == f"container:{i}:{block['package']}" for i in block["images"])
    return None if ok else "key does not match the block's repo or asset, ecosystem and package"


def checks(issue: dict) -> dict:
    out: dict = {"status": "skip", "reasons": []}

    def skip(reason: str) -> dict:
        out["reasons"].append(reason)
        return out

    span = generated_span(issue.get("description") or "")
    if span is None:
        return skip(f"no generated section; {REFRESH}")
    found = BLOCK_RE.findall(span)
    if len(found) != 1:
        return skip(f"{'no' if not found else 'more than one'} advisory block in the generated section; {REFRESH}")
    try:
        block = json.loads(found[0])
    except ValueError as exc:
        return skip(f"advisory block failed integrity check (invalid JSON: {exc}); {REFRESH}")
    problem = block_problem(block)
    if problem:
        return skip(f"advisory block failed integrity check ({problem}); {REFRESH}")
    digest, key = DIGEST_LINE_RE.search(span), KEY_LINE_RE.search(span)
    if not digest or digest.group(1) != advisory_digest(block):
        return skip(f"advisory block failed integrity check (Advisory set digest does not match); {REFRESH}")
    if not key or key.group(1) != block["key"]:
        return skip(f"advisory block failed integrity check (Vanta key line does not match); {REFRESH}")

    advisories = block["advisories"]
    out.update(kind=block["kind"], key=block["key"], repo=block["repo"], asset=block["asset"],
               ecosystem=block["ecosystem"], package=block["package"], images=block["images"],
               block_targets=block["targets"], digest=digest.group(1), advisories=advisories, targets=[],
               stale=None, fix_checks=[], residual_check=None,
               unfixed_advisories=sorted({a["id"] for a in advisories if a["fixed_version"] is None}))
    if block["kind"] == "container":
        return skip("an Assess (container) issue: follow references/containers.md with its images and advisories")
    title = TITLE_RE.match(issue.get("title") or "")
    targets = [v.strip().lstrip(">= ").strip() for v in title.group("ver").split(" / ")] if title else []
    out["targets"] = targets
    if not block["repo"]:
        return skip(f"no GitHub repo: {block['asset']!r} is a Vanta asset name")
    if not title or not all(targets):
        return skip("title is not '[Vanta] Remediate <package> to <versions> (<repo>)'")

    base = ["--ecosystem", block["ecosystem"], "--package", block["package"]]
    base += [a for t in targets for a in ("--target", t)]
    fixed = [a for a in advisories if a["fixed_version"] is not None]
    unfixed = [a for a in advisories if a["fixed_version"] is None]
    ranges = list(dict.fromkeys(a["affected"] for a in fixed if a["affected"]))
    stale = sorted(targets) != sorted(block["targets"])
    out["stale"] = stale
    if ranges:
        out["fix_checks"].append(base + [a for r in ranges for a in ("--affected", r)])
    if stale or not ranges or any(not a["affected"] for a in fixed):
        out["fix_checks"].append(base)
    if stale:  # the block's targets are integrity-checked; the title's are not
        out["fix_checks"].append(base[:4] + [a for t in block["targets"] for a in ("--target", t)])
    if unfixed:
        residual = list(dict.fromkeys(a["affected"] or MATCH_ALL for a in unfixed))
        out["residual_check"] = base + [a for r in residual for a in ("--affected", r)]
    out["status"] = "ok"
    return out


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--issue", required=True)
    args = parser.parse_args(argv)
    try:
        issue = load_issue(json.loads(Path(args.issue).read_text(encoding="utf-8")))
    except (OSError, ValueError) as exc:
        print(f"error: {args.issue}: {exc}", file=sys.stderr)
        return 2
    if issue is None:
        print(f"error: {args.issue}: not a get_issue result with a title", file=sys.stderr)
        return 2
    result = checks(issue)
    json.dump(result, sys.stdout, indent=2, ensure_ascii=False)
    print()
    return 0 if result["status"] == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
