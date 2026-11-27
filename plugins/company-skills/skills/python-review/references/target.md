# Resolving the target and preparing the tree

Read this in steps 1 and 2: how each kind of target becomes a base and a head, what to do when there is none, and how to build and remove the temporary worktree the checks run in.

## Contents

- [What to record](#what-to-record)
- [Pull request](#pull-request)
- [Branch](#branch)
- [Commit range or commit](#commit-range-or-commit)
- [Diff](#diff)
- [No target named](#no-target-named)
- [No identifiable target](#no-identifiable-target)
- [The temporary worktree](#the-temporary-worktree)

## What to record

- The target as the user gave it.
- The repository: its local path, and the PR's URL for a pull request.
- The reviewed state: the full base and head commit SHAs, or, for uncommitted changes, the commit they sit on and the words "plus uncommitted changes". A snapshot is not a commit, so `review-post` cannot post a review of it until it is committed.
- The changed files from `git diff --name-status <base> <head>`. For uncommitted changes there is no head commit: the list is `git diff --name-status HEAD` plus the untracked files from `git ls-files --others --exclude-standard`.
- From that list, the changed Python files and the modules they belong to. Python files are `.py` and `.pyi` files, any file whose first line is a `#!` line that runs `python`, `pyproject.toml`, `uv.lock`, `requirements*.txt`, `.python-version`, `setup.py`, `setup.cfg`, `py.typed`, `.pth` files, the tool configs `ruff.toml`, `.ruff.toml`, `mypy.ini`, `.mypy.ini`, `pytest.ini`, `.pytest.ini`, and `tox.ini`, and, in a directory that holds Python files, compiled `.so` and `.pyd` files. A module is the nearest `pyproject.toml` project above a file, or a script with a PEP 723 `# /// script` header. A Python file in neither is a script with no module; say so.
- The changed files that CI's check suite depends on: `.semgrepignore`, the files under `.github/workflows/`, `.github/actions/`, and `.semgrep/`, and the tool configs above. Step 1 reviews a change that touches any of them, even when it changes no other Python file.
- The changed files on the execution surface, as `checks.md` lists it. Step 5 needs them.

## Pull request

1. Read the PR's URL, base branch, and head commit with the GitHub tools the host has. With the GitHub MCP server, use `pull_request_read` with method `get` (`html_url`, `base.ref`, `head.sha`). With `gh`, use `gh pr view <PR> --json url,baseRefName,headRefOid`. Where `gh` refuses GraphQL, use `gh api repos/<owner>/<repo>/pulls/<number>`. Parse the host, owner, repository, and number from the URL and use them for every later call. A bare number resolves against the current repository's default remote, so name the resolved PR in the report.
2. In a local clone of that repository, fetch the head and the base tip from the PR's own repository, since `origin` may be a fork. Fetch them one at a time and read each SHA straight after its fetch, because `FETCH_HEAD` keeps only the last fetch: `git fetch https://<host>/<owner>/<repo>.git pull/<number>/head`, then `git rev-parse FETCH_HEAD^{commit}` for the head; the same with `<base branch>` for the base tip. Fetching writes only to `.git`, not the working tree. Check that the fetched head equals the head commit; if it does not, the PR moved during the fetch, so read it again.
3. The base is `git merge-base <head commit> <base tip SHA>`, which gives the same diff GitHub shows.
4. Without a local clone, read the diff (`pull_request_read` method `get_diff`, or `gh pr diff <url>`) and the head versions of the files it touches (`get_file_contents` at the head SHA). Review from those alone. Record that no checks could run as a limit.

## Branch

The head is the branch's tip commit. The base is `git merge-base refs/remotes/origin/<base branch> <branch>`, written with the full remote-tracking ref, not the bare branch name: a bare `main` names the local branch, which can be behind the remote, so the diff would count other people's commits as part of the change, and a clone may have no local `main` at all. Use the local branch only when `git rev-parse --verify refs/remotes/origin/<base branch>` fails, and record which ref the base came from. The base branch is the one the user named, or else the default branch, found by the first of these that works:

1. `git symbolic-ref --short refs/remotes/origin/HEAD`, with `origin/` stripped. It fails with `not a symbolic ref` when `origin/HEAD` was never set, as in a repository that added its remote after `git init`.
2. The `HEAD branch:` line of `git remote show origin`, which asks the remote.
3. A local `main` or `master`, whichever exists.

If none of these gives a branch, treat the target as unidentifiable.

## Commit range or commit

- `A..B`: base `A`, head `B`.
- `A...B`: base `git merge-base A B`, head `B`.
- One commit `C`: base `C^`, head `C`. A merge commit's base is its first parent; say so. A root commit has no parent: its base is the empty tree, `git hash-object -t tree /dev/null`, so every file in it is added. There is then no base commit to run checks at.

Resolve each name with `git rev-parse --verify <name>^{commit}`. A name that does not resolve makes the target unidentifiable.

## Diff

- **Uncommitted changes** ("my changes", "what I have here"): the base is `HEAD`, the changes are `git -c diff.noprefix=false diff --no-color --no-ext-diff --no-textconv HEAD` plus untracked files from `git ls-files --others --exclude-standard`. The reviewed state is a snapshot.
- **A patch file or pasted diff**: review the patch as the change. To run checks, find the commit it applies to: the commit the user names, or `HEAD`. In the temporary worktree at that commit, run `GIT_LFS_SKIP_SMUDGE=1 git -c core.hooksPath=/dev/null apply --check` and then the same without `--check`. If it does not apply cleanly, review the patch by reading alone and record that no checks could run as a limit.

## No target named

A request such as "review my Python changes" or "is this ready to merge?" names no target. Resolve it from the repository, in this order:

1. Uncommitted changes that touch Python files: review them as a snapshot. If the current branch also has commits ahead of `refs/remotes/origin/<default branch>`, review the branch and the uncommitted changes together, and say so: the base is then the branch's base, found against the remote-tracking ref as [Branch](#branch) describes, and the head is the snapshot.
2. A current branch with commits ahead of the default branch: review that branch. Count the commits against `refs/remotes/origin/<default branch>`, as in [Branch](#branch).
3. Otherwise there is no identifiable target.

## No identifiable target

Stop before step 2 and report, without asking a question:

- what you looked for and found, for example "no uncommitted changes, and `main` has no commits ahead of `origin/main`", or "`feature-x` is not a branch or commit here";
- what the review needs: a PR number or URL, a branch name, a commit range such as `main..feature-x`, or a diff.

Outside a git repository, with no PR URL or diff given, the report says that too.

## The temporary worktree

Checks run in a worktree made with `git worktree add`, so that the user's working tree, index, and branch stay as they were. A `git archive` export, a copy of the files, or a checkout in the user's tree is not a substitute. An archive leaves out files marked `export-ignore` and rewrites `export-subst` ones. The checks would then not run on the reviewed commit. A checkout in the user's tree would change it.

The worktree is not a sandbox. Code that runs in it, such as a test, runs as the user and can write anywhere the user can. Writable places include the main repository's `.git` directory, named in the worktree's `.git` file. Reading the code first, and the rules in `checks.md` on when tests run, are what protect the user.

Checking out the change's code must run none of it. Run every git command that checks out or updates files in the worktree (`worktree add`, and `apply` in it) with `GIT_LFS_SKIP_SMUDGE=1 git -c core.hooksPath=/dev/null …`. Without them, `worktree add` runs the repository's `post-checkout` hook, and any hook manager it starts, before the change has been read, and Git LFS downloads large files over the network. Files stored in LFS stay as pointer files; a test that loads one fails, which is a limit, not a finding.

1. Record `git status --porcelain` for the user's tree.
2. Choose a directory outside the repository: the host's scratch directory, or one from `mktemp -d`.
3. Create the worktree at the head: `GIT_LFS_SKIP_SMUDGE=1 git -c core.hooksPath=/dev/null worktree add --detach <dir>/python-review-<short head SHA> <head commit>`. This writes only under `.git/worktrees/`.
4. For uncommitted changes, create it at `HEAD` instead. Then copy the changes in with `git -c diff.noprefix=false diff --no-color --no-ext-diff --no-textconv --binary HEAD | GIT_LFS_SKIP_SMUDGE=1 git -C <worktree> -c core.hooksPath=/dev/null apply --binary`, and copy each untracked file from `git ls-files --others --exclude-standard -z` to the same path in the worktree. The flags keep the user's git config, such as `diff.noprefix`, `color.diff`, an external diff tool or a `textconv` driver, out of the patch. A patch file is applied the same way. If `apply` fails, remove the worktree, review the snapshot by reading alone, and record that no checks could run as a limit, with git's error.
5. Remove it on every exit from here on, including a stop: `git worktree remove --force <worktree>`. Do not run `git worktree prune`, which also deletes the records of the user's other worktrees whose directories are missing, such as ones on an unmounted drive. Remove a base worktree, if `checks.md` had you make one, the same way. Make a base worktree exactly as this one, at the base commit.
6. Before the report, run `git status --porcelain` again for the user's tree. Any difference from step 1 is reported, with the paths.
