#!/usr/bin/env python3
"""Decide whether deps.py evidence supports a remediation claim.

Usage:
  gate.py --claim already-fixed|linked|opened --ref-kind default|merge|head|fix-branch
          [--fix FILE --fix-exit N] [--residual FILE --residual-exit N]
          [--unfixed-advisory ID ...] [--scope-ok | --scope-bad | --diff-files PATH ...]
          [--pr-base BRANCH --default-branch BRANCH]
  gate.py --claim container --ref-kind fix-branch --determinations FILE [--diff-files PATH ...]

Standard library only. Python 3.9+. Reads only the files named; writes nothing.

Remediate claims (FILE is deps.py's JSON output, N its exit code):
  already-fixed  ref-kind default.         Fix check exit 0; residual exit 0 when one is needed.
  linked         ref-kind merge or head.   Fix check exit 0; residual exit 0 or 1; --pr-base must
                                           equal --default-branch; scope enforced when given.
  opened         ref-kind fix-branch.      Fix check exit 0; residual exit 0 or 1; scope required.
  Outcome on a pass is the claim. On a failure: not-linked for linked; patch for already-fixed
  when the fix check is a valid exit 1 (still vulnerable: go on and patch); blocked otherwise.
  Every claim fails when: the claim and ref kind do not pair; the fix check is missing or exits
  anything but 0; the JSON is unreadable, lacks a stable field, or contradicts its exit code; any
  `unsupported` entry is listed (an unattended run cannot check a file by hand); a residual check
  is needed (--unfixed-advisory given) but missing, or exits anything but 0 or 1; scope is bad.
  A residual exit 1 lets linked and opened pass with must_name_unfixed set to every
  --unfixed-advisory id: the PR body and Linear comment must name each one. It never allows
  already-fixed.

Container claim (FILE is JSON {"images": [...], "advisories": [{"id", "status", "source",
"verified_images": [...]}]}, status one of fixed, removed, not-affected, staged, unfixed):
  outcome pr-in-review  every advisory fixed or removed and verified in every image; pass true
          pr-todo       every fixed or removed advisory verified in every image, others remain
          draft-todo    a fixed or removed advisory is not verified in every image
          comment-only  no advisory is fixed or removed: no PR
          blocked       bad determinations, a missing source, a bad diff, or fixes with no diff
  Only Dockerfiles may change.

Prints JSON {pass, outcome, reasons, notes, must_name_unfixed}. Exit 0 when pass is true,
1 when it is false, 2 on bad usage. A missing or unreadable input file is a failed gate (exit 1),
never a pass.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import PurePosixPath

PAIRS = {"already-fixed": {"default"}, "linked": {"merge", "head"}, "opened": {"fix-branch"},
         "container": {"fix-branch"}}
OUTCOME_PASS = {"already-fixed": "already-fixed", "linked": "linked", "opened": "opened"}
STABLE_FIELDS = ("ok", "unreadable", "unsupported", "vulnerable", "lockfiles")
MANIFESTS = {"package.json", "pnpm-workspace.yaml", "Cargo.toml", "go.mod", "pyproject.toml",
             "Pipfile", "composer.json"}
LOCKFILES = {"package-lock.json", "npm-shrinkwrap.json", "pnpm-lock.yaml", "yarn.lock", "bun.lock",
             "Cargo.lock", "go.sum", "poetry.lock", "uv.lock", "Pipfile.lock", "composer.lock"}
REQUIREMENTS = re.compile(r"requirements.*\.txt$")
DOCKERFILE = re.compile(r"(^Dockerfile(\..+)?$)|(\.Dockerfile$)|(^Containerfile$)")
STATUSES = {"fixed", "removed", "not-affected", "staged", "unfixed"}
CLEARING = {"fixed", "removed"}


def classify(path: str, container: bool) -> bool:
    """True when `path` may change for this kind of claim."""
    name = PurePosixPath(path).name
    if container:
        return bool(DOCKERFILE.search(name))
    return name in MANIFESTS or name in LOCKFILES or bool(REQUIREMENTS.match(name))


def load_json(path: str | None, label: str, reasons: list[str]):
    if path is None:
        return None
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError) as exc:
        reasons.append(f"{label}: cannot read {path}: {type(exc).__name__}: {exc}")
        return None


def check_deps(label: str, data, code: int | None, allowed: set[int], reasons: list[str]) -> bool:
    """Validate one deps.py run. True when it is readable, consistent, and its exit is allowed."""
    if code is None:
        reasons.append(f"{label}: no exit code given")
        return False
    if not isinstance(data, dict) or any(f not in data for f in STABLE_FIELDS):
        reasons.append(f"{label}: JSON is not deps.py output (needs {', '.join(STABLE_FIELDS)})")
        return False
    good = True
    if data["unsupported"]:
        paths = "; ".join(f"{u.get('path')} ({u.get('reason')})" if isinstance(u, dict) else str(u)
                          for u in data["unsupported"])
        reasons.append(f"{label}: unsupported entries cannot be checked unattended: {paths}")
        good = False
    if code == 0 and (data["vulnerable"] or not data["ok"] or data["unreadable"]):
        reasons.append(f"{label}: exit 0 contradicts its JSON (vulnerable, ok or unreadable)")
        good = False
    if code == 1 and not data["vulnerable"]:
        reasons.append(f"{label}: exit 1 with no vulnerable entry")
        good = False
    if code not in allowed:
        reasons.append(f"{label}: exit {code}" + (" (unreadable or bad usage)" if code not in (0, 1) else ""))
        good = False
    return good


def scope_result(args, container: bool, reasons: list[str]) -> bool | None:
    """True/False when scope is known, None when not given."""
    if args.scope_bad:
        reasons.append("scope: the diff changes files other than manifests and lockfiles")
        return False
    if args.scope_ok:
        return True
    if args.diff_files is None:
        return None
    bad = [p for p in args.diff_files if not classify(p, container)]
    if bad:
        reasons.append("scope: files outside the allowed set changed: " + ", ".join(bad))
        return False
    return True


def gate_remediate(args) -> dict:
    reasons, notes, name = [], [], []
    claim = args.claim
    if args.ref_kind not in PAIRS[claim]:
        reasons.append(f"ref kind {args.ref_kind} cannot support {claim} "
                       f"(needs {' or '.join(sorted(PAIRS[claim]))})")
    pairing_ok = not reasons
    # The fix check: exit 1 is a valid measurement (still vulnerable) but never a pass.
    fix_reasons: list[str] = []
    fix_code = args.fix_exit
    if args.fix is None:
        fix_reasons.append("fix check: missing")
        fix_valid = False
    else:
        fix = load_json(args.fix, "fix check", fix_reasons)
        fix_valid = fix is not None and check_deps("fix check", fix, fix_code, {0, 1}, fix_reasons)
        if fix_valid and fix_code == 1:
            fix_reasons.append("fix check: exit 1 (a resolved version is still vulnerable)")
    reasons += fix_reasons
    needed = bool(args.unfixed_advisory)
    residual_valid, residual_code = not needed, None
    if args.residual is None:
        if needed:
            reasons.append("residual check: missing, but unfixed advisories exist: " + ", ".join(args.unfixed_advisory))
    else:
        residual_reasons: list[str] = []
        residual = load_json(args.residual, "residual check", residual_reasons)
        residual_code = args.residual_exit
        residual_valid = residual is not None and check_deps("residual check", residual, residual_code, {0, 1},
                                                              residual_reasons)
        if residual_valid and residual_code == 1:
            if not needed:
                residual_reasons.append("residual check: exit 1 but no --unfixed-advisory ids to name")
                residual_valid = False
            elif claim == "already-fixed":
                residual_reasons.append("residual check: exit 1; unfixed advisories still match: "
                                        + ", ".join(args.unfixed_advisory))
            else:
                name = list(args.unfixed_advisory)
        reasons += residual_reasons
    scope = scope_result(args, False, reasons)
    if claim == "opened":
        if scope is None:
            reasons.append("scope: required for opened (pass --diff-files, --scope-ok or --scope-bad)")
        elif args.diff_files is not None and not args.diff_files:
            reasons.append("scope: the branch changes nothing against the default branch")
    if claim == "linked":
        if not args.pr_base or not args.default_branch:
            reasons.append("linked: --pr-base and --default-branch are required")
        elif args.pr_base != args.default_branch:
            reasons.append(f"linked: PR base {args.pr_base} is not the default branch {args.default_branch}")
        if args.ref_kind == "head":
            notes.append("measured the PR head: GitHub provided no merge ref; say so in the comment")
    passed = not reasons
    if passed:
        outcome = OUTCOME_PASS[claim]
    elif claim == "linked":
        outcome = "not-linked"
    elif (claim == "already-fixed" and pairing_ok and fix_valid and fix_code == 1
          and not (args.residual is not None and not residual_valid) and scope is not False):
        outcome = "patch"
    else:
        outcome = "blocked"
    if not passed:
        name = []
    return {"pass": passed, "outcome": outcome, "reasons": reasons, "notes": notes, "must_name_unfixed": name}


def gate_container(args) -> dict:
    reasons: list[str] = []
    if args.ref_kind not in PAIRS["container"]:
        reasons.append(f"ref kind {args.ref_kind} cannot support container (needs fix-branch)")
    if args.determinations is None:
        reasons.append("determinations: missing")
    data = load_json(args.determinations, "determinations", reasons)
    images, advisories = [], []
    if args.determinations is not None and data is not None:
        images = data.get("images") if isinstance(data, dict) else None
        advisories = data.get("advisories") if isinstance(data, dict) else None
        if not isinstance(images, list) or not images or not all(isinstance(i, str) and i for i in images):
            reasons.append("determinations: images must be a non-empty list of names")
            images = []
        if not isinstance(advisories, list) or not advisories:
            reasons.append("determinations: advisories must be a non-empty list")
            advisories = []
    clean = []
    for a in advisories:
        if not isinstance(a, dict) or not a.get("id"):
            reasons.append(f"determinations: advisory without an id: {a!r}")
            continue
        if a.get("status") not in STATUSES:
            reasons.append(f"{a['id']}: status must be one of {', '.join(sorted(STATUSES))}")
            continue
        if not a.get("source"):
            reasons.append(f"{a['id']}: no cited source")
            continue
        verified = a.get("verified_images") or []
        if not isinstance(verified, list):
            reasons.append(f"{a['id']}: verified_images must be a list")
            continue
        clean.append((a["id"], a["status"], set(verified)))
    scope = scope_result(args, True, reasons)
    clearing = [c for c in clean if c[1] in CLEARING]
    if clearing and not args.diff_files and not args.scope_ok:
        reasons.append("diff: fixed or removed advisories claimed but no Dockerfile change given")
    remaining = [c[0] for c in clean if c[1] not in CLEARING]
    if reasons or scope is False:
        return {"pass": False, "outcome": "blocked", "reasons": reasons, "notes": [], "must_name_unfixed": []}
    if not clearing:
        return {"pass": False, "outcome": "comment-only", "reasons": ["no advisory is fixed or removed by a change"],
                "notes": [], "must_name_unfixed": remaining}
    unverified = [c[0] for c in clearing if not set(images) <= c[2]]
    if unverified:
        return {"pass": False, "outcome": "draft-todo",
                "reasons": ["not verified in every image: " + ", ".join(unverified)], "notes": [],
                "must_name_unfixed": unverified + remaining}
    if remaining:
        return {"pass": False, "outcome": "pr-todo", "reasons": ["advisories the PR does not clear: " + ", ".join(remaining)],
                "notes": [], "must_name_unfixed": remaining}
    return {"pass": True, "outcome": "pr-in-review", "reasons": [], "notes": [], "must_name_unfixed": []}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--claim", required=True, choices=sorted(PAIRS))
    parser.add_argument("--ref-kind", required=True, choices=["default", "merge", "head", "fix-branch"])
    parser.add_argument("--fix")
    parser.add_argument("--fix-exit", type=int)
    parser.add_argument("--residual")
    parser.add_argument("--residual-exit", type=int)
    parser.add_argument("--unfixed-advisory", action="append", default=[])
    scope = parser.add_mutually_exclusive_group()
    scope.add_argument("--scope-ok", action="store_true")
    scope.add_argument("--scope-bad", action="store_true")
    scope.add_argument("--diff-files", nargs="*")
    parser.add_argument("--pr-base")
    parser.add_argument("--default-branch")
    parser.add_argument("--determinations")
    args = parser.parse_args(argv)
    result = gate_container(args) if args.claim == "container" else gate_remediate(args)
    json.dump(result, sys.stdout, indent=2)
    print()
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
