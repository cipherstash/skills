# Seeded-defect fixture: expected findings

A sample Go change with one planted defect in each area `golang-review` covers, and the findings a correct review must report. Run it by hand: nothing in CI drives an agent. `tests/test_fixture.py` checks that the fixture still builds, that `go vet` passes on the head, that `go test -race` reports the planted race, and that each location below quotes its line.

## The change

`base/` is a Go module (`go 1.22`) whose `orders.Summarise` decodes JSON order records one at a time and returns an error naming the first record that does not decode. `head/` is the same module after a change titled "orders: decode records concurrently". It starts one goroutine per record, and it drops the test that a bad record is rejected.

## Run it

Build a repository with the change as its last commit, in a scratch directory:

```sh
fixture=<golang-review skill dir>/tests/fixtures/seeded-change
work=$(mktemp -d)
cp -R "$fixture/base/." "$work"
cd "$work"
git init -q && git add -A && git commit -qm "orders: total order lines"
cp -R "$fixture/head/." "$work"
git add -A && git commit -qm "orders: decode records concurrently"
```

Then, in a session started in `$work`, ask for a review of the last commit, for example "Review my last commit for Go problems." The review can also take the diff `git diff --no-index "$fixture/base" "$fixture/head"`, but with a pasted diff and no checkout it cannot run the checks.

## Checks a correct review reports

- `go vet ./...` passes. Neither planted defect is one `go vet` detects, so a clean vet is not a clean review.
- `go test -race ./...` fails with `WARNING: DATA RACE`: writes in `(*Summary).add` (`orders/orders.go:43` to `:45`) from goroutines started at `orders/orders.go:31`, reached through `orders/orders.go:35`.
- The Go version, read from `go.mod`, is 1.22.
- The `golang-practices` references read: `references/error-handling.md` and `references/concurrency.md`. If the skill could not be loaded, the review says so as a limit instead.
- The eight checklist areas this version does not cover are listed as not reviewed.

## G1 · major · error handling

- Location: `head/orders/orders.go:34`
- Line: `json.Unmarshal(raw, &l)`
- Cause: the change drops the error from `json.Unmarshal`. The base returned `decode record <i>: <cause>`.
- Trigger and consequence: a record that does not decode, such as `{"sku":"B2","quantity":"one"}`, is counted as a zero-valued line. `Summarise` returns a `Summary` with `Lines` one too high and a `nil` error, so the caller cannot tell that the totals are wrong. The change also deleted `TestSummariseRejectsABadRecord`, the test that caught this.
- Rule: golang-practices, error handling: check every returned error.
- Evidence: reading the diff. `go vet` passes, so tools do not show it.
- A correct fix sends each goroutine's error back to `Summarise`, which returns it with the record's index, and restores the deleted test.

## G2 · major · concurrency

- Location: `head/orders/orders.go:35`
- Line: `s.add(l)`
- Cause: every goroutine calls `s.add` on the shared `Summary` with no lock, so the `+=` and `++` in `add` race.
- Trigger and consequence: any call with two or more records. Updates are lost, so `Lines`, `Units`, and `TotalCents` can come back too low, with no error.
- Rule: golang-practices, concurrency: a data race is a bug even when the test passes.
- Evidence: `go test -race ./...` reports `WARNING: DATA RACE` at `orders.go:43` through `orders.go:35`.
- A correct fix guards the totals with a mutex, or has each goroutine send its line to one goroutine that adds them.

## Must not report

Each of these would be a false finding.

- The closure capturing the loop variable `raw` at `orders/orders.go:34`. `go.mod` says `go 1.22`, where each iteration has its own `raw`. Before Go 1.22 it would be a defect.
- A missing `context.Context` on `Summarise`. It does no I/O and nothing in it can block for long, and the goroutines all end once decoding ends, so `wg.Wait` always returns.
- A goroutine leak. Every goroutine ends after one decode and one `add`, and `wg.Wait` waits for all of them.
- Anything in `base/`, which the change does not touch apart from the two files in the diff.
