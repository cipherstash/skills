# Seeded-defect fixture: expected findings

A sample Go change with at least one planted defect in each of the ten checklist areas, and the findings a correct review must report. Run it by hand: nothing in CI drives an agent. `tests/test_fixture.py` checks that each location below is exactly the line it quotes, that the base is clean, and, where a tool or a short probe can show a defect, that it does.

## Contents

- [The change](#the-change)
- [Run it](#run-it)
- [Checks a correct review reports](#checks-a-correct-review-reports)
- Findings G1 to G10, one per area in priority order, then G11, a second in testing and coverage
- [May report](#may-report)
- [Must not report](#must-not-report)

## The change

`base/` is a Go module (`go 1.22`, standard library only) whose `orders.Summarise` decodes JSON order records one at a time and returns an error naming the first record that does not decode. `head/` is the same module after a change titled "orders: decode records concurrently and add reporting helpers". It:

- starts one goroutine per record in `Summarise`, and drops the test that a bad record is rejected;
- adds `orders/report.go` (`DefaultCurrency`, `AverageCents`, `Merge`, `SKUs`), `orders/query.go` (`LinesQuery`), `orders/units.go` (`UnitsPerLine`), `orders/upload.go` (`ParseLine`), and tests for all of them but `Merge`;
- removes the exported method `Summary.Empty`;
- adds a requirement on `example.com/pricing`, replaced by the local directory `pricing/`, which nothing imports.

The finding IDs below are labels for this file. A report numbers its findings most severe first, so its IDs can differ.

## Run it

Build a repository with the change as its last commit, in a scratch directory:

```sh
fixture=<golang-review skill dir>/tests/fixtures/seeded-change
work=$(mktemp -d)
cp -R "$fixture/base/." "$work"
cd "$work"
git init -q && git add -A && git commit -qm "orders: total order lines"
cp -R "$fixture/head/." "$work"
git add -A && git commit -qm "orders: decode records concurrently and add reporting helpers"
```

Then, in a session started in `$work`, ask for a review of the last commit, for example "Review my last commit for Go problems." The review can also take the diff `git diff --no-index "$fixture/base" "$fixture/head"`, but with a pasted diff and no checkout it cannot run the checks.

## Checks a correct review reports

With Go 1.24 and no linters installed. The skill runs the checks over the changed package, `./orders`, and adds `./...` for `go vet`, because the change touches `go.mod` and exported identifiers. A review that runs every check over `./...` is also correct: in this module the two scopes hold the same package, since `pricing/` is a separate module with no packages.

- `go vet ./orders ./...` passes. It detects none of the planted defects, so a clean vet is not a clean review.
- `go test -race -count=1 -timeout 5m -coverprofile=<temp dir>/cover.out ./orders` fails with `WARNING: DATA RACE`: writes in `(*Summary).add` (`orders/orders.go:43` to `:45`) from goroutines started at `orders/orders.go:31`, reached through `orders/orders.go:35`. The profile is still written: coverage 97.1% of statements, and `go tool cover -func` shows `Merge` (`orders/report.go:13`) at 0.0%.
- `gofmt -l` on the changed files lists `orders/units.go`.
- `go mod tidy -diff` fails and prints a diff that removes `require example.com/pricing v0.0.0` from `go.mod`.
- The exported API, compared with `go doc -all ./orders` at the base and the head, has lost `func (s Summary) Empty() bool`, and gained `DefaultCurrency`, `AverageCents`, `Merge`, `SKUs`, `LinesQuery`, `UnitsPerLine`, and `ParseLine`. The repository has no remote and no version tags.
- `govulncheck` is not run: it needs the Go vulnerability database over the network, which the review does not fetch unless the user allows it. This is a limit. With network allowed and `govulncheck` installed, it finds nothing in the module's dependencies, since `example.com/pricing` is a local directory with no code. It may report standard-library vulnerabilities fixed in a newer Go release than the local toolchain; those are not caused by the change.
- `staticcheck`, `gosec`, and `apidiff` are each recorded as not run because they are not installed, or run and quoted if they are. `gosec` reports G104 (unhandled error) at `orders/orders.go:34`, which is G1, and nothing at `orders/query.go:6`: its SQL rules, G201 and G202, look only at `database/sql` call sites, and `LinesQuery` only returns the query, so G6 comes from reading.
- `golangci-lint` is not run: the base commit has no config for it. `semgrep` is not run: it is not installed, or the review has no network access for its ruleset.
- The check suite section lists four checks of the Go check suite as missing, one line each, since the repository has no CI: `golangci-lint`, `govulncheck`, `semgrep`, and the race-enabled tests with coverage. None of them is a finding. The Fuzz target rule is not a missing line: CI cannot tell that a Fuzz target is missing, so the review enforces it, as G11 does.
- The Go version, read from `go.mod`, is 1.22.
- The `golang-practices` references read, one or more for each area, as SKILL.md's areas table names them. If the skill could not be loaded, the review says so as a limit instead.

The verdict is `REQUEST_CHANGES`: G6 is critical, and G1, G2, and G4 are major.

## G1 · major · error handling

- Location: `head/orders/orders.go:34`
- Line: `json.Unmarshal(raw, &l)`
- Cause: the change drops the error from `json.Unmarshal`. The base returned `decode record <i>: <cause>`.
- Trigger and consequence: a record that does not decode, such as `{"sku":"B2","quantity":"one"}`, is still counted as a line. `json.Unmarshal` keeps decoding after the type error, so the line has SKU `B2` and a zero quantity and price. `Summarise` returns a `Summary` with `Lines` one too high and a `nil` error, so the caller cannot tell that the totals are wrong. The change also deleted `TestSummariseRejectsABadRecord`, the test that caught this.
- Rule: golang-practices, error handling: check every returned error.
- Evidence: reading the diff. `go vet` passes, so tools do not show it.
- A correct fix sends each goroutine's error back to `Summarise`, which returns it with the record's index, and restores the deleted test.

## G2 · major · correctness and edge cases

- Location: `head/orders/report.go:8`
- Line: `return s.TotalCents / s.Units`
- Cause: `AverageCents` is documented to return 0 when the summary has no units, but it divides by `s.Units` without checking it.
- Trigger and consequence: an empty summary, as `Summarise(nil)` or a batch of zero-quantity lines returns, makes `AverageCents` panic with `integer divide by zero`, where the documentation promises 0. Major, not critical: the review shows no caller where an empty batch is the common path.
- Evidence: reading the function against its doc comment. `TestAverageCents` covers only a non-empty summary, so the tests pass.
- A correct fix returns 0 when `s.Units == 0`, and adds that case to the test.

## G3 · minor · testing and coverage

- Location: `head/orders/report.go:13`
- Line: `func (s Summary) Merge(o Summary) Summary {`
- Cause: the change adds the exported method `Merge` with no test.
- Rule: golang-practices, testing: look at uncovered new code and decide whether a regression there would go unnoticed. A `Merge` that dropped one of its three fields would pass every test.
- Evidence: `go tool cover -func` shows `Merge` at 0.0%, the only function at 0.0%. Coverage is 97.1% of statements.
- A correct fix adds a table test for `Merge`, including merging with an empty summary.

## G4 · major · concurrency safety

- Location: `head/orders/orders.go:35`
- Line: `s.add(l)`
- Cause: every goroutine calls `s.add` on the shared `Summary` with no lock, so the `+=` and `++` in `add` race.
- Trigger and consequence: any call with two or more records. Updates are lost, so `Lines`, `Units`, and `TotalCents` can come back too low, with no error. It is major, not critical: the wrong totals are `Summarise`'s result, and nothing in the change stores or sends them.
- Rule: golang-practices, concurrency: a data race is a bug even when the test passes.
- Evidence: `go test -race -count=1 -timeout 5m ./orders` reports `WARNING: DATA RACE` at `orders.go:43` through `orders.go:35`.
- A correct fix guards the totals with a mutex, or has each goroutine send its line to one goroutine that adds them.

## G5 · minor · naming and style

- Location: `head/orders/units.go:5`
- Line: `func (this Summary) UnitsPerLine() float64{`
- Cause: the new method's receiver is named `this`, where every other `Summary` method uses `s`, and the file is not formatted: `gofmt` adds a space before the `{`.
- Rule: golang-practices, naming: a receiver is one or two letters from its type, the same on every method, never `this` or `self`; and format with `gofmt`.
- Evidence: `gofmt -l` lists `orders/units.go`, and `gofmt -d` changes this line.
- A correct fix renames the receiver to `s` and runs `gofmt -w orders/units.go`.

## G6 · critical · security

- Location: `head/orders/query.go:6`
- Line: `return "SELECT sku, quantity, price_cents FROM order_lines WHERE sku = '" + sku + "'"`
- Cause: `LinesQuery` builds SQL by concatenating `sku`, which its doc comment says is what the customer typed.
- Trigger and consequence: a SKU such as `x' OR '1'='1` returns `... WHERE sku = 'x' OR '1'='1'`, which selects every order line; other input can change the statement further. The doc comment says the search handler passes the SKU as the customer typed it, so an attacker controls the input. `step-security.md` makes SQL injection from attacker-controlled input critical. That rule is more specific than the finding contract's, so it decides the severity, though nothing in the change runs the query yet.
- Rule: golang-practices, security: build SQL with placeholders and pass values as arguments.
- Evidence: reading the function. `gosec` does not report it, because nothing in the change passes the query to a `database/sql` call.
- A correct fix returns the query with a placeholder (`WHERE sku = $1`, or `?` for the driver in use) and passes `sku` as an argument to `QueryContext`.

## G7 · minor · performance

- Location: `head/orders/report.go:24`
- Line: `var skus []string`
- Cause: `SKUs` appends one SKU per line to a slice declared with no capacity, though the final length, `len(lines)`, is known. Its doc comment says it runs for every batch.
- Rule: golang-practices, performance: when the final length is known, make a slice with that capacity.
- Evidence: reading the function. For 100 lines, `testing.AllocsPerRun` measures several allocations where `make([]string, 0, len(lines))` needs one.
- A correct fix declares `skus := make([]string, 0, len(lines))`.

## G8 · minor · dependency management

- Location: `head/go.mod:5`
- Line: `require example.com/pricing v0.0.0`
- Cause: the change requires `example.com/pricing`, which no package imports. A `replace` points it at the directory `./pricing`, which is inside the repository, so this module still builds anywhere. But importers ignore a dependency's `replace`, so the requirement puts a version that exists nowhere else into their module graph: their build still works, but `go list -m all` there fails to find `example.com/pricing v0.0.0`.
- Rule: golang-practices, dependencies: run `go mod tidy` after changing imports.
- Evidence: `go mod tidy -diff` fails and its diff removes this line.
- A correct fix removes the `require` and the `replace`, and the `pricing/` directory.

## G9 · minor · documentation

- Location: `head/orders/report.go:3`
- Line: `const DefaultCurrency = "AUD"`
- Cause: the new exported constant has no doc comment, so `go doc` shows no guidance on what it is the default for.
- Rule: golang-practices, naming: document every exported name with a comment that starts with the name.
- Evidence: reading the declaration. It is the only exported identifier in the change without a comment.
- A correct fix adds a comment such as `// DefaultCurrency is the ISO 4217 code of the currency that prices are in.`

## G10 · minor · breaking changes

- Location: `base/orders/orders.go:44` (deleted)
- Line: `func (s Summary) Empty() bool {`
- Cause: the change removes the exported method `Summary.Empty`.
- Trigger and consequence: any importer that calls `Empty` stops compiling when it updates to this version. The module path has no major-version suffix, and the repository, which has no remote, has no version tags, so it is at v0, where Go makes no compatibility promise: minor. Released at v1 or later, the change would need a new major version and module path (`/v2`), and would be major.
- Evidence: `go doc -all ./orders` at the base lists `func (s Summary) Empty() bool`, and at the head does not.
- A correct fix keeps `Empty`, or, if it must go, names the removal in the release notes and bumps the version: the minor version at v0, a new major version at v1 or later.

## G11 · minor · testing and coverage

- Location: `head/orders/upload.go:11`
- Line: `func ParseLine(row string) (Line, error) {`
- Cause: the change adds `ParseLine`, which parses a row of a file that a customer uploads, with no Fuzz target. That row is untrusted input.
- Rule: golang-practices, the Go check suite: a function that parses or decodes untrusted input must have a Fuzz target. CI cannot tell that one is missing, so the review reports it.
- Evidence: reading the function and its doc comment. No test file in the module declares a `Fuzz` function. `TestParseLine` covers it with fixed rows only.
- A correct fix adds `FuzzParseLine` to `orders/upload_test.go`, with the rows from `TestParseLine` as its seed corpus through `f.Add`.

## May report

These neither count for nor against the review. For example:

- Testing and coverage: the change deleted `TestSummariseRejectsABadRecord`. This may also be folded into G1, as above.
- Correctness and edge cases: `ParseLine` accepts a negative quantity or price. Its doc comment sets no range.
- Performance: one goroutine per record has no bound, so a very large batch starts that many goroutines.
- Dependency management: the `replace` to `./pricing`, as part of G8. On its own it breaks no build, since the directory is in the repository.
- Documentation: the doc comment on `Summarise` says records are decoded concurrently "so large batches finish sooner", which no benchmark shows.

## Must not report

Each of these would be a false finding.

- The closure capturing the loop variable `raw` at `orders/orders.go:34`. `go.mod` says `go 1.22`, where each iteration has its own `raw`. Before Go 1.22 it would be a defect.
- A missing `context.Context` on `Summarise`. It does no I/O and nothing in it can block for long, and the goroutines all end once decoding ends, so `wg.Wait` always returns.
- A goroutine leak. Every goroutine ends after one decode and one `add`, and `wg.Wait` waits for all of them.
- `UnitsPerLine` dividing by zero. It returns 0 for an empty summary before dividing, as documented, and its test covers that case.
- `SKUs` returning `nil` for no lines. Its doc comment promises no non-nil slice, and `len` and `range` treat `nil` as empty.
- `AverageCents` rounding down. Its doc comment says it does.
- Missing tests for `DefaultCurrency`. A constant has no statements to cover.
- A known vulnerability in a dependency. The module has none to scan, and without network the review cannot run `govulncheck` at all: that is a limit, not a finding.
- Anything in `base/` that the change does not touch.
