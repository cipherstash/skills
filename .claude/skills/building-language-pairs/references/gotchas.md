# Problems the Go run hit

Each of these cost a review round on the Go pair. Plan for them up front.

## Reviews

- **Agent-opened drafts get no automated review.** The Claude review workflow skips draft PRs, and it skips an `@cipherstash-agent review` comment posted by the agent account. Get the independent review from a separate agent, as build step 8 says. For a GitHub review, ask the person to mark the PR ready or post the comment themselves.
- **Independent reviews find real defects.** On Go they found 2 to 9 per PR, 7 of them major. Budget a fix round for every PR.

## The stack

- **Merge, never rebase.** Fixes move through the stack by merging the lower branch into each branch above it. The same files conflict again and again (on Go: a reference's Rules section and the example checker's fence regex). Keep both sides, then rerun the checks.
- **Retarget as the stack merges.** When the person merges a PR into the integration branch, retarget the next PR's base to the integration branch.

## The example checker

- **Parse fences by CommonMark rules.** A closing fence may be longer than the opening one or less indented, and a fence may use tildes. A regex that demands the same indent and length skips valid blocks silently.
- **Fail on anything skipped.** The test fails when a fence for the language opens no block, or a block never closes. Then no example escapes the source and verbatim checks.

## The review skill

- **Keep fixture answers out of the skill.** An output template example that quotes the fixture's findings lets a review pass without looking. Write examples against a different package, and add a test that no fixture answer appears in the skill's text.
- **Diff against the remote-tracking base.** Take the merge base from `refs/remotes/origin/<base>`. Fall back to a local branch only when that ref is missing. Record which ref the review used. A local `main` may contain other people's commits.
- **A worktree, not a copy.** Only a detached `git worktree` counts as the temporary tree. A `git archive` export or a file copy does not.
- **Name every area not reviewed.** The report lists each area left out, and why: the request named other areas, or a check could not run.
- **Nested modules.** A change that adds a second module or package root inside the repository makes whole-repository checks fail. Scope each check to the module it belongs to.
- **Narrow requests must trigger.** "Just check the concurrency" missed the review skill until it was a behaviour case. Add a narrow, area-only request to "Should activate".

## Host testing

- **Dependency plugins block a local load.** `claude -p --plugin-dir plugins/company-skills` loads no skills unless every dependency plugin is installed. Test from a scratch copy of the plugin with `dependencies` removed from its manifest.
- **Codex may be missing.** Cloud sessions have no Codex CLI. Ask the person to run the Codex cases, and record their results in the release PR body.
