---
name: review-fix
description: Verify and fix code review findings — this session's review plus any pasted from parallel agents — each confirmed behavioural defect fixed red first with a regression test wherever one can be written. Use when asked to fix, or work through, the findings of a code review run in this session, a PR's unresolved review feedback as audited by review-audit, or findings pasted from review agents. Does not perform the review, reply to or resolve PR review threads, or audit a PR's existing feedback (review-audit).
argument-hint: "[pasted findings]"
---

# review-fix

Turn code review findings into verified fixes. A finding is a claim, not a fact: every one earns a **verdict** backed by evidence before any code changes, and a confirmed behavioural defect goes **red first** — a regression test that fails on the current code — so the test outlives the fix.

## Inputs

Every source of findings present, merged:

- **A code review** run earlier in this conversation.
- **A review-audit report** in this conversation: take its **Unresolved** entries as findings, each sourced by its comment URLs and carrying the audit's evidence into the verify batch. Carry its **Needs decision** entries straight to `needs-decision` with the audit's question, unless the user has since answered it. Skip **Addressed** and **Refuted** entries — the audit has already settled them.
- **Findings pasted** into the invocation — that is how parallel agents' findings arrive.

Asked to fix a pull request's review feedback with no review-audit report for it in this conversation, run review-audit on that PR first — it changes nothing until approved — and take its report as above. With no source at all, stop and ask for findings: this skill works a list of findings, and producing that list is a review's job.

Findings about a pull request — a review-audit report, or a review of a PR — are fixed only in a checkout of that PR. review-audit verifies in a temporary worktree it removes, so the user's tree may be on any branch; establish the checkout before step 1:

- Run `gh pr view <PR> --json headRefName,headRefOid,headRepository,headRepositoryOwner,url`. The checkout is right when the current branch is the PR's head branch and `headRefOid` is `HEAD` or an ancestor of it — local commits on top are kept.
- Otherwise, with `git status --porcelain` empty, ask before running `gh pr checkout <PR>`, which also sets up a fork's remote; a local head branch behind `headRefOid` is updated the same way, on approval. With uncommitted changes, stop and ask — never stash, reset, or switch branches over the user's work.
- Record the PR, its head branch, and the remote it pushes to; step 5 pushes only there. Completion: `HEAD` is the PR's head branch and contains `headRefOid`.

## Steps

1. **Ledger.** Merge every finding into one ledger: a short id minted here and used in every prompt and in the report, file:line, claim, failure scenario (`n/a` for a finding with no behaviour, such as naming or a convention), severity, sources. Normalise each source's severity to critical/major/minor — P0, blocker, or critical → critical; P1, major, or high → major; P2 and below, minor, nit, or nitpick → minor — and keep the original wording beside it. The same defect reported twice is one entry listing both sources, at the higher normalised severity. Order most-severe first. Completion: every input finding appears in the ledger exactly once.

2. **Partition.** Each finding owns the files its claim cites — or, citing none, the files located for it here. Group findings by owned files, pooling any two that share one. A test file joins the group whose files it covers; one covering several groups' files — a shared integration suite — belongs to none, and a regression test that would land there goes in a new file instead. Plan every new test file's path here, one group each. Completion: every ledger entry sits in exactly one group, and no file, existing or planned, appears in two groups.

3. **Baseline.** Fix the done bar: the checks the repo's `AGENTS.md` / `CLAUDE.md` names, or absent those, the test, lint, and type-check commands its CI config runs, or absent those, the test command its build manifest defines. Finding no check, stop and ask the user for one — success over an empty bar proves nothing. Run the bar on the untouched tree and record each check's result and, for a red check, the individual failures it reports; with a pull request open, add the failures of the completed CI run for the checked-out commit — a run for an older commit, or one still in progress, is not a baseline. Record `git status` too: the files already carrying uncommitted changes.

4. **Delegate.** Dispatch one subagent per group — in Claude Code a `general-purpose` agent; without subagents, work the groups in turn under the same rules — all groups in one parallel batch, pooling the smallest groups until at most three run at once. A delegate sees neither this conversation nor this skill, so build each prompt from [references/delegate-brief.md](references/delegate-brief.md): fill its assignment with the group's ledger entries verbatim, its owned files including planned ones, and the baseline failures, and paste the rest unchanged — the brief carries the rules (verify, fix red first, stay inside the group), the shared-tree constraints, and the return format. A prompt naming ids alone arrives empty. Concurrent delegates share one working tree and one git index, so a sibling's half-made edit can fake a red or mask a defect; dispatch twice: a **verify** batch that writes verdicts and red tests and edits no other file, then a **fix** batch carrying each confirmed entry's verdict, evidence, and red test file:line and output, so neither is repeated.

   A delegate that needs a file outside its group defers the entry. Deferred entries re-partition by step 2's rule, with the wanted files added, and dispatch again in the batch they were deferred from, carrying what they returned. The fix batch starts only once every entry has a verify verdict and none is deferred — a verify deferral still outstanding would otherwise run beside fix edits. A batch that defers every entry it was given is a cycle: pool those entries into one group worked by a single agent whose brief lists its owned files as `unrestricted` — the file set exists to keep concurrent agents apart, and a lone agent has no one to collide with. Completion: every ledger entry has a verdict and none is deferred.

5. **Verify the tree.** Run the done bar. Rerun a new failure once; one that does not reproduce is flaky — report it, do not return it. A failure also present in the baseline is pre-existing: report it, do not return it. A reproducible new failure returns the responsible entry — or entries, where the failure is not attributable to one — to the fix batch with the failing output and the entry's prior fix, so the delegate repairs rather than restarts, and the bar runs again. An entry returned twice without clearing its failure ends `needs-decision`: revert its fix and test, keeping the failing output as evidence. Once the bar holds, list the files to commit — those the delegates reported touching and every regression test file they cite — flagging any `git status` showed dirty in the baseline, name the branch, and ask before committing; on approval commit them by path — never a blanket add, which sweeps in unrelated work. Push only when the user asks, then read the pull request's CI and treat a new failure as above. Completion: every failure on the final tree also appears in the baseline, each check's result reported, and nothing committed or pushed without the user's go-ahead.

6. **Report.** Map each ledger entry, with all its sources, to exactly one outcome:
   - `fixed` — the change, plus the regression test's file:line, or `no test — <reason>` (no behaviour to regress, or untestable and why).
   - `refuted` — the evidence.
   - `needs-decision` — the decision the user must make.

   For entries sourced from a review-audit report, give each `fixed` entry's comment URLs, so the user can have review-audit re-verify and resolve those threads once the fix is pushed; this skill never resolves or replies to threads itself.

   Then list each done-bar check with its result, marking pre-existing and flaky failures, and state what was committed or pushed. Completion: every ledger entry carries an outcome, and every input finding is traceable to an entry through its sources.
