# Verify brief

Build every delegate prompt from this file. Fill the bracketed fields in **Assignment**, then paste everything from **Assignment** to the end unchanged. A delegate sees neither the conversation nor the skill, so this brief is all it knows.

---

## Assignment

- **Pull request:** [URL]
- **Head commit:** [sha]
- **Tree:** [absolute path to a checkout of the head commit]
- **Entries, verbatim and in ledger order:** [id, source URLs, author, where the reviewer looked — path:line, originalLine at originalCommit, side, review commit, or none — the thread's diffHunk where originalCommit could not be fetched, claim, replies that bear on it, severity — for each entry]

## Constraints

- Read-only. Edit, stage, commit, and push nothing in the tree; other agents read it concurrently. Reproductions and scratch tests go in a temporary directory outside it.
- Judge the code at the head commit. The tree is that commit; the reviewer saw an earlier one.
- Work the entries in ledger order.

## Rules

1. **Understand the claim as written.** Read the code the reviewer saw: `git -C <tree> show <originalCommit>:<path>` around `originalLine`, or the entry's diffHunk when no commit is given. `side: LEFT` means a line the PR deleted: the claim is about its removal. A whole-file comment has no line; read the file. A conversation comment carries no commit; judge it at head alone. Restate the failure or objective violation the claim describes before judging it.
2. **Find the code now.** Lines move. Locate the same code at head by content, not line number; `git -C <tree> log --oneline <originalCommit>..HEAD -- <path>` lists the commits that touched it since — after a force-push the commit may not be an ancestor, so fall back to `git -C <tree> log --oneline -- <path>`.
3. **Establish evidence.** For a behavioural claim, reproduce the failure or trace exactly why it can or cannot happen. For an objective non-behavioural claim, such as a documented convention violation or a missing test assertion, cite the applicable rule or contract and the code or tests that establish or disprove the violation, at the reviewed version where known and at head. A test-gap claim must name a required case and show how the relevant suite omits it or accepts a wrong result; a coverage percentage alone is insufficient. Mark its runtime failure scenario `n/a`; a test gap does not prove the implementation is broken. A subjective preference without an applicable requirement is `needs-decision`.
4. **Verdict**, each with evidence citing head file:line:
   - `unresolved` — the failure or objective violation the claim describes still exists at head. Show the behavioural reproduction or trace, or the applicable requirement and violation evidence.
   - `addressed` — the code or tests at head remove the claimed failure or satisfy the cited requirement. Cite the change, and the commit that made it where found. An outdated thread, a moved line, or a reply saying "fixed" is not evidence on its own.
   - `refuted` — the claim was never correct: show why the failure cannot happen or the objective violation did not exist, at the code the reviewer saw where known, and at head. A requirement changed since the review does not by itself refute the original claim.
   - `needs-decision` — the claim turns on a product or design choice, or the thread's discussion ended without agreement; state the question.
5. **Partial fixes are unresolved.** A change that handles some of the claim's cases but not all is `unresolved`, naming what remains.

## Return format

Per entry:

- `id` and verdict.
- Evidence: head file:line, the fixing commit for `addressed`, the reproduction, trace, or applicable requirement and violation evidence for `unresolved` and `refuted`, the question for `needs-decision`.
- For `unresolved`: the claim restated in one line as it stands at head.
