# Advisory checks report without blocking

Status: accepted, 2026-11-27

Some evidence helps a review but would make a bad gate. A public API comparison is one example: a PR that removes a function on purpose would fail. So a language may pin a tool as an advisory check (see GLOSSARY). CI runs it on every pull request and reports its result, but the result never blocks the merge. The review quotes the result and judges it. Python's first advisory check is `griffe check`.

The Python skills' grill made this decision on the Python ticket, [#64](https://github.com/cipherstash/skills/issues/64). [#152](https://github.com/cipherstash/skills/issues/152) added it to the shared text.

## Considered options

- **Make it a check suite check.** Rejected: it fails every intended API break, so teams would need an override, and an override weakens the check.
- **A tool only the review fetches.** Rejected: it needs ADR 0002 amended, and the evidence depends on the reviewer's machine and is seen only in the review.
- **Read the API diff by hand.** Kept as the fallback when a repository has no advisory check. It misses signature changes that a tool would catch.

## Consequences

`checks.md` gains a second table for advisory checks, so the shared drift parser does not change. A failed advisory check never blocks, so it is easy to ignore. The review is what keeps it visible.
