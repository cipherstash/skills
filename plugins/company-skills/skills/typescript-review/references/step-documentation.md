# Step: documentation

Area 10, low priority. Read this, and typescript-practices' `references/project-structure.md` (its section on documentation comments), before reviewing the change's documentation. The rule "give every export of a published package a documentation comment" is also in typescript-practices' own rule list. This file says what to report.

## Contents

- [Undocumented exports](#undocumented-exports)
- [Stale documentation](#stale-documentation)
- [Evidence](#evidence)
- [Not a finding](#not-a-finding)

## Undocumented exports

A package is published when its `package.json` does not set `"private": true`. Its public exports are what its `exports` map's entry points export, directly or through `export *` and `export { … } from`. Report each export the change adds to a published package that has no `/** */` documentation comment: a function, class, method of an exported class, type, interface, or constant. A `//` comment, or a `/* */` comment without the second `*`, does not count: editors and documentation tools read only `/** */`.

Report too a documentation comment the change adds that leaves out what the caller must know and the signature does not say: that it returns a result union and which failures, the errors it throws, the units of a number, or that it takes an `AbortSignal`.

In a private package, or a module no entry point exports, report missing comments only when the repository's own convention requires them.

## Stale documentation

Report text the change makes wrong:

- a documentation comment on a changed function that no longer matches what it does, its parameters, its failures, or what it throws;
- an `@param` for a parameter that was renamed or removed, or an `@deprecated` that names a replacement the change removes;
- a README or other documentation in the repository that describes the changed behaviour, options, configuration, or API as it was before the change. Search the repository's Markdown files and documentation comments for the changed names, options, and settings.

A stale comment is a finding when a reader would be misled: quote the stale text and the line that contradicts it. When the stale text describes a defect another area reports, mention it there instead.

## Evidence

- Reading the diff: for each new export, the line above its declaration. Follow the entry point's `export *` lines to know which modules are public.
- Searching the repository's documentation for the changed names.
- The declaration comparison that the breaking changes area describes, when it ran, lists every export at the head with its comment.

## Not a finding

- A documentation comment's wording or length, when it is accurate.
- A missing comment on a declaration that is not exported, or on a test file.
- Documentation of code the change does not touch, unless the change makes it wrong.

Documentation findings are `minor`, unless stale text would lead a user to do something harmful, such as a README that still shows a removed safety option.
