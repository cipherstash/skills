# Settle shared language decisions once

Status: accepted, 2026-11-26

Building the Go skills showed that questions common to every language get answered again, and differently, in each language's design. The TypeScript, Python and Rust reports raised 45 open decisions, and 17 of them were the same 15 questions. So the work runs as a loop:

1. Research each language and list its open decisions.
2. Sort the decisions into shared ones and language-only ones. Settle the shared ones in one grill, before any language grill.
3. A grill writes only GLOSSARY entries and ADRs, and stops at shared understanding. A spec and tickets come next. No code is written before tickets are labelled `ready-for-agent`.
4. Save each language's research and grill outcome as comments on its parent ticket, so a resumed session finds them.
5. Shared text (CONTRIBUTING, GLOSSARY, the process skill) changes only in the shared tickets. A language's PRs touch only its own skill directories, its own CI job and its own drift test. The version bump happens only in each main PR, after merging `main`. The release ticket PR, which replaces an upstream plugin, also updates the catalogs, the company-skills dependencies and the README, as CONTRIBUTING requires. Languages then build at the same time.
6. Before a PR merges, every review finding deferred from it is filed as an issue and linked from the PR body.
7. When a language's main PR is open, file one issue listing that run's deviations and process findings. That issue starts the next pass.

Scope stays narrow. A language's skills do not roll their check suite out to other repositories; the review's "missing check" lines are each repository's backlog. A language's skills cover its files wherever they are, such as JavaScript in TypeScript repositories or Python scripts in Rust repositories. SHA-pinned actions and zizmor are not part of any language's suite. They get one ticket covering every language.

## Considered options

- **Grill each language on its own.** Rejected: the reports already disagreed on seeds and pins.
- **Build the languages one after another.** Rejected: it takes three times as long. The shared-files rule removes most conflicts.
- **Each language's skills fix the company repositories.** Rejected: each language would grow into a migration project.

## Consequences

A language that finds a gap in shared text needs a separate ticket for it. Each language adds one stop for the person: its grill.
