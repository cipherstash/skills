# Behavior cases

## Should activate

- "Post the review findings to PR 42" immediately after a code review in the same session.
- "Leave those comments on https://github.com/org/repo/pull/42 with an attestation" with findings pasted from parallel agents.
- "Get these in front of the author as review comments" after review-cross-check reported a postable set for PR 42.
- "Put this on the PR" after a review, with no PR given — the skill asks for the PR number or URL.
- "Post a review attestation on PR 42" with no review in the session and nothing pasted — the skill asks whether to review first, or for the reviewed commit and source of a review done elsewhere.

## Should not activate

- "Review PR 42" — producing findings is a review's job.
- "Drop anything reviewers already raised" — review-cross-check.
- "What feedback is still open on PR 42?" — review-audit.
- "Resolve the threads that are fixed on PR 42" — review-audit.
- "Fix these findings" — review-fix.

## Expected behavior

- One PR review is posted: inline comments plus a summary body; replies to existing threads follow as separate calls only after the review succeeds.
- Every inline comment ends with a source line naming the skill or agent and model; a finding with no stated source is `unattributed`, never a guessed source.
- The summary is headed `Review attestation` and names the reviewed commit, the posting host and model, every distinct finding source and model, and the skills used; any value the session does not reveal is `unknown`.
- A reviewed commit that differs from the PR head, or is unknown, stops the post with two offers: re-verify at head, or post a summary-only attestation naming the reviewed commit (or `unknown`) and the head — not offered when the commit is unknown and there are no findings. The attestation never names a commit that was not reviewed.
- Owner, repo, and host come from the PR's URL, never the working directory's remote; a PR URL on another repository, a fork, or a GitHub Enterprise host (with `--hostname`) is posted there.
- A failing `gh` call stops the run with its error shown.
- With zero findings, the attestation is still posted with `No findings.` — but only with a stated reviewed commit and source; it never attests `Reviewed unknown`.
- The draft shows the target PR's URL, the reviewed commit, and the head, so a bare number that resolved to the wrong repository is caught before posting.
- Critical findings, and any a source marked blocking, lead with `**blocking · <severity>**` and are listed under **Blocking** in the summary.
- Comments are at most three sentences with no greeting, praise, hedging, or narration of how the review ran.
- A finding spanning lines in one hunk posts inline with `start_line`; a suggestion block replaces exactly that range. A finding outside the diff, across hunks, on deleted lines, or with no file:line goes in the summary.
- A finding with a reply target on a review thread is posted as a reply carrying only the addition, attached to the thread's first comment even when the target is a later reply; one targeting a review body or conversation comment becomes a summary bullet linking it.
- With review-cross-check's postable set as input, the attestation is posted even when the set is empty.
- The full draft is always shown; posting waits for approval unless the request already said to post.
- A head that moved since the draft stops the post with the same two offers; `commit_id` is never switched silently.
- The payload is built with a JSON serializer in a scratch directory outside the user's repository.
- A 422 for an out-of-diff line moves that comment to the summary and retries once, reporting the move; before any retry the skill checks the review did not already post, counting only a review whose id was not in its pre-post snapshot, so an earlier review with the same commit and counts is never mistaken for this one. The user's own pending review is never discarded — the user is asked to submit or discard it.
- The review event is `COMMENT` unless the user asks to approve or request changes; approving over blocking entries is confirmed first, and an approve or request-changes rejected on the user's own PR is offered as `COMMENT`, posted only on agreement.
- After a 422 moves comments to the summary, the summary's Findings counts are updated before the retry.
- The URLs of the posted review and every reply are reported, along with any comment moved to the summary or reply that failed.
