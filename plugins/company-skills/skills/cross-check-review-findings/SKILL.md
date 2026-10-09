---
name: cross-check-review-findings
description: Verify new code review findings — this session's review or ones pasted from parallel agents — against a pull request's head, cross-check the confirmed ones against the PR's existing review feedback, keep only findings that are new or materially add to existing ones, and draft a concise PR review response. Use after reviewing a PR, or when asked to check findings against existing PR comments, drop findings reviewers already raised, or draft a PR review from findings. Takes a PR number or URL. Does not perform the review, fix code, or post anything without approval.
argument-hint: "<PR number or URL> [pasted findings]"
---

# cross-check-review-findings

Turn a fresh set of review findings into a PR response that says only what the existing review has not. Every finding earns a **verdict** against the PR's head before it is cross-checked, and every confirmed finding is matched against what reviewers already posted, so the response carries no false finding and no repeat.

## Inputs

- A PR number or URL. Without one, stop and ask.
- The new findings: those already in this session's context (a review run earlier in the conversation), merged with any pasted into the invocation. With neither, stop and ask for findings — producing them is a review's job.

Nothing is posted without the user's go-ahead.

## Steps

1. **Ledger.** Merge the new findings into one ledger: an id minted here (N1, N2, …), file:line, claim, failure scenario, severity, sources. Normalise severity to critical/major/minor — P0, blocker, or critical → critical; P1, major, or high → major; P2 and below, minor, nit, or nitpick → minor — keeping the original wording. The same defect reported twice is one entry listing both sources, at the higher severity. Order most-severe first. Completion: every input finding appears in exactly one entry.

2. **Fetch.** Run this skill's [scripts/pr_feedback.py](scripts/pr_feedback.py) as `python3 <skill dir>/scripts/pr_feedback.py <PR>` and save its JSON to a scratch file — the script documents its fields; it needs `gh` authenticated for the PR's host. A non-zero exit stops the run with gh's error shown to the user. Record the head commit, `pr.headRefOid`. Completion: the JSON is saved and the head commit recorded.

3. **Tree at head.** Verification reads the head commit, never the user's uncommitted work. With `git rev-parse HEAD` equal to the head commit and `git status --porcelain` empty, verify in place. Otherwise fetch from the PR's own repository — `origin` may be a fork — `git fetch https://<host>/<owner>/<name>.git pull/<number>/head`, parsed from `pr.url`; stop if `FETCH_HEAD` is not the head commit (the PR moved mid-fetch: rerun step 2). Then `git worktree add --detach <scratch>/pr-<number> <head commit>` and verify there; never check out, stash, or reset the user's tree. Outside a git repository, ask for a local clone's path. Remove the worktree on every exit from here on, including a stop or abort. Completion: a tree at exactly the head commit, and its path recorded.

4. **Existing feedback.** Build a second ledger from the JSON: every review thread — resolved ones included, marked resolved — every review body, and every conversation comment, the user's own earlier comments included. Skip minimized comments. Split an item carrying several findings — a bot body listing nitpicks — into one entry each; skip items carrying none — approvals, praise, summaries, bot status. Each entry: an id (E1, E2, …), source URL, author, path:line — `originalLine` once a thread is outdated, with its `diffHunk` — the claim, its fix if one is suggested, the replies that bear on it, resolved or not. Page a `truncated` thread's remaining replies from `gh api --paginate repos/<owner>/<name>/pulls/<number>/comments` by `in_reply_to_id`. The viewer's unsubmitted review is excluded by the script. Existing entries are not verified here; auditing them is audit-pr-feedback's job. Completion: every non-minimized item is an entry source or skipped as carrying no finding.

5. **Verify.** Group new entries by the files they cite — an entry citing several by its first — pooling the smallest groups, and entries citing no file into the smallest, until there are at most three. Dispatch one delegate per group in one parallel batch — in Claude Code a `general-purpose` agent; without subagents, work the groups in turn under the same rules. Build each prompt from [references/verify-brief.md](references/verify-brief.md): fill its assignment with the PR URL, the head commit, the tree path, and the group's entries verbatim, and paste the rest unchanged. A prompt naming ids alone arrives empty.

   Then check every return. Read the head lines each `confirmed` and `refuted` verdict cites: evidence that does not show the failure, or its impossibility, downgrades the entry to `needs-decision`. An entry missing from a return, a verdict other than `needs-decision` without head file:line evidence, or a delegate that failed, goes back once; still missing, the entry is `needs-decision`. Apply each confirmed entry's corrections — line, scope, affected sites, fix. A different defect a delegate reports alongside becomes its own `needs-decision` entry, never part of the confirmed one. Completion: every new entry is `confirmed`, `refuted`, or `needs-decision`, with checked evidence.

6. **Cross-check.** Match each `confirmed` entry against the existing ledger. A match is the same defect — the same root cause and failure — not merely the same file or line; one existing entry can cover several new ones, and one new entry can span several existing ones. Each confirmed entry gets one outcome:
   - `new` — no existing entry reports the defect.
   - `covered` — an existing entry reports it and the new entry adds nothing material. Dropped from the response.
   - `covered+` — an existing entry reports it, and the new entry adds material content. Record the addition alone, against the existing entry.

   An existing entry covers a new one only if it reports the same failure; existing entries are unverified, so a wrong or vaguer one does not swallow a correct finding — that is `covered+`. An existing entry its thread dismissed — "intentional", "won't fix", withdrawn — still covers the defect: `covered+` only with evidence the dismissal did not weigh, otherwise `covered`. A `covered+` addition attaches to one existing entry: an unresolved thread first, then a resolved thread, then a review body or conversation comment.

   Material content changes what the author would fix, where, or how urgently: a concrete trigger where the existing entry has none, further affected sites, a different root cause, a fix where the existing suggestion is wrong or incomplete, higher severity with evidence, or a resolved thread whose defect is still present at head. Rewording, extra explanation, and agreement are not material. Completion: every confirmed entry has one outcome, and every `covered` or `covered+` entry names the existing entries it matched.

7. **Report and draft.** Report the ledger to the user, every new entry once:
   - **New** — id, severity, head file:line, the defect in one line, evidence.
   - **Adds to existing** — id, the existing comment's URL, the addition.
   - **Already covered** — id and the existing comment's URL.
   - **Refuted** — id and evidence.
   - **Needs decision** — id and the question.

   Then draft the PR response from the **New** and **Adds to existing** entries only, following [references/draft-response.md](references/draft-response.md), and show it in a code block. With neither, there is no draft: say the existing review already covers every confirmed finding, or, with nothing confirmed, that no finding survived verification. Completion: every input finding is traceable to one report section through its entry, and the draft holds nothing from Already covered, Refuted, or Needs decision.

8. **Post on approval.** Post only the draft the user approved, only on their go-ahead, as [references/draft-response.md](references/draft-response.md) describes; a head that moved since step 2, or an unsubmitted review of the user's own on the PR, stops the post. Completion: nothing posted without approval, and each posted review and reply reported by URL.
