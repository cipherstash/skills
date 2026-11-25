# Go check suite

The Go check suite is the set of checks that gate every pull request in a Go repository. They run in CI, and CI is the gate. Run any of these tools locally when it helps you get a change right, but do not treat a local run as the gate.

The examples module targets Go 1.22, the `go` line in [`examples/go.mod`](../examples/go.mod). CI builds and checks it with the latest stable Go release.

## Pinned versions

Every tool version is pinned. A repository's CI uses these versions.

| Tool | Version | Package |
| --- | --- | --- |
| golangci-lint | `v2.15.0` | `github.com/golangci/golangci-lint/v2/cmd/golangci-lint` |
| govulncheck | `v1.10.0` | `golang.org/x/vuln/cmd/govulncheck` |
| semgrep | `1.186.0` | `semgrep` on PyPI |

Two things float by choice. CI uses the latest stable Go release, through `actions/setup-go` with `go-version: stable`. semgrep reads the latest `p/golang` ruleset. Either can fail a pull request that did not cause the finding. Fix the finding.

The golangci-lint pin moves with each Go minor release. A golangci-lint release cannot type-check code for a Go release newer than the one it was built with. So when a new Go minor release comes out, the lint steps fail with `file requires newer Go version` until the pin moves. That failure is not a finding in the code. Move the pin to a golangci-lint release built with the new Go.

## The checks

- **golangci-lint**, as the runner for `govet`, `staticcheck`, `gosec`, and the `gofumpt` formatter. Use `gofumpt`, not `gofmt`. To format locally, run `golangci-lint fmt`. Start from the template [assets/golangci.yml](../assets/golangci.yml). A repository's own config may enable more linters, but must enable at least these four.
- **govulncheck**, run on its own: `go run golang.org/x/vuln/cmd/govulncheck@<version> ./...`, with the version from the table.
- **semgrep**, run on its own, with the `p/golang` ruleset plus the repository's own rules in `.semgrep/` at its root, when that directory exists. By default, semgrep skips test files (`*_test.go`) and test directories. Add a `.semgrepignore` at the repository root. That file replaces the default list. Leave the test entries out of it, so that semgrep scans the tests too.
- **Tests with the race detector and coverage**: `go test -race -coverprofile=coverage.out ./...`, then `go tool cover -func=coverage.out` to report coverage. There is no coverage threshold.
- **Fuzz targets**: a function that parses or decodes untrusted input must have a Fuzz target. Untrusted input is bytes from outside the process, such as a request body, a file, or a message. Give each target a seed corpus with `f.Add`. CI runs only the seed corpus, through plain `go test`. It never runs `-fuzz`. CI cannot tell that a Fuzz target is missing, so code review enforces this rule.

Profiling, with `-bench` or pprof, is not part of the suite. [performance.md](performance.md) keeps it as advice.

## When a check is in place

A check is in place when it is a GitHub Actions step that:

- runs on `pull_request`;
- blocks: it has no `continue-on-error`, no `|| true`, and no other way of ignoring the tool's exit status, such as a shell set without `-e` (`shell: bash {0}`), which lets a failing line pass when a later line passes;
- covers every Go module, except test fixtures that contain planted defects;
- pins its tool version, such as `version: v2.15.0` for `golangci-lint-action` or `@v1.10.0` for `go run`. `@latest` does not count. In a module whose `go` line is 1.24 or later, a `tool` directive in `go.mod`, run with `go tool <name>`, also counts as pinned, because `go.mod` fixes its version.

## Exemptions

A repository may leave a check out only through an exemption architecture decision record (ADR). The ADR is a file in `docs/adr/` on the repository's default branch, added through an issue and a reviewed pull request. It:

- names each check it exempts, and each Go module it covers;
- gives the reason;
- links the issue it came from and the merged pull request that added it.

An ADR leaves out only the checks and modules it names. A pull request cannot exempt itself by adding one.
