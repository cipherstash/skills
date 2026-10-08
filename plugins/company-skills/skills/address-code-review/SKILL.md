---
name: address-code-review
description: Verify and fix code review findings — this session's review plus any pasted from parallel agents — each confirmed defect fixed red first with a regression test. Invoked explicitly after a code review; does not perform the review itself.
argument-hint: "[pasted findings]"
disable-model-invocation: true
---

# address-code-review

Turn code review findings into verified fixes. A finding is a claim, not a fact: every one earns a **verdict** backed by evidence before any code changes, and a confirmed defect goes **red first** — a regression test that fails on the current code — so the test outlives the fix.

## Inputs

The findings already in this session's context (a code review run earlier in the conversation), merged with any pasted into the invocation — that is how parallel agents' findings arrive. With neither, stop and ask for findings: this skill works a list of findings, and producing that list is a review's job.

## Steps

1. **Ledger.** Merge every finding into one ledger: a short id minted here and used in every prompt and in the report, file:line, claim, failure scenario (`n/a` for a finding with no behaviour, such as naming or a convention), severity, sources. Normalise each source's severity to critical/major/minor and keep the original wording beside it. The same defect reported twice is one entry listing both sources, at the higher normalised severity. Order most-severe first. Completion: every input finding appears in the ledger exactly once.

2. **Partition.** Each finding owns the files its claim cites — or, citing none, the files located for it here — plus the tests that cover them, since its regression test lands there; a new test file belongs to the group that creates it. Group findings by owned files, pooling any two that share one. Completion: every ledger entry sits in exactly one group, and no file appears in two groups.

3. **Baseline, then delegate.** First run the step 4 done bar on the untouched tree and record each check's result and, for a red check, the individual failures it reports — with a pull request open, from its last CI run too — so failures that predate the fixes are known. Then dispatch one `general-purpose` agent per group, all groups in one parallel batch, pooling the smallest groups once the count passes a workable number of concurrent agents. A delegate sees neither this conversation nor this skill, so each prompt carries its group's ledger entries verbatim, the group's owned file list, the baseline failures, the three rules below, and the return format — a prompt naming ids alone arrives empty. Delegates edit files and run the group's own tests only — the full bar is step 4's job — they never stage, commit, or push, since concurrent agents share one working tree and one git index. Each agent works its entries in ledger order:
   - **Investigate and verify.** Read the code and either reproduce the failure scenario or trace exactly why it cannot happen. Verdict: `confirmed`, `refuted`, or `needs-decision` for a finding that turns on a product or design decision. Each verdict carries its evidence, and `needs-decision` states the question.
   - **Fix, red first.** A confirmed finding that describes behaviour gets its regression test first: the test goes red on the current code for that exact failure scenario, and only then is made to pass. Red means the test's own assertion fails; a build or compile error is not red. A build error the baseline already shows blocks the test: return the entry as `needs-decision` with the output. A build error the baseline does not show, caused by a file outside the group, means another agent is mid-edit: rerun, and if it persists return the entry as deferred with the output. An entry that ends `refuted` or `needs-decision` reverts any test written for it. A behavioural finding that will not go red is evidence the verdict was wrong — return to verification. Re-confirmed but untestable in practice (a race, timing, an external service) is fixed without a test and the reason recorded. A confirmed finding with no behaviour to regress — naming, duplication, a convention or ADR point — is fixed directly.
   - **Stay inside the group.** A fix that needs a file outside the group stops there: revert the partial fix, keep any red regression test, and return that entry as deferred with its verdict, its evidence, and the file it wanted.

   Each agent returns, per entry: the verdict, its evidence, and for a fixed entry a one-line summary of the change, the files it touched, and the regression test's file:line with the red output that proved the finding real, or the reason it has no test. Deferred entries re-partition by step 2's rule, with the wanted files added, and dispatch again carrying their verdict, evidence, and any kept test's file:line and red output, so neither verification nor the test is repeated. A batch that defers every entry it was given is a cycle: pool those entries into one group worked by a single agent free of any file set — the file set exists to keep concurrent agents apart, and a lone agent has no one to collide with. Completion: every ledger entry has a verdict and none is deferred.

4. **Verify the tree.** Meet the repo's done bar: the checks its `AGENTS.md` / `CLAUDE.md` names, or absent those, the test, lint, and type-check commands its CI config runs. Commit the files the delegates reported touching and every regression test file they cite, by path — never a blanket add, which sweeps in unrelated work — and with a pull request open, push them and read its CI. A failure also present in the baseline is pre-existing: report it, do not return it to step 3. A new failure returns the responsible entry — or entries, where the failure is not attributable to one — to step 3 with the failing output and the entry's prior fix, so the delegate repairs rather than restarts, and the bar runs again. Completion: every failure on the final tree also appears in the baseline, each check's result reported.

5. **Report.** Map each ledger entry, with all its sources, to exactly one outcome:
   - `fixed` — the change, plus the regression test's file:line, or `no test — <reason>` (no behaviour to regress, or untestable and why).
   - `refuted` — the evidence.
   - `needs-decision` — the decision the user must make.

   Then list each done-bar check with its result, marking pre-existing failures. Completion: every ledger entry carries an outcome, and every input finding is traceable to an entry through its sources.
