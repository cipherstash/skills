# Behavior cases

## Should activate

- `/review-fix` immediately after a code review in the same session produced findings.
- "Fix those findings" right after a code review in the same session.
- "Work through these and fix what's real" with findings pasted from parallel review agents, in a session that has no review of its own.
- "Now fix them" right after review-audit reported unresolved feedback on PR 12 in the same session.
- "Fix the review comments on PR 12" with no audit in the session — the skill runs review-audit on PR 12 first, then works its Unresolved entries.
- "Fix the review findings" with no review in the session, no PR named, and nothing pasted — the skill stops and asks for findings.
- `/review-fix` in a repo with no `AGENTS.md`/`CLAUDE.md` checks, no CI config, and no manifest test command — the skill asks for the done bar instead of reporting success over no checks.

## Should not activate

- "Review this branch for bugs" — producing findings is a review's job, not this skill's.
- "What feedback is still open on PR 12?" — review-audit.
- "Post these findings to PR 12" — review-post.
- "Resolve the CodeRabbit threads that are fixed on PR 12" — resolving threads is review-audit's job.

## Expected behavior

- A review-audit report in the session is used: its Unresolved entries become ledger entries sourced by their comment URLs, its Needs decision entries end `needs-decision` with the audit's question, and its Addressed and Refuted entries are not worked. Findings from a session review or pasted input merge into the same ledger, a defect raised in both being one entry.
- Asked to fix a PR's feedback with no audit report in the session, the skill runs review-audit first instead of reading PR comments itself.
- Fixed entries from an audit report list their comment URLs in the report; no thread is resolved or replied to.
- Every input finding lands in one ledger exactly once; a defect reported by two sources is one entry listing both, at the higher normalised severity.
- The done bar runs on the untouched tree before any delegate starts, and its failures are recorded as the baseline; with a pull request open, only a completed CI run for the checked-out commit is added — a stale or in-progress run is not used.
- The baseline records `git status`; files already dirty are flagged before any commit, never committed silently with the fixes.
- Groups own disjoint file sets, including covering tests and every planned new test file; a delegate needing an unplanned file defers. A test file covering several groups belongs to none, so one shared integration suite does not pool every finding into one group.
- At most three delegates run at once; delegates never stage, commit, or push. Without subagent support (e.g. Codex without them), the main agent works the groups in turn under the same rules.
- Dispatch runs in two batches: every verify delegate (verdicts and red tests, no other edits) returns before any fix starts, so no red or refutation rests on a sibling's half-made edit.
- Each delegate prompt is built from `references/delegate-brief.md`: entries verbatim, owned files, baseline failures, and the brief's rules and return format pasted unchanged — never ledger ids alone.
- An entry deferred during the verify batch re-dispatches into verify, and no fix delegate starts until every entry has a verify verdict and none is deferred.
- Severities from mixed scales (P0–P3, blocker/nit, CodeRabbit "nitpick") normalise to critical/major/minor with the original wording kept.
- A confirmed behavioural finding gets a regression test that fails on its own assertion before the fix; a compile error is not accepted as red.
- A finding that will not go red is re-verified, not fixed blind; a refuted or needs-decision entry has any test written for it reverted.
- A confirmed finding with no behaviour to regress, or untestable in practice, is reported `fixed` with `no test — <reason>`.
- A new failure is rerun once before attribution; one that does not reproduce is reported flaky. An entry still failing after two repair rounds ends `needs-decision` with its fix and test reverted — the run never loops indefinitely.
- Nothing is committed until the done bar holds, and committing waits for the user's go-ahead with the branch named — including on `main`; nothing is pushed unless the user asks.
- Only files delegates reported touching are committed, by path — never `git add -A` or `git add .`.
- A failure also present in the baseline is reported as pre-existing, not attributed to a fix.
- The report gives every ledger entry exactly one outcome (`fixed`, `refuted`, `needs-decision`) with evidence, lists each done-bar check's result, and states what was committed or pushed; it never claims a test or CI result that was not run.
