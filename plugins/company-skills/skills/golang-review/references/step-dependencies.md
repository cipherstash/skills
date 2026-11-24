# Step: dependency management

Area 8, medium priority. Read this, and golang-practices' `references/dependencies.md` and the section on the `go.mod` file in `references/project-structure.md`, before reviewing changes to `go.mod`, `go.sum`, `go.work`, vendored modules, or imports. The practices references hold the rules and commands. This file says what to look for, how to get evidence without changing the tree or fetching anything unasked, and what is not a finding.

## Contents

- [What to report](#what-to-report)
- [Untidy module files](#untidy-module-files)
- [Known vulnerabilities](#known-vulnerabilities)
- [Severity](#severity)
- [Not a finding](#not-a-finding)

## What to report

- **An untidy module file**: a requirement nothing imports, an import with no requirement, or `go.sum` out of step with `go.mod`. See [Untidy module files](#untidy-module-files).
- **Dependencies with known vulnerabilities**: see [Known vulnerabilities](#known-vulnerabilities).
- **A `replace` that points at a local path outside the repository**, such as `=> ../mylib`, and a `go.work` file the repository did not track before. Builds outside the author's machine cannot see that path. A `replace` to a directory inside the repository is committed with it, so every clone builds; it is not a finding on its own (see [Not a finding](#not-a-finding)).
- **`go.mod` changed without `go.sum`**, or the reverse, when a requirement changed.
- **Many modules updated in one change**, as `go get -u ./...` does, with no reason given. The change cannot be reviewed module by module.
- **A new dependency** where the standard library or an existing dependency already does the job, or one that is archived or below `v1` with no reason in the change.
- **A raised `go` or `toolchain` line** together with dependency updates, or with no note of the behaviour that changes, such as per-iteration loop variables from Go 1.22.
- **A major-version upgrade** treated as an update: the import path must change to `/vN`, and the change must handle the API differences.

## Untidy module files

`go mod tidy` would rewrite the files, so the review never runs it. With a local toolchain at Go 1.23 or later, `checks.md` runs `go mod tidy -diff` in the temporary worktree: it prints the changes tidy would make and changes nothing. A non-zero exit with a diff is evidence: quote the lines it adds or removes. It uses the local module cache only, under `GOPROXY=off` and `GOSUMDB=off`; if it fails because a module is missing from the cache, that is a limit, not a finding.

With an older local toolchain, `go mod tidy -diff` does not exist. Record the tidy check as not run, and review by reading: compare the `require` lines with the imports in the module's `.go` files (`go list -deps -test -f '{{with .Module}}{{.Path}}{{end}}' ./...` lists the modules the packages use, without changing anything) and name any requirement nothing imports.

## Known vulnerabilities

CI runs `govulncheck` as part of the Go check suite; the review never runs it. Read its result for the head as `checks.md` describes. When it failed, report each vulnerability in a function the code calls as a finding, with its ID, the module and version, the "Fixed in" version, and the call path it prints. Vulnerabilities only in imported packages or required modules, which the code does not call, go under the checks as context. A standard-library vulnerability fixed in a newer Go than the local toolchain is caused by the build's toolchain, not by the change, unless the change lowers the `toolchain` line: report it under the checks.

Without a CI `govulncheck` result for the head, review a change that adds or updates a dependency by reading: name the module and version, and say the vulnerability check is a limit.

## Severity

- `critical`: a known vulnerability in a function the code calls with untrusted input.
- `major`: a known vulnerability the code calls, with no shown path from untrusted input; a requirement that breaks the build for others, such as a `replace` to a path outside the repository that the build depends on.
- `minor`: an untidy module file or an unused requirement; a `replace` outside the repository that nothing builds through.

## Not a finding

- An available update with no fix, vulnerability, or reason behind it.
- A requirement marked `// indirect` that tidy keeps.
- A `replace` to another module version, not a local path, with a reason in a comment.
- A `replace` to a directory inside the repository. Importers ignore a dependency's `replace`, so it matters to them only through the requirement it serves: report that requirement when it is unused, or when importers need a version that exists nowhere but in the repository.
- A vulnerability check that could not run. That is a limit.
