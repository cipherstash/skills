---
name: filing-github-issues
description: Drafts and files GitHub issues on CipherStash repositories — searches open and closed issues in the current repo and its siblings first, verifies every mechanical claim with file:line evidence, picks the right repo (upstream cause versus consumer impact), and writes a Background / Problem / Proposal body in plain wording a reader new to CipherStash can follow. Use when drafting or filing a GitHub issue on a CipherStash repository, or when asked to write up a bug, gap, or proposal as a GitHub issue. Files only when the user asked to file or approves the draft. Not for Linear issues or tickets, and not for pull requests (authoring-pull-requests).
---

# filing-github-issues

Turn a problem into a GitHub issue that a reader who joined yesterday can act on. The issue is a set of claims: each one is checked before it is written, and the draft is shown before anything is filed.

## Inputs

- **The problem**: what breaks, where, and how it was found. Without one, ask.
- **The repository**: `owner/repo`. Default to the current repository's GitHub remote when the problem lives there. When no repository is given and none can be inferred, or the cause may sit in another repo, ask.
- **Mode**: draft by default. File only when the user asked to file the issue, or approves the draft.

Needs the GitHub MCP server's tools: `search_issues`, `issue_read`, `get_label`, `issue_write`, and `add_issue_comment`. Use them for every GitHub step. Fall back to the `gh` CLI (`gh search issues`, `gh label list`, `gh issue create`, `gh issue comment`) only when the MCP server is unavailable, and say so in the report.

## Steps

1. **Search for existing coverage.** Search open *and* closed issues in the target repo *and* each sibling repo the problem might belong to (an upstream library, a consumer of it, a shared SDK). Call `search_issues` with `owner`, `repo`, the symptom in plain words, and `fields: ["number", "title", "state", "state_reason", "html_url", "labels"]`; try two or three wordings. A closed issue that covers the problem is a finding, not a dead end: read it with `issue_read` and check *why* it closed (a linked PR, a shipped release, a silent close). Reopening or commenting often beats a new issue — propose that to the user instead of a duplicate. Completion: each searched repo and query is listed, with any matches and their state.

2. **Verify every mechanical claim** against the code or the installed package before asserting it, and cite `file:line` (or the command and its output). Sort claims into **verified** (you read or ran it) and **plausible** (inferred, not checked). Never present a plausible claim as verified. Completion: every claim in the draft is one or the other.

3. **Pick the right repo.** A problem caused upstream gets its issue upstream. The consumer repo gets its own consumer-impact issue only when it needs its own mitigation. Cross-reference with the full `owner/repo#N` form so links work from both sides. Example: a bug in the SQL that `cipherstash/encrypt-query-language` ships is filed there; a `cipherstash/stack` issue is added only if stack must work around it.

4. **Draft** the title and body following [Structure](#structure) and [Wording](#wording). Pick labels from those already in use: read them off the issues found in step 1, and confirm each with `get_label`. Never invent a label. Show the user the target repo, title, labels, and body, plus the step 1 findings.

5. **File** only on the user's request or approval. Call `issue_write` with `method: "create"`, `owner`, `repo`, `title`, `body`, and `labels`. Report the new issue's URL.

6. **Leave back-links.** For each related issue named in the body, post a short comment on it with `add_issue_comment` pointing to the new issue (`owner/repo#N`), so the link works in both directions. These comments are part of the filing the user approved; list them in the draft.

## Structure

Required sections, in this order:

- **Background** — orient a reader who is new to CipherStash and the product involved. One short paragraph: what the relevant piece does and why it exists. Define every product term and acronym at first use, for example "EQL (Encrypt Query Language) — the SQL library we install into the customer's database as the `eql_v3` schema".
- **Problem** — the mechanism (what actually happens, step by step), then the impact (who hits it, when, how often), then why nothing catches it today. A concrete failure narrative beats an abstraction: "queries slow from instant to scan-every-row, silently", not "performance degradation may occur".
- **Proposal** — numbered, concrete steps. When the full fix is large, include a cheap interim step that could ship first. State the failure behaviour you want, for example "fail loudly, listing the statements — a loud failure beats a silent deletion".

Optional sections, only when they earn their place:

- **Affected versions** — when the problem is version-bounded.
- **Evidence / Verification** — commands run, output observed, `file:line`, with verified and plausible claims marked.
- **Relationship to other work** — links to related issues and PRs, and what each does and does not cover.

## Wording

These rules apply to anything an agent writes on GitHub for a CipherStash repo: issues, pull requests, and comments. Other skills link here instead of restating them.

Plain, always. Assume the reader joined yesterday:

- Short sentences. Plain verbs. No internal shorthand or codenames.
- Expand every acronym at first use, even "obvious" ones (EQL, ZeroKMS, FFI).
- Say what breaks in the user's world, not just in the code's world.
- Titles are symptom-first and name the command or package. For example, `` `stash eql upgrade` silently deletes search indexes — save and restore them `` beats "Improve EQL upgrade robustness".
- Write `#N` **only** for a real GitHub issue or PR. GitHub autolinks every `#N`, so "step #2 of the plan" links to issue 2. Write "step 2" or "item 3" instead. Use `owner/repo#N` for anything in another repo.
- **Never** reference internal Linear issues (`CIP-…` numbers) anywhere on GitHub: issues, PRs, comments, or commit messages. Linear is private and some repos are public. GitHub references are fine.

## Report

The issue URL (or the draft, when not filed), the repos and queries searched with what they found, the labels applied, the back-link comments posted, and any claim left as plausible.

## Boundaries

- Never file, reopen, comment, or edit labels without the user's request or approval of the draft.
- Never create new labels; reuse existing ones.
- Never file a duplicate of an open issue; point the user to it instead.
