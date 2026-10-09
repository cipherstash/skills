---
name: audit-pr-feedback
description: Collate a pull request's existing review feedback — inline threads, review bodies, and conversation comments from people and bots — verify each finding against the PR's head commit, and report which remain unresolved and which are addressed and can be resolved. Use when asked what review feedback is still outstanding on a PR, which review threads can be resolved, or to audit PR comments against the code. Takes a PR number or URL. Does not fix findings (address-code-review), run a new review, or cross-check new findings against the PR (cross-check-review-findings).
argument-hint: "<PR number or URL>"
---

# audit-pr-feedback

Turn a pull request's accumulated review feedback into an audited list of what is still open. A comment is a claim about the code when it was written; every finding earns a **verdict** against the PR's current head, backed by evidence, before it is called unresolved or resolvable.

## Inputs

A PR number or URL. Without one, stop and ask. Nothing is posted, replied to, or resolved without the user's go-ahead.

## Steps

1. **Fetch.** Run this skill's [scripts/pr_feedback.py](scripts/pr_feedback.py) as `python3 <skill dir>/scripts/pr_feedback.py <PR>` and save its JSON to a scratch file — the script documents its fields; it needs `gh` authenticated for the PR's host. A non-zero exit stops the run with gh's error shown to the user. Record the head commit, `pr.headRefOid`. Completion: the JSON is saved and the head commit recorded.

2. **Tree at head.** Verification reads the head commit, never the user's uncommitted work. With `git rev-parse HEAD` equal to the head commit and `git status --porcelain` empty, verify in place. Otherwise fetch from the PR's own repository — `origin` may be a fork — `git fetch https://<host>/<owner>/<name>.git pull/<number>/head`, parsed from `pr.url`; stop if `FETCH_HEAD` is not the head commit (the PR moved mid-fetch: rerun step 1). Then `git worktree add --detach <scratch>/pr-<number> <head commit>` and verify there; never check out, stash, or reset the user's tree. Outside a git repository, ask for a local clone's path. Also fetch each thread's `originalCommit` by sha from the same URL; one that will not fetch (force-pushed away) leaves the thread's `diffHunk` as the record of what the reviewer saw. Remove the worktree on every exit from here on, including a stop or abort. Completion: a tree at exactly the head commit, and its path recorded.

3. **Collate.** Build one ledger of findings from the JSON:
   - In scope: unresolved threads, review bodies, conversation comments. Tally, without entering, resolved threads and minimized comments.
   - One item can carry several findings — a bot review body listing nitpicks, a comment with numbered points: split them. Items carrying none — approvals, praise, answered questions, walkthroughs and summaries, CI or bot status — are tallied by kind.
   - Each entry: an id minted here (F1, F2, …), source URLs, author, where the reviewer looked, the claim, the replies that bear on it (the author's "fixed in abc123", "won't fix", a reviewer's follow-up), and severity normalised to critical/major/minor — P0, blocker, or critical → critical; P1, major, or high → major; P2 and below, minor, nit, or nitpick → minor; unstated → minor — with the original wording kept.
   - Where the reviewer looked: for a thread, `path:line`, or `originalLine` at `originalCommit` once outdated (`line` is null); a `FILE` subject has no line; `side: LEFT` is a line the PR deleted, read in the base. For a review body, the review's `commit`. A conversation comment has none.
   - A `truncated` thread has more replies than fetched; page them from `gh api --paginate repos/<owner>/<name>/pulls/<number>/comments` by `in_reply_to_id` before summarising, since a "fixed in …" reply may be among them.
   - The same issue raised in several items is one entry listing every source, at the higher severity. Order most-severe first.

   Completion: every in-scope item is an entry source or tallied, and every finding appears in exactly one entry.

4. **Verify.** Group entries by the files they cite — an entry citing several by its first — pooling the smallest groups, and entries citing no file into the smallest, until there are at most three. Dispatch one delegate per group in one parallel batch — in Claude Code a `general-purpose` agent; without subagents, work the groups in turn under the same rules. Build each prompt from [references/verify-brief.md](references/verify-brief.md): fill its assignment with the PR URL, the head commit, the tree path, and the group's entries verbatim, and paste the rest unchanged. A prompt naming ids alone arrives empty.

   Then check every return. Read the head lines each `addressed` and `refuted` verdict cites: evidence that does not show the claim's failure removed, or impossible, downgrades the entry to `needs-decision`, the gap as its question. An entry missing from a return, a verdict other than `needs-decision` without head file:line evidence, or a delegate that failed, goes back once; still missing, the entry is `needs-decision`. Completion: every entry has one verdict — `unresolved`, `addressed`, `refuted`, or `needs-decision` — with checked evidence.

5. **Report.** Map every entry to exactly one section, most-severe first within each:
   - **Unresolved** — id, severity (original wording), path:line at head, the claim in one line, the evidence it still holds, source URLs.
   - **Needs decision** — the question, and source URLs.
   - **Addressed, can resolve** — id, the evidence (head file:line, and the fixing commit where found), and the thread to resolve; an entry sourced only from review bodies or conversation comments has no thread and says so.
   - **Refuted** — the evidence; its thread needs a reply stating it before resolving, since resolving silently hides a disagreement.

   Then the tallies from step 3 and the head commit audited. Completion: every ledger entry appears in exactly one section, and every in-scope item is traceable to an entry or a tally.

6. **Act on approval.** Offer to resolve the **Addressed, can resolve** threads. Act only on the user's go-ahead, and first re-run `gh pr view <PR> --json headRefOid`: a head that moved since step 1 stops here — report it and re-verify before resolving. Resolve only those threads, one call per thread id; every `gh api` call adds `--hostname <host>` when the host is not github.com:

   ```sh
   gh api graphql -f query='mutation($id: ID!) { resolveReviewThread(input: {threadId: $id}) { thread { isResolved } } }' -f id=<thread id>
   ```

   Reply to a refuted thread only with text the user approved: `gh api repos/<owner>/<name>/pulls/<number>/comments/<first comment id>/replies -f body=<reply>`. Completion: nothing resolved or posted without approval, and each call's result reported.
