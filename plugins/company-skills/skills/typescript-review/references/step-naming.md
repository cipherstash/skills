# Step: naming and style

Area 6, medium priority. Read this, and typescript-practices' `references/project-structure.md` (its sections on module format and on naming and style), before reviewing names, imports, and formatting in the change. typescript-practices' own rule list also holds the naming rules. This file says what to report and how.

## Contents

- [What to report](#what-to-report)
- [Formatting](#formatting)
- [Severity](#severity)
- [Not a finding](#not-a-finding)

## What to report

In names and exports the change adds or renames:

- **Case**: a type, interface, class, or `enum` not in `PascalCase`; a function, value, or parameter not in `camelCase`; `snake_case` or `SCREAMING_CASE` names other than a constant the repository already writes that way.
- **Prefixes**: an interface or type prefixed with `I`, such as `IKeyStore`, or suffixed with `Interface`; a type parameter not named `T` or a word starting with `T`.
- **Acronyms**: an acronym in capitals inside a name, such as `keyID`, `parseJSON`, or `HTTPClient`, where the rule writes `keyId`, `parseJson`, and `HttpClient`.
- **Booleans**: a boolean not named as a question, such as `valid` for `isValid`.
- **Files**: a new file not in `kebab-case`, or not named after what it exports.
- **Exports**: a default export, other than in a file a tool requires to have one, such as `vitest.config.ts`.
- **Imports**: a type imported without `import type` or an inline `type` modifier, which `verbatimModuleSyntax` makes a compile error or a runtime import; a relative import without the `.js` extension under `module: "nodenext"`; `require` or `__dirname` in an ES module.

Group repeats of one problem into one finding that lists every location.

## Formatting

Biome formats every file, so formatting is Biome's to report, not the reviewer's. Run it as `checks.md` describes, with the base commit's configuration, and report each file it says is not formatted, quoting its diff. Never run Biome with `--write`. When Biome could not run, do not report layout by reading: record the limit.

## Severity

Naming and style findings are `minor`: they break a rule and have no runtime consequence. An import that `verbatimModuleSyntax` turns into a runtime import of a module with side effects can have one: report that consequence, and its severity, under the area it belongs to. A rename that breaks callers outside the package belongs to the breaking changes area, which sets its own severity.

## Not a finding

- A name in code the change does not add or rename.
- A short name in a short scope, such as `i` or `key`.
- A name that follows the repository's own documented convention where it differs from typescript-practices. Say which convention you followed.
- A naming or layout preference with no rule behind it.
- An error message's wording. Report it only when it breaks a rule, such as a secret in the message, under the area that rule belongs to.
