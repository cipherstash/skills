# Running checks safely

Read this in step 5, before running any command in the worktree. It lists the checks, the settings that keep them read-only, what to read before running tests, and how to record each outcome.

## Contents

- [Settings for every go command](#settings-for-every-go-command)
- [Scope](#scope)
- [Before running tests](#before-running-tests)
- [The checks](#the-checks)
- [Commands the review never runs](#commands-the-review-never-runs)
- [Recording outcomes](#recording-outcomes)

## Settings for every go command

Run every `go` command from the root of the module that holds the packages, inside the temporary worktree, with these environment variables:

| Setting | Why |
| --- | --- |
| `GOFLAGS=-mod=readonly` | `go.mod` and `go.sum` are never rewritten. If the module has `vendor/modules.txt`, use `GOFLAGS=-mod=vendor` instead, so the vendored copies are used. |
| `GOTOOLCHAIN=local` | The go command never downloads a toolchain to match a `go` or `toolchain` line. |
| `GOPROXY=off` | No module is downloaded. A module missing from the local module cache fails the command, which is a limit. |

Leave `GOWORK` as the repository has it: a committed `go.work` is part of how the code builds. The go command still writes to its build cache, which lives outside the repository (`go env GOCACHE`). That is not a change to the tree.

## Scope

Check the changed packages: each directory with a changed `.go` file, as `./<dir>` from the module root. When the change touches `go.mod` or an exported identifier, add `./...` for `go vet`, since a change there can break other packages in the module. Record the package list in the report.

## Before running tests

`go vet` compiles the packages but runs none of their code. `go test` runs the change's code on this machine with the user's permissions: `init` functions, `TestMain`, the tests themselves, and every function they call, changed or not. An unchanged test that calls a changed function runs the change. Treat all of the changed code as untrusted until you have read it.

1. Read every changed `.go` file, test or not, in the packages under test and in the module's packages they import; every `TestMain` and `init` function in the packages under test; and every changed file the tests load, such as files under `testdata/`.
2. Look for code that reaches outside a test's own sandbox: `os/exec` or `syscall` calls, network connections to anything but loopback, reads of credentials, tokens, or the user's home directory, writes outside `t.TempDir()`, and `//go:generate` or `cgo` code.
3. Run the tests if that code does only what the change and its tests plainly need. If it does more, or there is more changed code than you can read (large generated or vendored code), do not run them. Record the tests as not run, give the reason, and say that the user can run them.

Read the repository's `Makefile`, task runner file, or CI configuration only to learn the flags and build tags its tests use, such as `-tags integration`. Run the `go` commands directly with those flags. Do not run the task runner.

## The checks

| Check | Command | What it can show |
| --- | --- | --- |
| Vet | `go vet <packages>` | Copied locks, lost `cancel` functions, misused `printf` verbs and `%w`, `errors.As` with a non-pointer, and, in modules below Go 1.22, loop variables captured by goroutines |
| Race-enabled tests | `go test -race -count=1 -timeout 5m <packages>` | Data races on paths the tests execute, deadlocks (`all goroutines are asleep`, or a timeout with goroutine dumps), and failing tests |

`-race` needs cgo and a supported platform. If it fails with `-race requires cgo` or an unsupported-platform error, record the race check as not run, then run `go test -count=1 -timeout 5m <packages>` without it and record that as a separate check.

A linter the repository already uses, such as `staticcheck` or `errcheck`, can also be run when it is already installed: check with `command -v` and record its version. Do not install one.

To show a suspected race or leak that no existing test reaches, you may add a test file in the temporary worktree, run it there, and quote its output as evidence. Say in the finding that the test was written for the review. It goes away with the worktree.

## Commands the review never runs

`go generate`, `go run`, `go install`, `go get`, `go mod tidy`, `go mod download`, `go mod vendor`, `go work sync`, `go test` with `-exec` or a flag that updates golden files (such as `-update`), and repository scripts or task-runner targets. For any other command, read what it does first, with `go help <command>` or by reading the script, and run it only if it changes no file in the repository and fetches nothing.

## Recording outcomes

Record each check as exactly one of:

- **passed**: it ran over the recorded scope and reported nothing. A pass shows only what the check can see. `go test -race` sees races only on paths a test executed, so a pass is not evidence that code no test reached is race-free.
- **failed**: it ran and reported a problem. Quote the relevant output with its file and line. A failure caused by the change is evidence for a finding, and a compile error in changed code is itself a finding.
  - A race report (`WARNING: DATA RACE`) or a deadlock is evidence even if it does not happen again: the race detector reports only races that happened, and both depend on timing. Never discard one as flaky.
  - Any other test failure that does not happen again when run once more is flaky. Report it under the checks, not as a finding.
  - To tell whether a failure is already present, run the same command at the base, in a second worktree made as `target.md` describes but at the base commit, and remove it the same way. Run it only if the diff's base side, read like the head in [Before running tests](#before-running-tests), is safe too. A failure that also happens at the base is not caused by the change: report it under the checks as already present.
- **not run**: it could not run or was not run. Give the reason: the go command is missing, the local toolchain is older than the `go` line, modules are missing from the cache (the user can run `go mod download`), the race detector is unavailable, the test code was not safe to run, there is no local clone, or the patch did not apply. This is a limit of the review. It is never a pass and never a defect.
