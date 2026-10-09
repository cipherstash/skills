# Draft PR response

Read this before drafting the response and again before posting it.

## Contents

- Shape
- Writing rules
- Templates
- Presenting the draft
- Posting on approval

## Shape

One pull request review, plus replies to existing threads:

- **Inline comment** — a `new` finding whose line is in the PR's diff at head (`gh pr diff <number>` hunks, right side).
- **Review body** — a `new` finding whose line is outside the diff, one bullet each, led by `path:line`.
- **Thread reply** — a `covered+` addition to an existing review thread, posted on that thread.
- **Review body, linked** — a `covered+` addition to a review body or conversation comment, which have no thread: one bullet linking the existing comment.

Nothing else goes in: no greeting, summary, verdict line, or sign-off. With no `new` finding and no `covered+` addition, there is no draft — report that the existing review already covers every confirmed finding.

## Writing rules

- Include only `new` findings and `covered+` additions. Never a refuted, needs-decision, or plain `covered` finding.
- Each comment states a concrete, actionable defect: what is wrong, the trigger that shows it, and the fix when one is clear.
- At most three sentences. Code identifiers in backticks. A ```` ```suggestion ```` block only when the replacement is exact and complete.
- A thread reply carries only the addition. Do not restate the existing comment, agree with it, or credit it.
- No exposition: no background, no explanation of how the finding was found, no mention of reviews, agents, tools, or verification, no thoughts or feelings, no hedging ("might", "consider", "perhaps"), no praise.
- Severity leads each `new` finding in bold: `**critical**`, `**major**`, or `**minor**`. A thread reply leads with it only when its addition is higher severity.

## Templates

Inline comment or review-body bullet:

```markdown
**major** `parseConfig` returns `undefined` when `timeout` is `0`, so `connect()` waits forever. Check `timeout === undefined` instead of falsiness.
```

Thread reply, additional sites:

```markdown
Same defect in `src/client.ts:88` and `src/pool.ts:41`.
```

Thread reply, resolved but still present:

```markdown
Still present at abc1234: `retry()` still swallows the `AbortError` at `src/retry.ts:57`.
```

Thread reply, different root cause:

```markdown
Root cause is `normalize()` dropping the trailing slash (`src/path.ts:23`); guarding the caller leaves `resolve()` and `join()` affected.
```

## Presenting the draft

Show the draft to the user in one code block, grouped under `Review body`, `Inline comments` (each led by `path:line`), and `Thread replies` (each led by the existing comment's URL). Save the review payload and the replies to scratch files for posting.

## Posting on approval

Post only on the user's explicit go-ahead, and only the draft they approved.

Every `gh api` call adds `--hostname <host>` when the host is not github.com.

1. Re-run `gh pr view <PR> --json headRefOid`. A head that moved since verification stops the post: the findings were verified against an older commit. Re-run the feedback script too: `pendingReview: true` stops the post — GitHub allows one unsubmitted review per user, so the user submits or discards theirs first.
2. Check every inline comment's `line`, and `start_line`, against `gh pr diff <number>`: each must be a right-side line of the same hunk. Move any that is not to the review body. GitHub's 422 rarely names the failing comment.
3. With a review body or any inline comment, post the review: `gh api repos/<owner>/<repo>/pulls/<number>/reviews --input <payload.json>`, the payload being:

   ```json
   {
     "commit_id": "<head commit>",
     "event": "COMMENT",
     "body": "<review body, or empty>",
     "comments": [
       {"path": "src/config.ts", "line": 42, "side": "RIGHT", "body": "<comment>"},
       {"path": "src/pool.ts", "start_line": 10, "line": 14, "start_side": "RIGHT", "side": "RIGHT", "body": "<comment>"}
     ]
   }
   ```

   Use `event: "REQUEST_CHANGES"` or `"APPROVE"` only when the user asks. With only thread replies, post no review: an empty one is rejected.
4. Post each thread reply: `gh api repos/<owner>/<repo>/pulls/<number>/comments/<comment id>/replies -f body=<reply>`, where the comment id is the thread's first comment `id` from the fetched JSON.
5. Report the URL of the review and of each reply.
