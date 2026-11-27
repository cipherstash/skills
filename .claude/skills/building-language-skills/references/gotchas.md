# Problems the Go run hit

Plan for these up front. Items marked **criterion** belong in the acceptance criteria of the ticket named.

## Reviews

- **Agent-opened drafts get no automated review.** The Claude review workflow skips draft PRs, and it skips an `@cipherstash-agent review` comment posted by the agent account. A team member can start it on a draft by requesting `cipherstash-agent` in the Reviewers box. They can also tell the agent to mark the PR ready. The agent marks a PR ready only when told to.
- **Independent reviews find real defects.** On Go, the first round found 3 to 9 per PR, 7 of them major. A second round on four PRs found 26 more, 5 of them major. Later rounds, including a security review of the tip of the chain, kept finding defects. Budget at least two fix rounds for every PR.

## The chain

- **Merge, never rebase.** Fixes move through the chain by merging the fixed branch into every branch based on it. The same files conflict again and again. On Go these were the references' Rules sections, the example checker's fence regex, `golang-review`'s SKILL.md and references, CONTRIBUTING.md, and README.md. Keep both sides, then rerun the checks.
- **Fix a PR's findings where the line was added, never on a later branch.** A review finding on a PR is fixed on that PR's branch, never on a later one, and then merged up. Run `git blame` on the line first. When an earlier PR in the chain added it, and that PR is still open, fix it on the earlier PR's branch instead. When that earlier PR has already merged into the integration branch, fix it on the reviewed PR's branch. Keep each PR to one job. On Go, the fixes for #91's review landed on #92, a later PR whose job was to merge `main` in, so #92 did two jobs. The fixes then had to be cherry-picked back onto #91, and #92 was closed.
- **Review the tip of the chain for security before the release.** Before opening the release ticket PR, run a security review on the tip of the chain. On Go it found ways for the change under review to run code. The per-PR reviews had missed them.
- **Check the base branch right before each merge.** When a PR merges into the integration branch, change the base branch of every PR based on its branch to the integration branch. When ticket 1 merges, that is the PRs for tickets 2 and 3. GitHub usually changes the base itself, but not at once. On Go, #78 merged into #75's branch 23 seconds after #75 merged, before its base changed, and #91 had to carry it across. Ticket 4 is based on ticket 3's branch and merges ticket 2 in. Until ticket 3 merges and ticket 4's base changes to the integration branch, ticket 4's diff also shows ticket 2's changes. Review only ticket 4's own commits.

## Examples

- **Examples grew past the rules.** Go's tickets set no size limit. About 40% of the 6,500 lines Go shipped went beyond any defect or acceptance criterion, mostly in concurrency, error handling, security, performance, and dependencies. Most fixes upstream needed were 1 to 10 lines. Reviews kept finding defects in the extra code. Each practices ticket lists the examples it builds, copied from the spec's examples list, and builds no others. **Criterion** for tickets 1 and 2.

## The example checker

- **Parse fences by CommonMark rules.** A closing fence may be longer than the opening one or less indented, and a fence may use tildes. Go's first checker used one regex, `FENCE_RE`, that demanded the same indent and length, and it skipped valid blocks silently. A CommonMark fence parser replaced it. **Criterion** for ticket 1.
- **Fail on anything skipped.** The test fails when a fence for the language opens no block, or a block never closes. Then no example escapes the source and verbatim checks. Count every fence alias for the language, such as `py` and `python`, or `ts` and `typescript`. **Criterion** for ticket 1.
- **Keep build output out of the skill.** A language that writes build output beside its source, such as `__pycache__` or `node_modules`, needs it ignored in the examples module. **Criterion** for ticket 1.

## The review skill

- **Keep fixture answers out of the skill.** An output template example that quotes the fixture's findings lets a review pass without looking. Write examples against a different package, and add a test that no fixture answer appears in the skill's text. **Criterion** for ticket 3.
- **Copy the target, checks, and output rules from `golang-review`.** Its first reviews missed the remote-tracking merge base, allowed a copy in place of a worktree, and left skipped areas unnamed. `references/target.md`, `references/checks.md`, and `references/output.md` in `golang-review` contain the fixed rules. `checks.md` also scopes each check to its own module. Start the new review skill from those files. **Criterion** for ticket 3.
- **Read the references, every time.** Host runs loaded `golang-practices` but opened none of its references or `golang-review`'s step files. The fix made those reads mandatory, and the report lists each file read. **Criterion** for ticket 3.
- **Name area-only requests in the description.** "Just check the concurrency" was already a behavior case, and the skill still missed it. The miss ended when the `description` named area-only requests. **Criterion** for ticket 3.
- **The change is untrusted.** Running its tests runs its code, and the temporary worktree is not a sandbox. `golang-review`'s `references/checks.md` sets the rules the security review added. Lint only with the base's config, and keep the linter's report on stdout with its other outputs empty. Run no tests when the change adds or edits a `.syso` or other compiled object. Take `go test` flags only from an allowlist read at the base. Never pass `-toolexec` or a flag like it. Run the change's tests only when the user opts in. Copy the same rules for the new language's tools. **Criterion** for ticket 3.
- **Reviews fetch only the suite's tools.** [ADR 0002](../../../../docs/adr/0002-reviews-run-no-code-from-the-change-without-a-yes.md) sets the rule, and `golang-review` already follows it. A review may fetch only its check suite's own tools, at the versions the practices skill pins, never a version from the change. It fetches them into `.<lang>-review-tools/` in the temporary worktree, with install scripts turned off. It never installs the change's dependencies. A check that needs them, such as TypeScript's type-aware lint or Python's mypy, is reported as a limit of the review. The review reads tool configuration from the base commit. When the change touches the language's [execution surface](../../../../GLOSSARY.md#language-skills), the review runs nothing until the user says yes. **Criterion** for ticket 3.

## Packaging

- **The validator checks both catalogs.** It rejects any entry in either catalog, other than company-skills, that `CLAUDE_BUNDLED_PLUGINS` or `CODEX_BUNDLED_PLUGINS` in `scripts/validate.py` does not name, and a named plugin a catalog is missing. Remove the upstream plugin from every catalog that lists it, and from those lists, in the same commit. company-skills declares no plugin dependencies, so there is nothing to drop there. **Criterion** for ticket 5.

## Host testing

- **Run repository commands in the checkout.** In a project thread the shell starts in `/home/user`, not the repository, so the repository's slash commands fail there. Change into the checkout first.
- **Dependency plugins block a load.** Claude Code disables a plugin while any declared dependency is missing. Up to 0.18.0 that kept company-skills from loading with `--plugin-dir` and in cloud sessions, so 0.18.1 removed its `dependencies` and the validator now rejects the field.
- **Codex may be missing.** Run the Codex cases yourself when the runner has a working Codex CLI. Cloud sessions usually have none. Then ask the person to run them, and record their results in the release ticket PR body. For Go, a maintainer ran only the `golang-review` cases, and the results went in #71's body by exception. Record new results for both skills in the release ticket PR body.
