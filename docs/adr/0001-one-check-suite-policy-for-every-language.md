# One check suite policy for every language

Status: accepted, 2026-11-26

The TypeScript, Python and Rust research reports each proposed rules for their check suites, and two of them disagreed. We settled the rules that apply to every language once, so each language's grill only picks its tools and versions:

- A parser of untrusted input needs a fuzz target or a property test. The language's `checks.md` names which, or says why none fits.
- In pull request CI, fuzz and property tests use fixed inputs: they replay the seed corpus, or run a derandomized profile with a bounded number of examples, as Go's CI replays only its `f.Add` seeds. Random and long runs go on a schedule.
- A version is pinned when it is exact, or fixed by a committed lockfile that CI installs frozen or locked. A range with no frozen install does not count.
- Coverage is reported with no threshold. Coverage gates such as CRAP stay in the repository that wants them, so #69 is work for the Rust repositories.
- semgrep has one pin, shared by every language, and every language's pin moves in one PR. The ruleset floats. Before pinning, check that the language's `p/<lang>` ruleset exists.
- References state the minimum language version they target. CI floats the latest stable or LTS release.
- "In place" is defined once, for every language (see GLOSSARY). A path-filtered trigger counts only alongside a changes job that fails closed. A `continue-on-error` step followed by a step that enforces its result does not count.
- A language's review skill may add areas beyond Go's ten when a suite tool gives evidence for the area and the review fixture can plant a defect in it. The spec records why.
- Every language's drift test uses one shared parser for the pinned-versions table.

## Considered options

- **Exact versions only.** Rejected: it fails repositories that pin through lockfiles, such as stashctl, and Go already counts a `go.mod` tool directive.
- **A coverage threshold per language.** Rejected: it fails unrelated PRs whenever coverage dips.
- **One semgrep pin per language.** Rejected: the pins drift apart.
- **Random fuzz and property inputs in pull request CI, with the seed printed.** Rejected: an unrelated PR could fail on a newly found input.
- **Exactly ten review areas.** Rejected: Python's type checking would have to fold into Correctness.

## Consequences

Some existing repositories will show more missing checks, because path filters and enforce-later steps no longer count as in place. Moving the semgrep pin touches every language at once.
