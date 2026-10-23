# Behavior cases

## Should activate

- "Commit this and open a PR for issue 214."
- "This looks done — push it up so the team can review it."
- "Rebase my branch onto main and re-sign the commits; the PR is already open."
- "Open a PR for the fix we talked about" when the user mentioned an issue earlier without naming it — the skill asks which GitHub issue the work serves, or proceeds without one if there is none.

## Should not activate

- "Fix the review comments on PR 42" — address-code-review.
- "What review feedback is still outstanding on PR 42?" — audit-pr-feedback.
- "File an issue about the slow EQL upgrade" — filing-github-issues.
- "Review PR 42 for bugs" — a new code review, not authoring.

## Expected behavior

- Work on the default branch moves to a new type-prefixed branch (`fix/…`, `feat/…`) before any commit; nothing is committed to the default branch.
- Commit subjects follow `type(scope): imperative summary`; bodies explain why and the mechanism, and reference the GitHub issue when there is one.
- `git log --format='%h %G? %s' <base>..HEAD` runs before every push; an unsigned commit is fixed with `git rebase --force-rebase <base>` and pushed with `--force-with-lease`, never bare `--force`. If signing cannot work, the agent stops and tells the user rather than pushing unsigned commits.
- The repository's own CONTRIBUTING.md, AGENTS.md, or repo-local PR skill is read and followed, and its own lint/build/test commands are run; no package manager is assumed (`pnpm` is not run in a Cargo-only repository).
- The PR body has Summary, Changes, Verification, Related, and optionally Review notes; a failing or skipped check appears in Verification rather than being omitted; a repository PR template, when present, is filled in.
- No `#N` appears except as a real GitHub reference, and no Linear `CIP-…` number appears in commits, PR titles, bodies, or comments.
- The PR is opened with `create_pull_request` and `draft: true` unless the user explicitly asked for it ready; an existing open PR for the branch is updated with `update_pull_request`, not duplicated.
- A force-push that changes more than hashes on a branch with an open PR gets a PR comment via `add_issue_comment` explaining the change.
- Without a GitHub MCP server, the `gh` CLI is used instead and the report says so.
- The agent never merges, closes, or marks the PR ready for review unless asked.
