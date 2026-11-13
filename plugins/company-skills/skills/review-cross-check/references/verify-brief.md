# Verify brief

Build every delegate prompt from this file. Fill the bracketed fields in **Assignment**, then paste everything from **Assignment** to the end unchanged. A delegate sees neither the conversation nor the skill, so this brief is all it knows.

---

## Assignment

- **Pull request:** [URL]
- **Head commit:** [sha]
- **Tree:** [absolute path to a checkout of the head commit]
- **Findings, verbatim and in ledger order:** [id, file:line, claim, failure scenario, severity, sources — for each finding]

## Constraints

- Read-only. Edit, stage, commit, and push nothing in the tree; other agents read it concurrently. Reproductions and scratch tests go in a temporary directory outside it.
- Judge the code at the head commit. A finding may have been written against an earlier commit; locate its code at head by content, not line number.
- Work the findings in ledger order.

## Rules

1. **Investigate.** Read the code the finding cites and its callers. For a behavioural claim, either reproduce the failure scenario — a scratch test, a script, a traced input — or trace exactly why it cannot happen. For an objective non-behavioural claim, such as a documented convention violation or a missing test assertion, cite the applicable rule or contract and the head evidence that establishes or disproves the violation. A test-gap claim must name a required case and show how the relevant suite omits it or accepts a wrong result; a coverage percentage alone is insufficient. Mark its runtime failure scenario `n/a`; a test gap does not prove the implementation is broken. A subjective preference without an applicable requirement is `needs-decision`.
2. **Verdict**, each with evidence citing head file:line:
   - `confirmed` — the failure or objective violation exists at head. For behaviour, give the concrete trigger: the input or state, and the wrong result; otherwise give the rule or contract and violation evidence.
   - `refuted` — the failure cannot happen at head, or the claimed objective violation does not hold. Cite the preventing guard, type, invariant or caller, the satisfied or inapplicable requirement, or a later commit that fixed it (name it).
   - `needs-decision` — the finding turns on a product or design choice the code cannot settle; state the question.
3. **Correct the finding.** Where the claim is right but a detail is wrong — the line, the scope, the severity, the suggested fix — confirm it and return the corrected detail. List every other site with the same defect. Where the claimed failure or violation does not hold, the verdict is `refuted`, even if the code has a different defect nearby; report that defect separately under **Other defects**, not as a correction.
4. **No speculation.** A failure that needs an input no caller can produce is `refuted`. "Could be a problem if…" with no reachable trigger is not `confirmed`.

## Return format

Per finding:

- `id` and verdict.
- Evidence: head file:line and the reproduction, trace, or applicable requirement and violation evidence; for `needs-decision`, the question.
- For `confirmed`: the root cause in one sentence, the concrete trigger (or `n/a` for a non-behavioural claim), every affected site, a fix if one is clear, and any correction to the finding as given.

Then **Other defects**: any defect found along the way that no assigned finding claims, with file:line and trigger or objective violation evidence.
