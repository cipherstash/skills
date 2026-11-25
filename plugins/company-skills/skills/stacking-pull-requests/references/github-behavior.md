# What GitHub does with a stack

Read this when you need to explain a merge, a CI run, or GitHub's rebase to the user.
Read it also when the local record of a stack and GitHub's record disagree.
The examples come from `cipherstash/stack` and are labelled with their dates.
Other repositories have their own rules, so check the repository's settings before you rely on an example.

## Setup

GitHub's documentation says that stacked pull requests need no setup.
GitHub announced the public preview on 30 July 2026.
`gh api repos/{owner}/{repo}/stacks` lists a repository's stacks.

- [The gh-stack source code](https://github.com/github/gh-stack)
- [GitHub's documentation on stacked pull requests](https://docs.github.com/en/pull-requests/get-started/about-stacked-prs)

## After the bottom pull request merges

Example: `cipherstash/stack` #1094 merged on 7 October 2026. GitHub then did these things:

1. GitHub changed the base of the next pull request, #1095, to `main`.
2. GitHub deleted the merged branch, because that repository deletes branches after a merge.
3. GitHub rebased the remaining branches and force-pushed them. GitHub was the committer, and marked the commits as verified.

## `sync` pushes over GitHub's rebase

The gh-stack v0.3.0 source shows that `sync` replaces GitHub's rebased commits.

- In `cmd/sync.go`, `sync` force-pushes whenever it has rebased a branch.
- In `internal/git/gitops.go`, the lease for each branch is the commit that `sync` fetched immediately before the push.

So the lease always passes, and every remaining pull request gets new commits and a new CI run.
That finding comes from reading the source, not from a run.

## Merge commits from a group merge

GitHub's reference page says that a group merge makes one merge commit for each pull request.
Example: a group merge in `cipherstash/stack` on 8 October 2026 made one merge commit, `6f388478c`, for four pull requests.
The commit's title names only the top pull request, #1110.
To get one merge commit for each pull request, merge them one at a time from the bottom.

## CI

GitHub runs workflows for every pull request in a stack as if it targeted the default branch.
So a workflow filtered to pull requests into `main` runs for a pull request in the middle of a stack.

Example: `cipherstash/stack` pull request #1580 was in the middle of a stack.
That repository's `codeql.yml` and `osv-scanner.yml` workflows start only for pull requests into `main`.
Both still ran for #1580 on 17 November 2026.

In a hand-built chain, GitHub matches the workflow filter against each pull request's own base branch.
So those workflows do not start for the upper pull requests.

## `init` records the local default branch as the base

`init` records the commit of your local `<base>` as the base of the bottom branch.
`init` does this even when the bottom branch starts from a newer commit on `origin/<base>`.

Example, from a run on 20 November 2026:

- Local `main` was five commits behind `origin/main`.
- The bottom branch had been rebased onto `origin/main` before `init`.
- After `init`, `gh stack view --json` showed the local `main` commit as the bottom branch's `base`, with `"needsRebase": false`.
- The stack on GitHub showed the `origin/main` commit as the base of the bottom pull request.

A CodeRabbit review of the source guide read gh-stack's source and found a risk.
Sometimes gh-stack cannot find where a branch started.
In that case, gh-stack uses the recorded base as the starting point for a rebase.
With an out-of-date base, the rebase replays commits that `origin/<base>` already has.
The replay can stop on conflicts, or repeat work.

Nobody has seen this happen in a run.

So step 3 of SKILL.md updates the local `<base>` before `init`.

## Open questions

Nobody had checked these in a run when this skill was written:

- After the resets in step 8 of SKILL.md, does `gh stack view --json` show the stack correctly? Does gh-stack still list the merged branch?
- Do the [re-sign steps](restructuring.md#re-sign-a-branch-in-a-stack) work?
- Does the **Rebase stack** button sign commits? GitHub's reference page on stacks says yes. GitHub's page on managing stacks says no.
- Which branch does `github.base_ref` name for a pull request in the middle of a stack?
- How does the ruleset setting `require_extra_approval_for_unattributed_changes` treat the rebase that GitHub runs after a merge?
- When `init` records an out-of-date local base commit, does a later `rebase` or `sync` replay commits from `<base>`?

If a run answers one of these questions, tell the user, so that someone can update this skill.
