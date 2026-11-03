---
name: review-post
description: Posts a finished code review to a GitHub pull request as a single review — one inline comment per finding, tagged with its source, plus an attestation summary naming the commit reviewed, the host, models, and skills, with blocking issues first — posted even when there are no findings. A finding that adds to an existing review thread is posted as a reply on that thread. Use when asked to post, publish, or leave review findings or a review attestation on a PR. Takes a PR number or URL. Does not perform the review, verify findings, cross-check them against existing comments (review-cross-check), or resolve threads (review-audit).
argument-hint: "<PR number or URL> [pasted findings]"
---

# review-post

Publish a review as an **attestation**: a durable record on the PR that a named commit was examined, by what, and what it found. Every review posts one, findings or not. An attestation states only what is known — never a commit that was not reviewed, a source not stated, or a model not used. Comments are terse: the defect, its trigger, the fix.

## Inputs

- A PR number or URL. Without one, stop and ask.
- The findings: this session's review, merged with any pasted. Each carries file:line or range (none for a design-level finding), claim, severity, and source — the skill or agent and the model that produced it. A source not stated is `unattributed`; never guess one. A finding may carry a **reply target** — an existing comment's URL — when it adds to feedback already on the PR (review-cross-check's Adds to existing); it then carries only the addition.
- The **reviewed commit**: the commit the findings were checked against. Take review-cross-check's stated head commit verified; for this session's own review, the commit it read, as recorded when it ran — if it was not recorded, run `git rev-parse HEAD` and `git status --porcelain` now only when nothing in the session has committed, edited, or checked out since the review, and accept HEAD only with a clean tree; for pasted findings, the commit they name. Otherwise it is `unknown`.
- The posting session's provenance: host (Claude Code, Codex), model ID, effort level when one was set. Any value the session does not reveal is `unknown`.

With no review in the session and nothing pasted, ask whether to run a review first, or for the reviewed commit and source of a review done elsewhere. Post a no-findings attestation only with a stated reviewed commit and source.

## Steps

1. **Ledger.** One entry per finding. Normalise severity to critical/major/minor — P0, blocker, or critical → critical; P1, major, or high → major; anything else, or unstated, → minor — keeping the original wording. The same defect reported twice is one entry listing both sources, at the higher severity. An entry is **blocking** when it is critical or a source called it blocking. Order blocking first, then by severity. Completion: every input finding is in exactly one entry.

2. **Resolve the PR.** Run `gh pr view <PR> --json url,headRefOid`. Where `gh` refuses GraphQL — a 403 starting `GitHub GraphQL is not available`, as in Claude Code cloud sessions and scheduled tasks — `gh pr` subcommands fail; use REST: `gh api repos/<owner>/<repo>/pulls/<number>` for a URL, or `gh api repos/{owner}/{repo}/pulls/<number>` for a bare number, reading `html_url` as `url` and `head.sha` as `headRefOid`. Parse host, owner, repo, and number from `url` and use them for every later call — `gh pr diff <url>`, `gh api repos/<owner>/<repo>/…`, with `--hostname <host>` when the host is not github.com — never the working directory's remote, which may be a fork. A non-zero exit from any `gh` call stops the run with gh's error shown; given only a number where `gh pr view` fails, ask for the URL. A bare number resolves against the working directory's default repository, which in a fork can be a different PR with the same number — the draft names the resolved PR so the user can catch it. Compare the reviewed commit with `headRefOid`: when they differ or it is `unknown`, stop and offer to re-verify the findings at head (review-cross-check), or to post a summary-only attestation naming the reviewed commit and the current head, every entry as a summary bullet. With the reviewed commit `unknown`, that attestation reads `Reviewed commit unknown`; with no findings as well, do not offer it — ask for the reviewed commit instead. Completion: host, owner, repo, number, and head recorded, and the reviewed commit equals head or the user chose the summary-only attestation.

3. **Place.** Read the diff with `gh pr diff <url>`, or under the REST fallback `gh api repos/<owner>/<repo>/pulls/<number> -H 'Accept: application/vnd.github.diff'`; when it is too large, page `gh api --paginate repos/<owner>/<repo>/pulls/<number>/files` and read each file's `patch`, a file without one being outside the diff. Each entry is exactly one of:
   - **reply** — its reply target is a review thread comment (`#discussion_r<id>`).
   - **inline** — every line it cites is an added or context line in one hunk on the new side of the diff, under the file's new path; a range is inline as `start_line`..`line`.
   - **summary** — everything else: no file:line, lines outside the diff or spanning hunks, deleted lines, a reply target that is a review body (`#pullrequestreview-<id>`) or conversation comment (`#issuecomment-<id>`), and every entry of a summary-only attestation.

   Completion: every entry is reply, inline, or summary.

4. **Draft.** Write each inline comment:

   ```markdown
   **blocking · critical** `parse()` returns `None` on an empty header, so `auth()` admits the request. Return `Err(Invalid)` instead.

   <sub>Source: code-review · claude-opus-5-5</sub>
   ```

   Lead with `**blocking · <severity>**` or `**<severity>**`. At most three sentences, identifiers in backticks, no hedging, praise, or narration. A ```` ```suggestion ```` block only when the replacement is exact and complete; its content replaces exactly the commented lines, `start_line` through `line`. A reply uses the same format with only the addition — never restating, agreeing with, or crediting the existing comment.

   Write the summary:

   ```markdown
   ## Review attestation

   Reviewed `<reviewed short sha>` · posted from Claude Code · `claude-opus-5-5` · effort high
   Sources: code-review · claude-opus-5-5; security agent · gpt-5.2-codex
   Skills: `code-review`, `rust-security`

   **Blocking (1)**
   - `src/auth.rs:42` empty header admits the request

   **Findings (3):** 1 critical, 1 major, 1 minor — 2 inline, 1 below.

   - `src/lib.rs:7` (outside diff) **minor** `Config` derives `Debug` over `api_key`.
   ```

   **Sources** lists every distinct source and model across the ledger; **Skills** is the union of the skills they used. The **Findings** line counts every entry and how it was placed — inline, below, or in reply. Omit **Blocking** when there are none. Summary entries follow as bullets in the inline comment's format, led by `path:line`, the file alone, or `general`, and link their reply target when they have one. A summary-only attestation adds `Head is now <head short sha>; findings were not re-checked against it.` With no findings, the body after the provenance lines is `No findings.` Completion: every entry appears once — reply, inline, or summary bullet — and every blocking entry is also listed under **Blocking**.

5. **Confirm.** Always show the target PR's URL, the reviewed commit, and the head above the full draft — summary, inline comments with their `path:line`, and replies with their target URL — in one fenced block whose fence is longer than any fence inside it (````` ```` ````` around suggestion blocks). Wait for approval, unless the request already said to post, in which case post right after showing it. An `APPROVE` request with blocking entries is flagged above the draft and always waits for approval. Completion: the draft was shown and posting is approved.

6. **Post.** Read [references/posting.md](references/posting.md) and follow it: re-check the head, build the payload with a serializer in a scratch directory, post one review, handle a rejection, then post the replies. Completion: the URL of the review and of each reply reported, and any comment moved to the summary or reply that failed named.
