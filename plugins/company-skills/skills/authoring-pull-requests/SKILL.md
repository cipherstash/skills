---
name: authoring-pull-requests
description: Takes finished work from the working tree to a draft pull request on a CipherStash GitHub repository: branch, signed commits, the repository's own checks, and a plain-language PR body. Use when committing work, opening or updating a pull request, writing a PR title or body, re-signing or rebasing a branch with an open PR, or asked to ship work or push it up for review. Not for fixing or auditing review findings (review-fix, review-audit), filing GitHub issues (filing-github-issues), or a stack of pull requests that each need the one below (stacking-pull-requests).
---

# authoring-pull-requests

Turn finished work into a branch, signed commits, and a draft pull request a reviewer new to CipherStash can follow. These are company-wide rules. A repository's own checklist adds to them; it never loosens them.

## Inputs

- **The work**: uncommitted changes or local commits in the user's repository.
- **The issue** it serves, if any: a GitHub issue number or URL. Ask when the user mentions one without naming it; otherwise proceed without one.
- **Ready or draft**: draft unless the user explicitly says "open it ready" or "mark it ready".
- **An existing PR** for the branch, if one is open: update it rather than opening a second.

If there is nothing to commit and no unpushed commits, stop and say so.

## Tools

Use the GitHub MCP server's tools for every GitHub API step: `list_pull_requests` (find an open PR for the branch), `create_pull_request`, `update_pull_request`, and `add_issue_comment` (comment on a PR). Only when the host has no GitHub MCP server, fall back to the `gh` CLI (`gh pr list --head`, `gh pr create --draft`, `gh pr edit`, `gh pr comment`) and say in the report that you did. Use `git` for branches, commits, and pushes.

## 1. Branch

1. Find the default branch name: `git symbolic-ref --short refs/remotes/origin/HEAD` prints `origin/<name>`; strip the `origin/`. If `origin/HEAD` is not set, use `git remote show origin` (its `HEAD branch:` line) or the repository's settings. Call the bare name (for example `main`) `<base>` below, run `git fetch origin <base>`, and compare against `origin/<base>` so a stale local branch never widens the range.
2. Never commit to `<base>`. If you are on it, create a branch first.
3. Name the branch as a type-prefixed slug: `feat/…`, `fix/…`, `docs/…`, `chore/…`, `refactor/…`, `test/…` — for example `fix/prisma-null-ciphertext`. Reuse the current branch when it is already a feature branch for this work.

## 2. Commits

- Subject: `type(scope): imperative summary`, conventional-commit style — `fix(prisma): reject null ciphertext before insert`. Use the scope names the repository's history already uses (`git log --oneline -20`).
- Body: explain **why** the change is needed and the **mechanism** of the fix. Do not list what changed; the diff shows that.
- Reference the GitHub issue the commit serves (`Refs #123`, or `owner/repo#123` across repositories).
- Two wording traps apply to commits as much as to PRs: write `#N` only for a real GitHub issue or PR (GitHub autolinks it, so write "step 2", not "step #2"), and never mention internal Linear issue numbers (`CIP-…`) — GitHub is public. The full wording rules are the Wording rules in the filing-github-issues skill.

### Signed commits

Every commit must be signed. Before each push, check the range:

```bash
git log --format='%h %G? %an %s' origin/<base>..HEAD
```

On a branch above the bottom of a GitHub stack, this range also lists the commits of the branches below. Re-sign a stack with stacking-pull-requests instead. The rebase below would replay the lower branches' commits onto `<base>`.

- `N` means unsigned.
- `U` means signed with a key that is not trusted. `E` means signed with a key that is not in the local keyring. This machine cannot fully verify `U` or `E` commits. Leave them alone.
- Report any `B`, `X`, `Y`, or `R`.

Re-sign only when every commit in the range is yours, or the user's work on this branch. If the range holds anyone else's commits, stop and ask. To re-sign, pass the signing flag explicitly, because `--force-rebase` alone keeps commits unsigned unless `commit.gpgsign` is set:

```bash
git rebase --force-rebase --gpg-sign origin/<base>
git log --format='%h %G? %s' origin/<base>..HEAD   # confirm no N remains
git push --force-with-lease
```

Always `--force-with-lease`, never bare `--force`. If signing itself fails (no key configured, agent locked), stop and tell the user; do not push unsigned commits or disable signing.

## 3. Before opening the PR

1. If the repository has its own PR checklist (CONTRIBUTING.md, AGENTS.md, a repo-local skill), follow it — it adds to these rules. Read it from the file each time; do not work from memory.
2. Run the repository's own lint, build, and test commands, found in that checklist, the README, the package manifest, `Makefile`, or `justfile`. Do not assume a toolchain (`pnpm`, `cargo`, `mise`, …) the repository does not use. Scope them to the changed package when the repository supports it.
3. If a check fails, fix it, or record the failure for the Verification section. Never omit it.
4. Look for a PR template (`.github/pull_request_template.md` or `.github/PULL_REQUEST_TEMPLATE/`). If one exists, fill it in, mapping the sections below onto its headings.

## 4. PR body

Write for a reviewer who is new to CipherStash and the repository: plain wording, product terms and acronyms explained at first use, effects stated in the user's world and not only the code's. Apply the Wording rules in the filing-github-issues skill.

Sections, in order:

- **Summary** — what and why, in two or three plain sentences. Lead with the user-visible effect.
- **Changes** — grouped by area, one line each.
- **Verification** — exactly what was run and what it showed. Be honest: state a failing, skipped, or unrun check rather than omitting it. "Ran `cargo test -p stack-core`: 214 passed" beats "should work".
- **Related** — `Closes #N` or `Refs #N` for the GitHub issues this serves; cross-repository refs in full `owner/repo#N` form. No Linear refs. `Closes #N` links the pull request to the issue only when its base is the default branch. For any other base, link it with the linking-github-issues skill after you open the pull request.
- **Review notes** *(optional)* — where to look first, and anything deliberately deferred with the reason.

The PR title follows the commit-subject convention.

## 5. Open or update

1. Push the branch (`git push -u origin <branch>`) after the signature check passes.
2. Check for an open PR from this branch with `list_pull_requests` (`head: <owner>:<branch>`, `state: open`).
3. No PR: open one with `create_pull_request` — `title`, `head: <branch>`, `base: <base>`, `body`, and `draft: true`. Use `draft: false` only when the user explicitly said to open it ready.
4. An open PR: update its `title` and `body` with `update_pull_request` (`pullNumber`) when the change alters what they describe.
5. Force-pushing a branch with an open PR is fine (rebases, re-signing). When the rewrite changes more than commit hashes, say what changed in a PR comment with `add_issue_comment`.

## Boundaries

- Do not merge, close, or mark a PR ready for review unless the user asks. When they ask, mark it ready with `update_pull_request` (`draft: false`).
- Do not fix review findings or reply to review comments here; fixing them is review-fix, and auditing them is review-audit.
- Do not file issues here; that is filing-github-issues.
- Pull requests that build on each other go in a GitHub stack. Follow stacking-pull-requests for those. It uses these rules for each pull request.
- The implement-tickets workflow is the exception. That workflow builds a chain of pull requests, not a stack. When its prompt says so, never run `gh stack` or follow stacking-pull-requests.

## Report

Give the branch, the commit subjects with their signature status, the checks run and their results, and the PR link with its draft state. Name anything skipped, failed, or left for the user, and say if the `gh` fallback was used.
