# Step: naming and style

Area 5, medium priority. Read this, and golang-practices' `references/project-structure.md` (its section on naming packages and identifiers) and `references/interfaces.md` (interface names), before reviewing names and formatting in the change. golang-practices' own rule list also holds the naming rules. This file says what to report and how.

## Contents

- [What to report](#what-to-report)
- [Formatting](#formatting)
- [Severity](#severity)
- [Not a finding](#not-a-finding)

## What to report

In names the change adds or renames:

- **Packages**: not short, lower-case, one word; or named `util`, `common`, `helpers`, `misc`, `base`, or `models`.
- **Stutter**: an exported name that repeats its package, such as `user.UserService`.
- **Case**: `snake_case` or `ALL_CAPS` identifiers; initialisms in mixed case, such as `userId`, `baseUrl`, `ServeHttp`, `Json`.
- **Receivers**: `this` or `self`; a long receiver name; different receiver names on methods of one type.
- **Getters and errors**: a `Get` prefix on a getter; an error variable not named `ErrX`, or an error type not named `XError`.
- **Interfaces**: an `I` prefix or `Interface` suffix; a one-method interface named neither for its method plus `-er` (`Reader`) nor for its role (`http.Handler`, `Mailer`).
- **Error strings**: starting with a capital letter (unless a proper noun or acronym) or ending with punctuation.
- **Build tags**: `// +build` lines, or more than one `//go:build` line in a file.

Group repeats of one problem into one finding that lists every location.

## Formatting

Run `gofmt -l` over the changed `.go` files that still exist at the head, as `checks.md` describes. Each file it lists is a finding: quote the lines `gofmt -d` changes. Never run `gofmt -w`: the review changes no file. If the repository uses `goimports` or `gofumpt` and it is installed, its `-l` output counts the same way; if not installed, `gofmt` alone is the check.

## Severity

Naming and style findings are `minor`: they break a rule and have no runtime consequence. A rename that breaks importers belongs to the breaking-changes step, which sets its own severity.

## Not a finding

- A name in code the change does not add or rename.
- A short name in a short scope, such as `i`, `r`, or `buf`.
- A name that follows the repository's own documented convention where it differs from golang-practices. Say which convention you followed.
- A naming preference with no rule behind it.
