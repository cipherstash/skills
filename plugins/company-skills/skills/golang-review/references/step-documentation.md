# Step: documentation

Area 9, low priority. Read this, and golang-practices' `references/project-structure.md` (its examples show doc comments on every exported name) and `references/testing.md` (testable examples), before reviewing the change's documentation. The rule "document every exported name with a comment that starts with the name" is in golang-practices' own rule list. This file says what to report.

## Contents

- [Undocumented exported identifiers](#undocumented-exported-identifiers)
- [Stale documentation](#stale-documentation)
- [Evidence](#evidence)
- [Not a finding](#not-a-finding)

## Undocumented exported identifiers

Report each exported identifier the change adds that has no doc comment: a package-level function, method on an exported type, type, constant, or variable. A doc comment the change adds that does not start with the identifier's name breaks the same rule; group those into one finding. A grouped `const` or `var` block can carry one comment for the group.

Also report a new package with no package comment (`// Package x ...`) in any of its files.

Identifiers in `internal/` packages, `main` packages, and test files are documented for the module's own developers. Report missing comments there only when the repository's own convention requires them.

## Stale documentation

Report text the change makes wrong:

- a doc comment on a changed function that no longer matches what it does, its parameters, its errors, or its concurrency safety;
- README, `doc.go`, or other documentation in the repository that describes the changed behaviour, flags, configuration, or API as it was before the change. Search the repository's Markdown files and doc comments for the changed identifiers, flags, and settings by name;
- a testable example (`ExampleX`) whose `// Output:` the change makes wrong. CI's test run shows that as a failure.

A stale comment is a finding when a reader would be misled: quote the stale text and the line that contradicts it. When the stale text describes a defect another step reports, mention it there instead.

## Evidence

- `go doc -all <package>` in the temporary worktree prints each exported identifier with its comment. An identifier with no indented text under it has none. It runs no code.
- CI's lint does not report missing comments with the suite's config. A repository config that adds `revive`'s `exported` rule does: quote CI's output, as `checks.md` describes.
- Reading the diff and searching the repository's documentation.

## Not a finding

- A doc comment's wording or length, when it is accurate.
- A missing comment on an unexported identifier.
- Documentation of code the change does not touch, unless the change makes it wrong.

Documentation findings are `minor`, unless stale text would lead a user to do something harmful, such as a README that still shows a removed safety flag.
