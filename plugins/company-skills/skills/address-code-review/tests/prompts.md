# Behavior cases

The skill sets `disable-model-invocation: true` (Claude Code) and `allow_implicit_invocation: false` (Codex), so it activates only on explicit invocation.

## Should activate

- `/address-code-review` immediately after a code review in the same session produced findings.
- `/address-code-review` with findings pasted from parallel review agents, in a session that has no review of its own.
- `/address-code-review` with no review in the session and nothing pasted — the skill stops and asks for findings.

## Should not activate

- "Review this branch for bugs" — producing findings is a review's job, not this skill's.
- "Fix these review comments" without invoking the skill — implicit invocation is disabled.
- "Address the CodeRabbit threads on PR 12" — PR review-thread workflows belong to a review-thread skill.

## Expected behavior

- Every input finding lands in one ledger exactly once; a defect reported by two sources is one entry listing both, at the higher normalised severity.
- The done bar runs on the untouched tree before any delegate starts, and its failures are recorded as the baseline.
- Groups own disjoint file sets, including covering tests; delegates never stage, commit, or push.
- A confirmed behavioural finding gets a regression test that fails on its own assertion before the fix; a compile error is not accepted as red.
- A finding that will not go red is re-verified, not fixed blind; a refuted or needs-decision entry has any test written for it reverted.
- Only files delegates reported touching are committed, by path — never `git add -A` or `git add .`.
- A failure also present in the baseline is reported as pre-existing, not attributed to a fix.
- The report gives every ledger entry exactly one outcome (`fixed`, `refuted`, `needs-decision`) with evidence, and lists each done-bar check's result; it never claims a test or CI result that was not run.
