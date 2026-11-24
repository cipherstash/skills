# The Go check suite

The checks every Go repository runs in CI on each pull request. CI runs them; an agent does not. An agent writing Go runs only `go build` and `go test` on its own change. When an agent creates or edits a repository's CI, it adds any check below that is missing. `golang-review` reports the ones that are not in place.

## Contents

- [The checks](#the-checks)
- [In place](#in-place)
- [Exemptions](#exemptions)
- [Fuzz targets](#fuzz-targets)
- [Workflow](#workflow)

## The checks

| Check | Command | Finds |
| --- | --- | --- |
| Format | `golangci-lint fmt --diff ./...` (gofumpt) | Code that is not gofumpt-formatted. gofumpt is a stricter gofmt; use plain `gofmt -l` only where gofumpt cannot run |
| Lint | `golangci-lint run ./...` with [`assets/golangci.yml`](../assets/golangci.yml) | govet, staticcheck, errcheck, ineffassign, unused, and gosec |
| Known vulnerabilities | `govulncheck ./...` | Vulnerable dependencies and standard library calls; see `dependencies.md` |
| Pattern scan | `semgrep scan --config p/golang --error` | Insecure patterns, plus the repository's own rules in `.semgrep/` when it has one |
| Race-enabled tests | `go test -race -coverprofile=cover.out ./...` | Failing tests and data races on paths the tests run. Plain `go test` also runs every fuzz target's seed corpus |
| Coverage report | `go tool cover -func=cover.out` | Code no test runs. Report it; do not gate on a percentage |

Copy `assets/golangci.yml` to the repository root as `.golangci.yml`. A repository may enable more linters, or exclude a specific finding with a reason. It does not disable the linters, the formatter or the settings in that file.

Benchmarks and profiles are not part of the suite. They are in `performance.md`.

## In place

A check is in place when a GitHub Actions workflow step runs it, and the step:

- runs on `pull_request`. A check that runs only on pushes to the main branch does not count.
- blocks: no `continue-on-error: true`, and no `|| true` or other way of ignoring its exit status.
- covers every Go module in the repository, including each module in a `go.work` workspace.
- pins the tool's version, such as `version: v2.5.0` for `golangci-lint-action`, or `@v1.1.4` for `go run`. `@latest` does not count. In a module whose `go` line is 1.24 or later, a `tool` directive in `go.mod` run with `go tool` also counts as pinned.

Race-enabled tests are in place only in a job on Linux with `CGO_ENABLED=1`, because `-race` needs cgo. A repository whose test job sets `CGO_ENABLED=0`, for a static build for example, needs a second test job for `-race`.

A check can sit in any job, such as `govulncheck` in a `go-lint` job.

## Exemptions

A check that a repository cannot run is in place if an exemption ADR covers it. The ADR is a file in `docs/adr/` that:

- names each check it exempts, and the modules it covers.
- gives the reason, and what the repository does instead, if anything.
- links the issue that asked for the exemption, and the pull request that merged it.

Only an ADR on the default branch counts. A pull request cannot exempt itself by adding one.

## Fuzz targets

A function that parses or decodes bytes from outside the process has a fuzz target. Outside the process means the network, a file, a request, or user input. A fuzz target checks a property that holds for every input, as in `testing.md`. Because `go test` runs the seed corpus, the suite needs no separate fuzz step. Run longer `-fuzz` sessions locally or on a schedule.

## Workflow

A job that runs the suite on a module in the repository root. Pin each tool's version, and keep them current with Dependabot or Renovate. `go-version-file` takes the `toolchain` line in `go.mod`, or the `go` line when there is none. Keep that toolchain on a current patch release: `govulncheck` fails on every standard-library vulnerability fixed in a later one.

```yaml
on: [pull_request]

jobs:
  go-checks:
    runs-on: ubuntu-latest
    env:
      CGO_ENABLED: "1"
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-go@v5
        with:
          go-version-file: go.mod
      - uses: golangci/golangci-lint-action@v8
        with:
          version: v2.5.0
      - run: golangci-lint fmt --diff ./...
      - run: go run golang.org/x/vuln/cmd/govulncheck@v1.1.4 ./...
      - run: go test -race -coverprofile=cover.out ./...
      - run: go tool cover -func=cover.out
  semgrep:
    runs-on: ubuntu-latest
    container: semgrep/semgrep:1.186.0
    steps:
      - uses: actions/checkout@v4
      - run: semgrep scan --config p/golang --error --metrics off
```
