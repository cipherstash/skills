# Behavior cases

`test_pr_feedback.py` covers `scripts/pr_feedback.py` against a fake `gh`: `python3 -m unittest discover -s tests` from the skill directory.

## Should activate

- `/audit-pr-feedback 42` on a PR with open review threads.
- "What review feedback is still outstanding on https://github.com/org/repo/pull/42?"
- "Which threads on PR 42 can we resolve now?"
- "Audit the review comments on my PR" with no PR given and none inferable — the skill asks for the PR number or URL.

## Should not activate

- "Fix the review comments on PR 42" — fixing is address-code-review's job.
- "Review PR 42" — a new review, not an audit of existing feedback.
- "Check my review findings against what's already on PR 42" — cross-check-review-findings.

## Expected behavior

- Feedback comes from `scripts/pr_feedback.py`: inline threads, review bodies, and conversation comments, all pages; a gh failure stops the run with gh's error.
- Verification reads the PR head commit: in place only when HEAD matches it and the tree is clean, otherwise in a detached worktree; the user's branch and uncommitted work are never checked out over, stashed, or reset, and the worktree is removed at the end.
- Resolved threads and minimized comments are tallied, not verified; approvals, praise, summaries, and bot status are tallied by kind, not entered as findings.
- A bot review body listing several nitpicks becomes several entries; the same issue raised by a human and a bot is one entry listing both sources.
- Severities from mixed scales normalise to critical/major/minor with the original wording kept.
- At most three verify delegates run at once, read-only, each prompt built from `references/verify-brief.md` with entries verbatim.
- An outdated thread is judged by reading the code at its `originalCommit` and finding the same code at head; "outdated" or an author reply saying "fixed" is never accepted as evidence of `addressed`.
- A partial fix is reported `unresolved`, naming what remains.
- Every entry lands in exactly one of Unresolved, Needs decision, Addressed (can resolve), Refuted, each with head file:line evidence and source URLs; an addressed finding from a review body or conversation comment is marked as having no thread.
- Refuted threads are flagged as needing a reply before resolving.
- No thread is resolved and no reply posted without the user's go-ahead; only Addressed threads are offered for resolution.
- With `origin` a fork, the head is fetched from the PR's own repository URL, and a `FETCH_HEAD` that is not `headRefOid` stops the run.
- An outdated thread whose `originalCommit` was force-pushed away is judged from its `diffHunk`; a `side: LEFT` thread is read as a claim about a deleted line; a `FILE` thread has no line.
- A `truncated` thread's remaining replies are paged before its entry is summarised.
- The orchestrator re-reads the head lines cited for every `addressed` and `refuted` verdict, downgrading unsupported ones to `needs-decision`; a dropped entry or failed delegate is retried once, then `needs-decision`.
- A head that moved since the audit stops thread resolution until the findings are re-verified.
- The viewer's own unsubmitted review is never counted as feedback.
- The worktree is removed on every exit, including an early stop.
