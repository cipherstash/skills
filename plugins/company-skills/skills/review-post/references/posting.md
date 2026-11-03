# Posting the review

Read this at the Post step, after the draft is approved. `<host>`, `<owner>`, `<repo>`, `<number>`, and the head come from the Resolve step. Add `--hostname <host>` to every `gh api` call when the host is not github.com. A non-zero exit not covered below stops the run with gh's error shown.

## 1. Re-check the head

Run `gh pr view <url> --json headRefOid` — under SKILL.md's REST fallback, `gh api repos/<owner>/<repo>/pulls/<number> --jq .head.sha`. A head that moved since the Resolve step stops the post — the draft covers an older commit. Report the new head and offer to re-verify the findings there (review-cross-check) and redraft, or to redraft as a summary-only attestation naming the reviewed commit and the new head — SKILL.md's Place step onward, shown again before posting. The same holds for an approved summary-only attestation: refresh its `Head is now` line and show it again. Never switch `commit_id` silently.

## 2. Build the payload

Write files under a scratch directory outside the user's repository, never in it. Build the JSON with a serializer — `jq -n --arg` or `python3 -c 'import json, …'` — never by pasting text into a JSON string by hand; comment bodies hold backticks, quotes, newlines, and fences.

```json
{
  "commit_id": "<head commit>",
  "event": "COMMENT",
  "body": "<summary>",
  "comments": [
    {"path": "src/auth.rs", "line": 42, "side": "RIGHT", "body": "<comment>"},
    {"path": "src/db.rs", "start_line": 10, "start_side": "RIGHT", "line": 14, "side": "RIGHT", "body": "<comment>"}
  ]
}
```

`path` is the file's new path. A range sets `start_line` and `start_side` with `start_line` below `line`, both in the same hunk. `event` is `REQUEST_CHANGES` or `APPROVE` only when the user asked; otherwise `COMMENT`. A summary-only attestation has an empty `comments` array; its `commit_id` is still the head, because GitHub anchors every review to a PR commit, so its body is the record of what was reviewed.

## 3. Post one review

Record the posting account first: `gh api user --jq .login`. Then snapshot the ids of that account's existing reviews, so a retry can tell this attempt's review from an earlier one with the same commit and counts:

```sh
gh api --paginate repos/<owner>/<repo>/pulls/<number>/reviews --jq '.[] | select(.user.login == "<login>") | .id' > <scratch>/reviews-before.txt
```

Then post:

```sh
gh api --method POST repos/<owner>/<repo>/pulls/<number>/reviews --input <scratch>/review.json
```

The response's `html_url` is the review URL.

## 4. Handle a rejection

Before any retry — after a rejection, a timeout, or a 5xx — list the account's reviews and check whether this attempt already posted, since a timed-out request may have succeeded:

```sh
gh api --paginate repos/<owner>/<repo>/pulls/<number>/reviews --jq '.[] | select(.user.login == "<login>") | {id, html_url, commit_id, body}'
```

Only a review whose `id` is not in `reviews-before.txt` can be this attempt; an older review with the same commit, provenance, and counts is never taken as it. A new review at the head commit whose provenance and **Findings** lines match the summary's is the posted review — GitHub may normalise whitespace, so do not compare the body byte for byte: do not post again. A new review that does not match was posted by something else at the same time: report it and ask before posting. Otherwise read the 422's message:

- **A line or path not in the diff** — move the comments it names into the summary as bullets; when it names none, move every inline comment whose placement is in doubt (a range, a renamed file, a context line far from a change), and if none is, move them all. Add the moved comments as summary bullets and update the **Findings** counts. These moves are pre-approved; report each one.
- **A pending review of the user's own** — GitHub allows one per PR. Ask the user to submit or discard it in GitHub; never discard it for them.
- **Approving or requesting changes on the user's own PR** — offer to post as `COMMENT` instead, and post only on the user's agreement.
- **`commit_id` not part of the PR** — the PR changed under the draft: return to step 1.

Retry once — a retry after the user submits or discards a pending review, or agrees to `COMMENT`, is that one retry. A second failure stops the run with the error shown and the payload's path, so nothing is lost.

## 5. Post the replies

Only after the review has posted, post each reply. A reply attaches to the thread's first comment; the target may be any comment in the thread, so resolve it first:

```sh
gh api repos/<owner>/<repo>/pulls/comments/<id> --jq '.in_reply_to_id // .id'
gh api --method POST repos/<owner>/<repo>/pulls/<number>/comments/<first comment id>/replies -F body=@<scratch>/reply-<n>.md
```

`<id>` is the number in the target's `#discussion_r<id>`. Each reply is its own call: report each one's URL (`html_url`) or error. A failed reply never re-posts the review; offer to retry that reply alone.
