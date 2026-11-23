# Problems the Go run hit

Plan for these up front. Items marked **criterion** belong in the acceptance criteria of the ticket named.

## Reviews

- **Agent-opened drafts get no automated review.** The Claude review workflow skips draft PRs, and it skips an `@cipherstash-agent review` comment posted by the agent account. A team member can start it on a draft by requesting `cipherstash-agent` in the Reviewers box. They can also tell the agent to mark the PR ready. The agent marks a PR ready only when told to.
- **Independent reviews find real defects.** On Go, the first round found 3 to 9 per PR, 7 of them major. A second round on four PRs found 26 more, 5 of them major. Budget two fix rounds for every PR.

## The stack

- **Merge, never rebase.** Fixes move through the stack by merging the fixed branch into every branch that contains it. The same files conflict again and again. On Go these were the references' Rules sections, the example checker's fence regex, `golang-review`'s SKILL.md and references, CONTRIBUTING.md, and README.md. Keep both sides, then rerun the checks.
- **Retarget as the stack merges.** When the person merges a PR into the integration branch, retarget every PR based on its branch to the integration branch. When ticket 1 merges, that is the PRs for tickets 2 and 3. Until ticket 2 merges, ticket 4's diff also shows ticket 2's changes, so review only ticket 4's own commits. Go never reached this point, so treat it as untested.

## The example checker

- **Parse fences by CommonMark rules.** A closing fence may be longer than the opening one or less indented, and a fence may use tildes. A regex that demands the same indent and length skips valid blocks silently. **Criterion** for ticket 1.
- **Fail on anything skipped.** The test fails when a fence for the language opens no block, or a block never closes. Then no example escapes the source and verbatim checks. Count every fence alias for the language, such as `py` and `python`, or `ts` and `typescript`. **Criterion** for ticket 1.
- **Keep build output out of the skill.** A language that writes build output beside its source, such as `__pycache__` or `node_modules`, needs it ignored in the examples module. **Criterion** for ticket 1.

## The review skill

- **Keep fixture answers out of the skill.** An output template example that quotes the fixture's findings lets a review pass without looking. Write examples against a different package, and add a test that no fixture answer appears in the skill's text. **Criterion** for ticket 3.
- **Copy the target, checks, and output rules from `golang-review`.** Its first reviews missed the remote-tracking merge base, allowed a copy in place of a worktree, and left skipped areas unnamed. `references/target.md`, `references/checks.md`, and `references/output.md` in `golang-review` contain the fixed rules. `checks.md` also scopes each check to its own module. Start the new review skill from those files. **Criterion** for ticket 3.
- **Read the references, every time.** Host runs loaded `golang-practices` but opened none of its references or `golang-review`'s step files. The fix made those reads mandatory, and the report lists each file read. **Criterion** for ticket 3.
- **Name area-only requests in the description.** "Just check the concurrency" was already a behaviour case, and the skill still missed it. The miss ended when the `description` named area-only requests. **Criterion** for ticket 3.
- **No installs during a review.** The review is read-only and installs nothing. A language whose checks need packages installed, such as TypeScript's `tsc` and linters, reports a check it cannot run as a limit of the review.

## Host testing

- **Dependency plugins block a local load.** `claude -p --plugin-dir plugins/company-skills` loads no skills unless every dependency plugin is installed. Test from a scratch copy of the plugin with `dependencies` removed from its manifest.
- **Codex may be missing.** Cloud sessions have no Codex CLI. Ask the person to run the Codex cases, and record their results in the release ticket PR body.
