# Delegate brief

Build every delegate prompt from this file. Fill the bracketed fields in **Assignment**, then paste everything from **Assignment** to the end unchanged. A delegate sees neither the conversation nor the skill, so this brief is all it knows.

---

## Assignment

- **Batch:** [verify | fix]
- **Ledger entries, verbatim and in ledger order:** [id, file:line, claim, failure scenario, severity, sources — for each entry]
- **Owned files, including planned new test files:** [paths — or `unrestricted` for a lone agent breaking a deferral cycle]
- **Baseline failures:** [each check's failures on the untouched tree, or `none`]
- **Fix batch only — per confirmed entry:** [verdict, evidence, red regression test file:line and its red output]
- **Repair round only — per returned entry:** [the prior fix and the failing done-bar output]
- **Re-dispatch only — per previously deferred entry:** [what it returned: verdict, evidence, wanted file]

## Constraints

- Edit only owned files. Run only the tests covering owned files; the orchestrator runs the full check suite.
- Never stage, commit, or push. Other agents share this working tree and git index.
- **Verify batch:** write verdicts and red regression tests only; edit no other file.
- **Fix batch:** make each confirmed entry's red test pass, and fix confirmed entries with no test. Do not repeat verification the assignment already carries.
- Work the entries in ledger order.

## Rules

1. **Investigate and verify.** Read the code and either reproduce the failure scenario or trace exactly why it cannot happen. Verdict: `confirmed`, `refuted`, or `needs-decision` for a finding that turns on a product or design decision. Each verdict carries its evidence, and `needs-decision` states the question.
2. **Fix, red first.** A confirmed finding that describes behaviour gets its regression test in the verify batch: the test goes red on the current code for that exact failure scenario; the fix batch then makes it pass.
   - Red means the test's own assertion fails; a build or compile error is not red.
   - A build error listed in the baseline failures blocks the test: return the entry as `needs-decision` with the output.
   - A build error not in the baseline, caused by a file outside the owned files, means another agent is mid-edit: rerun, and if it persists defer the entry.
   - A behavioural finding that will not go red is evidence the verdict was wrong: return to verification.
   - Re-confirmed but untestable in practice (a race, timing, an external service): fix without a test and record the reason.
   - A confirmed finding with no behaviour to regress (naming, duplication, a convention or ADR point): fix directly.
   - An entry that ends `refuted` or `needs-decision`: revert any test written for it.
3. **Stay inside the owned files.** Work that needs any other file, including a new file not in the owned list, stops there and **defers** the entry: revert the partial fix, keep any red regression test, and return the entry with its verdict, its evidence, and the file it wanted.

## Return format

Per entry:

- `id` and outcome: `confirmed`, `refuted`, `needs-decision`, `fixed`, or `deferred`.
- Evidence for the verdict; for `needs-decision`, the question.
- Regression test file:line with its red output, or the reason there is no test.
- Fix batch: a one-line summary of the change and every file touched.
- Deferred: the file it wanted.
