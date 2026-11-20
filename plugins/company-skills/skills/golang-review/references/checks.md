# Running checks safely

Read this in step 5, before running any command in the worktree. It lists the checks and the areas each serves, the settings that keep them read-only, the tools that run only when installed, when the network may be used, what to read before running tests, and how to record each outcome.

## Contents

- [Settings for every go command](#settings-for-every-go-command)
- [Scope](#scope)
- [Before running tests](#before-running-tests)
- [The checks](#the-checks)
- [Tools outside the go command](#tools-outside-the-go-command)
- [Network](#network)
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

Write every file a check produces, such as a coverage profile, to a temporary directory outside the repository and outside the worktree (`mktemp -d`), and remove it with the worktree.

## Scope

Check the changed packages: each directory with a changed `.go` file, as `./<dir>` from the module root. When the change touches `go.mod` or an exported identifier, add `./...` for `go vet`, since a change there can break other packages in the module. Record the package list in the report.

Run only the checks the areas in scope need, as the table below maps them. When the request names areas, record each other check as `not run: <area> not in scope at the user's request`.

## Before running tests

`go vet`, `gofmt`, `go doc`, `go mod tidy -diff`, and the linters below read or compile the packages but run none of their code. `go test` runs the change's code on this machine with the user's permissions: `init` functions, `TestMain`, the tests themselves, and every function they call, changed or not. An unchanged test that calls a changed function runs the change. Treat all of the changed code as untrusted until you have read it.

1. Read every changed `.go` file, test or not, in the packages under test and in the module's packages they import; every `TestMain` and `init` function in the packages under test; and every changed file the tests load, such as files under `testdata/`.
2. Look for code that reaches outside a test's own sandbox: `os/exec` or `syscall` calls, network connections to anything but loopback, reads of credentials, tokens, or the user's home directory, writes outside `t.TempDir()`, and `//go:generate` or `cgo` code.
3. Run the tests if that code does only what the change and its tests plainly need. If it does more, or there is more changed code than you can read (large generated or vendored code), do not run them. Record the tests as not run, give the reason, and say that the user can run them.

Read the repository's `Makefile`, task runner file, or CI configuration only to learn the flags and build tags its tests use, such as `-tags integration`. Run the `go` commands directly with those flags. Do not run the task runner.

## The checks

| Check | Command | Areas | What it can show |
| --- | --- | --- | --- |
| Vet | `go vet <packages>` | All | Copied locks, lost `cancel` functions, misused `printf` verbs and `%w`, `errors.As` with a non-pointer, unreachable code, and, in modules below Go 1.22, loop variables captured by goroutines |
| Race-enabled tests with coverage | `go test -race -count=1 -timeout 5m -coverprofile=<tmp>/cover.out <packages>` | Error handling, correctness, testing, concurrency | Data races on paths the tests execute, deadlocks (`all goroutines are asleep`, or a timeout with goroutine dumps), failing tests, and the coverage profile |
| Coverage report | `go tool cover -func=<tmp>/cover.out` | Testing | Coverage per function and the total. It only reads the profile |
| Formatting | `gofmt -l <changed .go files>` | Naming and style | Files `gofmt` would change. Then `gofmt -d <file>` for the lines. Never `-w` |
| Module tidiness | `go mod tidy -diff`, from each touched module's root | Dependencies | Requirements tidy would add or remove. Needs a local toolchain at Go 1.23 or later; never run without `-diff` |
| Exported API | `go doc -all <package>` in the head worktree and a base worktree, or `apidiff` | Breaking changes | Removed, renamed, and changed exported declarations, as `step-breaking-changes.md` describes |

`-race` needs cgo and a supported platform. If it fails with `-race requires cgo` or an unsupported-platform error, record the race check as not run, then run `go test -count=1 -timeout 5m -coverprofile=<tmp>/cover.out <packages>` without it and record that as a separate check. The coverage profile is written even when tests fail, so its figure is still reported, beside the failure.

`go mod tidy -diff` runs with the settings above and writes nothing; a non-zero exit with a diff is the evidence. A failure that names a module missing from the cache, or a download, is a limit.

To show a suspected race, leak, edge case, or allocation that no existing test reaches, you may add a test file in the temporary worktree, run it there, and quote its output as evidence. Say in the finding that the test was written for the review. It goes away with the worktree.

## Tools outside the go command

Each of these runs only when it is already installed: check with `command -v <tool>` and record its version. When it is not installed, record it as `not run: not installed`, which is a limit. Never install one, or run one with `go run <tool>@<version>`, which downloads it.

| Tool | Command | Areas |
| --- | --- | --- |
| `staticcheck` | `staticcheck <packages>` | Error handling, correctness, concurrency, performance |
| `gosec` | `gosec <packages>` | Security |
| `golangci-lint` | `golangci-lint run <packages>`, only where the repository has a config for it | Any its config enables |
| `govulncheck` | `govulncheck <packages>`, only as [Network](#network) allows | Dependencies |
| `apidiff` | As its `-help` gives, comparing the base and head worktrees | Breaking changes |

These read source and run none of it, but read each one's configuration before running it. Do not run `golangci-lint` if its config loads plugins (`custom` linters or `.custom-gcl.yml`), which run code, and never pass `--fix` or any flag that writes files. They run under the same environment settings as the go command.

## Network

The review fetches nothing from the network unless the user allows it, with one use for that permission: `govulncheck` reads the Go vulnerability database from `vuln.go.dev`, requesting entries for the modules in the build. It changes no file. Run it only when it is installed and either:

- the user's request allows network access for the review, such as "check for vulnerabilities too"; or
- a local copy of the database exists: pass it as `govulncheck -db file:///<path> <packages>`.

Otherwise record `govulncheck` as `not run: needs the vulnerability database over the network`, and give the command the user can run. Reading a pull request through the host's GitHub tools, and the `git fetch` that `target.md` describes, are part of resolving the target, not checks.

## Commands the review never runs

`go generate`, `go run`, `go install`, `go get`, `go mod tidy` without `-diff`, `go mod download`, `go mod vendor`, `go work sync`, `go test` with `-exec` or a flag that updates golden files (such as `-update`), `gofmt -w` or any formatter that writes, a linter's `--fix`, `go tool cover -html` (it opens a browser), and repository scripts or task-runner targets. For any other command, read what it does first, with `go help <command>` or `<tool> -help`, or by reading the script, and run it only if it changes no file in the repository and fetches nothing that [Network](#network) does not allow.

## Recording outcomes

Record each check as exactly one of:

- **passed**: it ran over the recorded scope and reported nothing. A pass shows only what the check can see. `go test -race` sees races only on paths a test executed, so a pass is not evidence that code no test reached is race-free.
- **failed**: it ran and reported a problem. Quote the relevant output with its file and line. A failure caused by the change is evidence for a finding, and a compile error in changed code is itself a finding.
  - A race report (`WARNING: DATA RACE`) or a deadlock is evidence even if it does not happen again: the race detector reports only races that happened, and both depend on timing. Never discard one as flaky.
  - Any other test failure that does not happen again when run once more is flaky. Report it under the checks, not as a finding.
  - To tell whether a failure is already present, run the same command at the base, in a second worktree made as `target.md` describes but at the base commit, and remove it the same way. Run it only if the diff's base side, read like the head in [Before running tests](#before-running-tests), is safe too. A failure that also happens at the base is not caused by the change: report it under the checks as already present.
- **not run**: it could not run or was not run. Give the reason: the go command is missing, the local toolchain is older than the `go` line or too old for the check (`go mod tidy -diff` needs Go 1.23), modules are missing from the cache (the user can run `go mod download`), the race detector is unavailable, a tool is not installed, the vulnerability database needs the network, the test code was not safe to run, the area is not in scope at the user's request, there is no local clone, or the patch did not apply. This is a limit of the review, except an area left out at the user's request, which is listed as not reviewed. It is never a pass and never a defect.
