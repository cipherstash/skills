# Behavior cases

`test_pr_feedback.py` covers `scripts/pr_feedback.py` against a fake `gh`: `python3 -m unittest discover -s tests` from the skill directory.

## Should activate

- `/cross-check-review-findings 42` immediately after a code review of PR 42 in the same session.
- "Check these findings against what's already been said on https://github.com/org/repo/pull/42 and draft a review" with findings pasted.
- "Drop anything reviewers already raised and give me a PR comment for the rest" after a review, with the PR named.
- `/cross-check-review-findings` after a review, with no PR given and none inferable — the skill asks for the PR number or URL.
- `/cross-check-review-findings 42` with no review in the session and nothing pasted — the skill asks for findings rather than reviewing.

## Should not activate

- "Review PR 42" — producing findings is a review's job.
- "What feedback is still open on PR 42?" — audit-pr-feedback.
- "Fix these findings" — address-code-review.

## Expected behavior

- Every input finding lands in one ledger exactly once; duplicates merge with all sources at the higher normalised severity.
- Existing feedback comes from `scripts/pr_feedback.py` and includes resolved threads, review bodies, conversation comments, and the user's own earlier comments; minimized comments are skipped, and a multi-finding bot body is split.
- New findings are verified against the PR head commit — in place only when HEAD matches and the tree is clean, otherwise in a detached worktree — by at most three read-only delegates at once, each prompt built from `references/verify-brief.md`.
- A finding fixed by a later commit, or one with no reachable trigger, is refuted with evidence and never reaches the draft.
- Matching is by root cause and failure, not by file or line: two findings on the same line with different defects are both checked separately, and one defect reported at different lines matches.
- A confirmed finding already reported, with nothing material to add, is reported as covered with the existing comment's URL and left out of the draft.
- A covered finding that adds a trigger, more affected sites, a different root cause, a better fix, higher severity with evidence, or shows a resolved thread's defect still present becomes a reply on that thread carrying only the addition.
- The draft has no greeting, summary, process narration, hedging, praise, or mention of agents or verification; each comment is at most three sentences, led by severity.
- A finding whose line is outside the diff goes in the review body, not as an inline comment.
- With nothing new or material, there is no draft, and the skill says the existing review covers every confirmed finding.
- Nothing is posted without the user's go-ahead; a head that moved since verification stops the post.
- With `origin` a fork, the head is fetched from the PR's own repository URL, and a `FETCH_HEAD` that is not `headRefOid` stops the run; the worktree is removed on every exit.
- The viewer's own unsubmitted review never counts as existing feedback, and its presence stops posting until the user submits or discards it.
- A delegate that finds a different defect than claimed returns the claim `refuted` and the other defect separately; the other defect becomes a `needs-decision` entry, never a silent substitute in the draft.
- An existing comment dismissed as "won't fix" or "intentional" still covers its defect; the finding is `covered+` only with evidence the dismissal did not weigh.
- A `covered+` addition matching several existing entries is posted once, on an unresolved thread in preference to a resolved one, and on a thread in preference to a review body or conversation comment.
- With every finding refuted or needs-decision, there is no draft and the skill says no finding survived verification — not that the existing review covers them.
- A draft holding only thread replies posts the replies and no empty review.
- Inline lines are checked against the diff hunks before posting; any outside the diff move to the review body.
