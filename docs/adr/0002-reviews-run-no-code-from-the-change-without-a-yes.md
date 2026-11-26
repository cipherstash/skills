# Reviews run no code from the change without a yes

Status: accepted, 2026-11-26. Amended 2026-11-27. The amendment states who runs checks, and which tools wait for a yes.

CI runs the check suite, and CI is the hard gate on every pull request. An agent is never responsible for running checks. A review confirms that each check is in place and quotes CI's results.

An agent may run a tool when the tool gives useful insight or analysis. A language's review skill may fetch only its check suite's own tools, at the versions pinned in the practices skill, into `.<lang>-review-tools/`, with install scripts turned off. It never installs the change's dependencies. A tool that needs them, such as TypeScript's type-aware lint or Python's mypy, is reported as a limit of the review.

Each language's skills list their execution surface (see GLOSSARY). The review reads tool configuration from the base commit. The change may touch anything on that list. Then the agent runs no tool that would run the change's code, such as its tests or build scripts, until the user says yes. A tool that only reads the code may still run.

For example, a change to a `.syso` file makes golang-review hold back `go test`. golang-review still runs `go vet`, because vet does not link.

This replaces the "No installs during a review" gotcha in `building-language-pairs`, which contradicted golang-review: golang-review fetches its pinned tools. #128 makes that change to the gotcha.

## Considered options

- **Fetch nothing, and report every missing tool as a limit.** Rejected: reviews would be weak wherever tools are not already installed.
- **Also allow a frozen dependency install with scripts off.** Rejected: it runs package-manager logic on a lockfile the change controls.
- **Never run any tool on the change, and only quote CI.** Rejected: it loses read-only probes such as Go's API comparison.

## Consequences

Rust's review asks the user more often than Go's, because even `cargo check` runs the change's build scripts.
