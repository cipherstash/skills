#!/usr/bin/env python3
"""Decide where a remediation worktree may start, and create or remove only worktrees this run owns.

Usage:
  workspace.py --clone DIR --path DIR --branch NAME --default BRANCH [--pr-json FILE]
  workspace.py --clone DIR --path DIR --branch NAME --default BRANCH [--pr-json FILE] --create --run-id ID
  workspace.py --clone DIR --path DIR --detach REF --create --run-id ID
  workspace.py --clone DIR --path DIR --cleanup --run-id ID

Standard library plus the git CLI. Python 3.9+. Run `git -C <clone> fetch origin` first: the
script reads remote-tracking refs and never fetches.

Inspect (the default) changes nothing. It prints JSON {action, base, pr, reasons, evidence}:
  blocked  <path> exists or is a registered worktree, whatever its state (only dry runs and
           interrupted runs leave one, and neither can be told apart from a human's edits);
           the branch is checked out in another worktree; a local branch holds commits beyond
           <base>; the branch's only PRs were closed unmerged (a human rejected it); a merged
           PR's remote branch still holds commits not on the default branch (squash merge);
           an open PR exists for a head with no remote-tracking branch.
  resume   origin/<branch> exists with commits beyond the default branch, or has an open PR:
           base is origin/<branch>, and pr is the open PR's number, if any (update it, do not
           open another).
  create   otherwise: base is origin/<default>. A remote branch holding nothing beyond the
           default branch is noted; pushing onto it is a fast-forward.
--pr-json is a JSON list of the PRs whose head is <branch>, each {number, state, merged_at}
(from the GitHub MCP `list_pull_requests` with state all and head <owner>:<branch>); a missing
list means no PRs. The branch must be fix/<issue id>-<slug> or fix/vanta-<slug>, with the issue id
lowercase (the slug keeps the package name's case), so the script never adopts a human's branch.

--create inspects first and, unless blocked, runs `git worktree add -B <branch> <path> <base>`
(or `--detach <path> <REF>`, which only needs <path> to be free) and writes an ownership marker,
vanta-remediate-owner, into that worktree's git directory, recording --run-id. The marker lives
outside the working tree, so it never shows in a diff, and goes away with the worktree.

--cleanup removes <path> only when it is a registered worktree whose marker records this
--run-id: `git worktree remove --force`, then the local branch, only when it is not on origin
and holds nothing beyond origin/<default> (the marker records the default). Anything else is
refused, and nothing is deleted.

Exit codes: 0 for create or resume (and a successful --create or --cleanup), 1 for blocked or a
refused cleanup, 2 on bad usage or a git failure.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys

MARKER = "vanta-remediate-owner"
BRANCH_RE = re.compile(r"^fix/([a-z][a-z0-9]*-[0-9]+|vanta)-[A-Za-z0-9][A-Za-z0-9._-]*$")


class GitError(Exception):
    pass


def git(clone: str, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    proc = subprocess.run(["git", "-C", clone, *args], capture_output=True, text=True)
    if check and proc.returncode != 0:
        raise GitError(f"git {' '.join(args)}: {proc.stderr.strip() or proc.returncode}")
    return proc


def ref_exists(clone: str, ref: str) -> bool:
    return git(clone, "rev-parse", "--verify", "--quiet", ref + "^{commit}", check=False).returncode == 0


def commits(clone: str, rng: str) -> list[str]:
    out = git(clone, "log", "--format=%h %an: %s", rng).stdout
    return [line for line in out.splitlines() if line]


def worktrees(clone: str) -> list[dict]:
    entries, cur = [], {}
    for line in git(clone, "worktree", "list", "--porcelain").stdout.splitlines():
        if not line:
            if cur:
                entries.append(cur)
            cur = {}
            continue
        key, _, value = line.partition(" ")
        cur[key] = value
    if cur:
        entries.append(cur)
    return entries


def same_path(a: str, b: str) -> bool:
    return os.path.realpath(a) == os.path.realpath(b)


def worktree_git_dir(path: str) -> str:
    return git(path, "rev-parse", "--absolute-git-dir").stdout.strip()


def read_marker(path: str) -> dict | None:
    try:
        with open(os.path.join(worktree_git_dir(path), MARKER), encoding="utf-8") as fh:
            return json.load(fh)
    except (GitError, OSError, ValueError):
        return None


def load_prs(path: str | None) -> list[dict]:
    if path is None:
        return []
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, list) or not all(isinstance(p, dict) and "number" in p and "state" in p for p in data):
        raise ValueError("--pr-json must be a list of {number, state, merged_at}")
    return data


def path_evidence(clone: str, path: str, registered: bool) -> dict:
    ev = {"path": path, "exists": os.path.lexists(path), "registered": registered}
    if ev["exists"] and registered:
        ev["status"] = git(path, "status", "--porcelain", "--ignored", check=False).stdout.splitlines()
        ev["head"] = git(path, "rev-parse", "HEAD", check=False).stdout.strip()
        ev["owner_marker"] = read_marker(path)
    elif ev["exists"]:
        try:
            ev["entries"] = sorted(os.listdir(path))[:20]
        except OSError as exc:
            ev["entries"] = f"unlistable: {exc}"
    return ev


def inspect(clone: str, path: str, branch: str | None, default: str, prs: list[dict], detach: str | None) -> dict:
    reasons, evidence = [], {}
    trees = worktrees(clone)
    registered = any(same_path(t.get("worktree", ""), path) for t in trees)
    if os.path.lexists(path) or registered:
        evidence["leftover"] = path_evidence(clone, path, registered)
        reasons.append(f"{path} already exists or is a registered worktree; a human must inspect and remove it")
        return {"action": "blocked", "base": None, "pr": None, "reasons": reasons, "evidence": evidence}
    if detach:
        if not ref_exists(clone, detach):
            raise GitError(f"no such ref: {detach}")
        return {"action": "create", "base": detach, "pr": None, "reasons": [], "evidence": {}}
    default_ref = f"refs/remotes/origin/{default}"
    if not ref_exists(clone, default_ref):
        raise GitError(f"{default_ref} not found; fetch origin first")
    holders = [t["worktree"] for t in trees if t.get("branch") == f"refs/heads/{branch}"]
    if holders:
        reasons.append(f"{branch} is checked out in another worktree: {', '.join(holders)}")
        evidence["checked_out_in"] = holders
        return {"action": "blocked", "base": None, "pr": None, "reasons": reasons, "evidence": evidence}

    open_prs = [p for p in prs if str(p["state"]).lower() == "open"]
    merged = [p for p in prs if str(p["state"]).lower() != "open" and (p.get("merged_at") or p.get("merged"))]
    rejected = [p for p in prs if str(p["state"]).lower() != "open" and p not in merged]
    remote_ref = f"refs/remotes/origin/{branch}"
    action, base, pr = "create", f"origin/{default}", None
    if ref_exists(clone, remote_ref):
        ahead = commits(clone, f"origin/{default}..origin/{branch}")
        evidence["remote_commits_beyond_default"] = ahead
        if open_prs:
            action, base, pr = "resume", f"origin/{branch}", open_prs[0]["number"]
        elif rejected and not merged:
            reasons.append(f"PR #{rejected[0]['number']} for {branch} was closed unmerged: a human rejected it")
        elif not ahead:
            evidence["note"] = f"origin/{branch} holds nothing beyond origin/{default}; a push onto it fast-forwards"
        elif merged:
            reasons.append(f"PR #{merged[0]['number']} merged, but origin/{branch} still holds commits not on "
                           f"{default}; a human deletes the remote branch before this issue can be worked again")
        else:
            action, base = "resume", f"origin/{branch}"
    elif open_prs:
        reasons.append(f"PR #{open_prs[0]['number']} is open for {branch} but origin/{branch} is missing; fetch first")
    elif rejected and not merged:
        reasons.append(f"PR #{rejected[0]['number']} for {branch} was closed unmerged: a human rejected it")
    if reasons:
        return {"action": "blocked", "base": None, "pr": None, "reasons": reasons, "evidence": evidence}
    if ref_exists(clone, f"refs/heads/{branch}"):
        extra = commits(clone, f"{base}..refs/heads/{branch}")
        evidence["local_commits_beyond_base"] = extra
        if extra:
            reasons.append(f"local branch {branch} holds {len(extra)} commit(s) not on {base}; "
                           "worktree add -B would reset them")
            return {"action": "blocked", "base": None, "pr": None, "reasons": reasons, "evidence": evidence}
    return {"action": action, "base": base, "pr": pr, "reasons": reasons, "evidence": evidence}


def create(clone: str, path: str, branch: str | None, default: str | None, result: dict, run_id: str,
           detach: str | None) -> dict:
    if detach:
        git(clone, "worktree", "add", "--detach", path, result["base"])
    else:
        git(clone, "worktree", "add", "-B", branch, path, result["base"])
    marker = {"run_id": run_id, "branch": None if detach else branch, "default": default, "base": result["base"],
              "base_sha": git(path, "rev-parse", "HEAD").stdout.strip()}
    with open(os.path.join(worktree_git_dir(path), MARKER), "w", encoding="utf-8") as fh:
        json.dump(marker, fh)
    return {**result, "created": path, "marker": marker}


def cleanup(clone: str, path: str, run_id: str) -> dict:
    registered = any(same_path(t.get("worktree", ""), path) for t in worktrees(clone))
    marker = read_marker(path) if registered and os.path.isdir(path) else None
    if not registered or marker is None or marker.get("run_id") != run_id:
        why = ("not a registered worktree of this clone" if not registered else
               "no ownership marker" if marker is None else "marker belongs to another run")
        return {"removed": False, "branch_deleted": False, "reasons": [f"refused: {path} is {why}; nothing deleted"]}
    git(clone, "worktree", "remove", "--force", path)
    out = {"removed": True, "branch_deleted": False, "reasons": []}
    branch, default = marker.get("branch"), marker.get("default")
    if branch and ref_exists(clone, f"refs/heads/{branch}"):
        if ref_exists(clone, f"refs/remotes/origin/{branch}"):
            out["reasons"].append(f"kept {branch}: it is on origin")
        elif not default or commits(clone, f"origin/{default}..refs/heads/{branch}"):
            out["reasons"].append(f"kept {branch}: it holds commits not on origin/{default}")
        else:
            git(clone, "branch", "-D", branch)
            out["branch_deleted"] = True
    return out


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--clone", required=True)
    parser.add_argument("--path", required=True)
    parser.add_argument("--branch")
    parser.add_argument("--default")
    parser.add_argument("--pr-json")
    parser.add_argument("--detach")
    parser.add_argument("--run-id")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--create", action="store_true")
    mode.add_argument("--cleanup", action="store_true")
    args = parser.parse_args(argv)
    if (args.create or args.cleanup) and not args.run_id:
        parser.error("--create and --cleanup need --run-id")
    if not args.cleanup and not args.detach:
        if not args.branch or not args.default:
            parser.error("--branch and --default are required")
        if not BRANCH_RE.match(args.branch):
            parser.error(f"branch {args.branch!r} must be fix/<issue id>-<slug> or fix/vanta-<slug>, "
                         "with the issue id lowercase")
    path = os.path.abspath(args.path)
    try:
        git(args.clone, "rev-parse", "--git-dir")
        if args.cleanup:
            result = cleanup(args.clone, path, args.run_id)
            json.dump(result, sys.stdout, indent=2)
            print()
            return 0 if result["removed"] else 1
        result = inspect(args.clone, path, args.branch, args.default, load_prs(args.pr_json), args.detach)
        if args.create and result["action"] != "blocked":
            result = create(args.clone, path, args.branch, args.default, result, args.run_id, args.detach)
    except (GitError, OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    json.dump(result, sys.stdout, indent=2)
    print()
    return 1 if result["action"] == "blocked" else 0


if __name__ == "__main__":
    sys.exit(main())
