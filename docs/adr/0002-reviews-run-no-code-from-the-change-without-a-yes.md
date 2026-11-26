# Reviews run no code from the change without a yes

Status: accepted, 2026-11-26

A language's review skill may fetch only its check suite's own tools, at the versions pinned in the practices skill, into `.<lang>-review-tools/`, with install scripts turned off. It never installs the change's dependencies. A check that needs them, such as TypeScript's type-aware lint or Python's mypy, is reported as a limit of the review.

Each language's skills list their execution surface (see GLOSSARY). The review reads tool configuration from the base commit. When the change touches anything on that list, the review runs nothing until the user says yes.

This replaces the "No installs during a review" gotcha in `building-language-pairs`, which contradicted golang-review: golang-review fetches its pinned tools.

## Considered options

- **Fetch nothing, and report every missing tool as a limit.** Rejected: reviews would be weak wherever tools are not already installed.
- **Also allow a frozen dependency install with scripts off.** Rejected: it runs package-manager logic on a lockfile the change controls.
- **Never run any tool on the change, and only quote CI.** Rejected: it loses read-only probes such as Go's API comparison.

## Consequences

Rust's review asks the user more often than Go's, because even `cargo check` runs the change's build scripts.
