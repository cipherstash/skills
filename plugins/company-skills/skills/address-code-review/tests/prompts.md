# Behavior cases

The skill sets `disable-model-invocation: true` (Claude Code) and `allow_implicit_invocation: false` (Codex), so it activates only on explicit invocation.

## Should activate

- `/address-code-review` immediately after a code review in the same session produced findings.
- `/address-code-review` with findings pasted from parallel review agents, in a session that has no review of its own.
- `/address-code-review` with no review in the session and nothing pasted — the skill stops and asks for findings.
- `/address-code-review` in a repo with no `AGENTS.md`/`CLAUDE.md` checks, no CI config, and no manifest test command — the skill asks for the done bar instead of reporting success over no checks.

## Should not activate

- "Review this branch for bugs" — producing findings is a review's job, not this skill's.
- "Fix these review comments" without invoking the skill — implicit invocation is disabled.
- "Address the CodeRabbit threads on PR 12" — PR review-thread workflows belong to a review-thread skill.

## Expected behavior

- Every input finding lands in one ledger exactly once; a defect reported by two sources is one entry listing both, at the higher normalised severity.
- The done bar runs on the untouched tree before any delegate starts, and its failures are recorded as the baseline; with a pull request open, only a completed CI run for the checked-out commit is added — a stale or in-progress run is not used.
- The baseline records `git status`; files already dirty are flagged before any commit, never committed silently with the fixes.
- Groups own disjoint file sets, including covering tests and every planned new test file; a delegate needing an unplanned file defers. A test file covering several groups belongs to none, so one shared integration suite does not pool every finding into one group.
- At most three delegates run at once; delegates never stage, commit, or push. Without subagent support (e.g. Codex without them), the main agent works the groups in turn under the same rules.
- Dispatch runs in two batches: every verify delegate (verdicts and red tests, no other edits) returns before any fix starts, so no red or refutation rests on a sibling's half-made edit.
- A confirmed behavioural finding gets a regression test that fails on its own assertion before the fix; a compile error is not accepted as red.
- A finding that will not go red is re-verified, not fixed blind; a refuted or needs-decision entry has any test written for it reverted.
- A confirmed finding with no behaviour to regress, or untestable in practice, is reported `fixed` with `no test — <reason>`.
- A new failure is rerun once before attribution; one that does not reproduce is reported flaky. An entry still failing after two repair rounds ends `needs-decision` with its fix and test reverted — the run never loops indefinitely.
- Nothing is committed until the done bar holds, and committing waits for the user's go-ahead with the branch named — including on `main`; nothing is pushed unless the user asks.
- Only files delegates reported touching are committed, by path — never `git add -A` or `git add .`.
- A failure also present in the baseline is reported as pre-existing, not attributed to a fix.
- The report gives every ledger entry exactly one outcome (`fixed`, `refuted`, `needs-decision`) with evidence, lists each done-bar check's result, and states what was committed or pushed; it never claims a test or CI result that was not run.
