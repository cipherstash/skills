# Dependencies

Adding dependencies, keeping `go.mod` and `go.sum` tidy, checking for known vulnerabilities, finding outdated modules, and updating one dependency at a time.

The commands target Go 1.22, the `go` line in [`examples/go.mod`](../examples/go.mod), unless the text names a later version. `go mod tidy -diff` needs Go 1.23, and the `tool` directive needs Go 1.24. This reference has no Go examples: the examples module has no dependencies, so the commands are shown as shell blocks. The layout of `go.mod` itself is in `project-structure.md`.

## Contents

- [Rules](#rules)
- [Before adding a dependency](#before-adding-a-dependency)
- [Keep go.mod and go.sum tidy](#keep-gomod-and-gosum-tidy)
- [Check for known vulnerabilities](#check-for-known-vulnerabilities)
- [Find outdated dependencies](#find-outdated-dependencies)
- [Update one dependency at a time](#update-one-dependency-at-a-time)
- [Major versions](#major-versions)
- [Moving to a new Go version](#moving-to-a-new-go-version)
- [Quick reference](#quick-reference)

## Rules

- Prefer the standard library. Add a dependency only when it saves real work, and say so in the change.
- Run `go mod tidy` after changing imports or dependencies, and commit `go.mod` and `go.sum` together.
- Run `govulncheck`, as [checks.md](checks.md) sets it up, when dependencies change, and fix the vulnerabilities it reports in code the module calls.
- Update dependencies one at a time, to a version you chose, with the tests run after each. Do not run `go get -u ./...` as a routine step.
- Do not commit a `replace` that points at a path outside the repository, because no other checkout can see it. A `replace` to a directory inside the repository is fine. Do not commit a `go.work` file the repository does not already track.
- Treat a new major version as an API migration, not an update.

## Before adding a dependency

Check:

- **Need.** Does the standard library, or a dependency the module already has, do this? Small helpers are often cheaper to write than to depend on.
- **Health.** Is it maintained, with recent releases and answered issues? Is it at a stable `v1` or later? Is it archived? `pkg.go.dev` shows the licence, version history, and importers.
- **Licence.** Is it compatible with how the code is distributed?
- **Weight.** What does it pull in? After `go get`, `go mod graph | grep '^<module>@'` lists its own requirements.

Add it at a chosen version, then tidy:

```sh
go get example.com/some/module@v1.4.2
go mod tidy
```

## Keep go.mod and go.sum tidy

`go mod tidy` adds requirements the code imports but `go.mod` lacks, removes ones nothing imports, and updates `go.sum`. Run it after every change to imports or dependencies.

Check it in CI, so an untidy module fails the build:

```sh
# Go 1.23 and later: print the changes tidy would make, and fail if there are any.
go mod tidy -diff

# Earlier versions: tidy, then fail if the files changed.
go mod tidy && git diff --exit-code -- go.mod go.sum
```

Other checks:

```sh
go mod verify            # downloaded modules match go.sum
go mod why -m example.com/some/module   # why the module is needed
go list -m all           # every module in the build, with its version
```

`go.sum` contains checksums for module contents. Commit it. Do not edit it by hand. If it conflicts in a merge, take either side, then run `go mod tidy`.

## Check for known vulnerabilities

`govulncheck` checks the module's dependencies and the Go standard library against the Go vulnerability database. It analyses the code. It lists first the vulnerabilities in functions the code calls, because those matter most.

It is in the Go check suite. [checks.md](checks.md) gives its command and pinned version.

For each reported vulnerability:

- **In a dependency:** update that module to the "Fixed in" version or later, as in [Update one dependency at a time](#update-one-dependency-at-a-time). If it is an indirect dependency, `go get` it directly at the fixed version, then `go mod tidy`.
- **In the standard library:** build with a Go release that has the fix. Raise the `toolchain` line in `go.mod`, or the build image's Go version. The `go` line need not change.
- **No fix yet:** record it, check whether the vulnerable function can be reached with untrusted input, and track the upstream fix.

Security problems in the module's own code are in `security.md`.

## Find outdated dependencies

```sh
# Every module, with the newest available version in brackets where there is one:
go list -m -u all

# Direct dependencies only:
go list -m -u -f '{{if and (not .Indirect) .Update}}{{.Path}} {{.Version}} -> {{.Update.Version}}{{end}}' all
```

An available update is not a reason to update by itself. Update for a fix you need, a vulnerability, or to stay close enough to current that a later required update stays small.

## Update one dependency at a time

Updating every dependency at once (`go get -u ./...`) changes many modules in one step. When something breaks, you cannot tell which update caused it. The change is also too big to review. Update one module, check it, and commit it on its own:

```sh
go get example.com/some/module@v1.5.0   # or @latest for that one module
go mod tidy
go build ./... && go vet ./... && go test -race ./...
# then run govulncheck at the version pinned in checks.md
git diff -- go.mod go.sum                # review what else moved
```

- Read the module's release notes between the two versions before updating.
- `go get` may raise other modules too, because Go selects the minimum version that satisfies every requirement. Check the `go.mod` diff for those.
- `go get -u=patch example.com/some/module` takes the latest patch release of that module and of its dependencies, and no new minor versions.
- Bots such as Dependabot or Renovate open update pull requests. For the same reason, keep each to one module, or one tightly linked group.

To remove a dependency, delete the imports that use it and run `go mod tidy`.

## Major versions

From `v2`, a Go module's import path ends with the major version: `example.com/some/module/v2`. A new major version may break its API, so moving to it is a code change, not an update:

```sh
go get example.com/some/module/v2@v2.1.0
# change imports from example.com/some/module to example.com/some/module/v2, and fix what breaks
go mod tidy
```

Releasing a new major version of your own module means changing its `module` line and every import inside it. A breaking change to an exported API without one breaks every importer.

## Moving to a new Go version

Raising the `go` line in `go.mod` can change what code does, not only which features it may use. Moving to `go 1.22`, for example, gives each loop iteration its own loop variable. Read the release notes for each version crossed, then run the full test suite with `-race`. Raise the `go` line on its own, not in the same change as dependency updates.

## Quick reference

| Task | Command |
| --- | --- |
| Add a dependency | `go get example.com/m@v1.4.2`, then `go mod tidy` |
| Tidy | `go mod tidy` |
| Check tidiness in CI | `go mod tidy -diff` (Go 1.23), or tidy and `git diff --exit-code` |
| Known vulnerabilities | `govulncheck`, as in [checks.md](checks.md) |
| Outdated modules | `go list -m -u all` |
| Update one module | `go get example.com/m@v1.5.0`, then tidy and test |
| Patch releases of one module | `go get -u=patch example.com/m` |
| Why a module is needed | `go mod why -m example.com/m` |
| Check downloaded modules | `go mod verify` |
