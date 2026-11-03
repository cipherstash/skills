# Behavior cases

`test_pr_feedback.py` covers `scripts/pr_feedback.py` against a fake `gh`: `python3 -m unittest discover -s tests` from the skill directory.

## Should activate

- `/review-cross-check 42` immediately after a code review of PR 42 in the same session.
- "Check these findings against what's already been said on https://github.com/org/repo/pull/42 " with findings pasted.
- "Drop anything reviewers already raised and tell me what's left" after a review, with the PR named.
- `/review-cross-check` after a review, with no PR given and none inferable — the skill asks for the PR number or URL.
- `/review-cross-check 42` with no review in the session and nothing pasted — the skill asks for findings rather than reviewing.

## Should not activate

- "Review PR 42" — producing findings is a review's job.
- "What feedback is still open on PR 42?" — review-audit.
- "Fix these findings" — review-fix.
- "Post these findings to PR 42" — review-post.

## Expected behavior

- Every input finding lands in one ledger exactly once; duplicates merge with all sources at the higher normalised severity.
- Existing feedback comes from `scripts/pr_feedback.py` and includes resolved threads, review bodies, conversation comments, and the user's own earlier comments; minimized comments are skipped, and a multi-finding bot body is split.
- New findings are verified against the PR head commit — in place only when HEAD matches and the tree is clean, otherwise in a detached worktree — by at most three read-only delegates at once, each prompt built from `references/verify-brief.md`.
- A finding fixed by a later commit, or one with no reachable trigger, is refuted with evidence and never reaches the postable set.
- Matching is by root cause and failure, not by file or line: two findings on the same line with different defects are both checked separately, and one defect reported at different lines matches.
- A confirmed finding already reported, with nothing material to add, is reported as covered with the existing comment's URL and left out of the postable set.
- A covered finding that adds a trigger, more affected sites, a different root cause, a better fix, higher severity with evidence, or shows a resolved thread's defect still present enters the postable set carrying only the addition, with that thread's URL as its reply target.
- With nothing new or material, the postable set is empty, and the skill says the existing review covers every confirmed finding.
- Nothing is written to the PR; the report offers review-post to publish the postable set.
- With `origin` a fork, the head is fetched from the PR's own repository URL, and a `FETCH_HEAD` that is not `headRefOid` stops the run; the worktree is removed on every exit.
- The viewer's own unsubmitted review never counts as existing feedback.
- A delegate that finds a different defect than claimed returns the claim `refuted` and the other defect separately; the other defect becomes a `needs-decision` entry, never a silent substitute in the postable set.
- An existing comment dismissed as "won't fix" or "intentional" still covers its defect; the finding is `covered+` only with evidence the dismissal did not weigh.
- A `covered+` addition matching several existing entries targets one existing entry: an unresolved thread in preference to a resolved one, and a thread in preference to a review body or conversation comment.
- With every finding refuted or needs-decision, the postable set is empty and the skill says no finding survived verification — not that the existing review covers them.
- In a Claude Code cloud session or scheduled task, where GitHub refuses GraphQL, the fetch falls back to REST instead of stopping at a 403.
