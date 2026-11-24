# Step: performance

Area 7, medium priority. Read this, and golang-practices' `references/performance.md`, before reviewing the change for inefficiency. The practices reference holds the rules and the benchmark and profiling commands. This file says what to report and what is not a finding.

## Contents

- [What to report](#what-to-report)
- [Is it a hot path?](#is-it-a-hot-path)
- [Evidence](#evidence)
- [Severity](#severity)
- [Not a finding](#not-a-finding)

## What to report

Obvious inefficiencies in code the change adds or alters:

- **Slices and maps grown without capacity** when the final length is known, such as appending one element per input to `var out []T` instead of `make([]T, 0, len(in))`, or a map filled from a slice with no size hint.
- **Allocation in hot loops**: a `[]byte` or `string` built per record where a reused buffer or `strconv.Append...` would do; `string`/`[]byte` conversions on each pass; values boxed into `any` on each pass.
- **Repeated setup in a loop or per call**: `regexp.MustCompile`, `template.Parse`, `json` schema compilation, or a new `http.Client` per request.
- **String building** with `+=` in a loop, which copies the whole string on each pass.
- **Quadratic work** where linear is easy: a nested loop that searches a slice for each element, where a map would do; `slices.Contains` inside a loop over the same data.
- **Unbounded work**: one goroutine per item with no limit, or reading a whole stream into memory when it could be streamed. These also touch concurrency and security; report each once, in the area its consequence belongs to.
- **Missing reuse**: a `bufio.Writer` or `bufio.Scanner` not used for many small reads or writes; an HTTP response body not read to the end and closed, so the connection is not reused.

## Is it a hot path?

State why the code runs often: it is in a loop over records or requests, a doc comment or caller says so, or it serves every request. Code that runs once at start-up is not a hot path.

## Evidence

- Reading: quote the line and the loop or caller that makes it hot.
- A benchmark or allocation count from the repository's own results, when the change or its pull request includes them. The review runs no benchmark; to ask for one, name it in the fix.
- `go build -gcflags=-m <package>`, the escape-analysis probe in `checks.md`. It compiles and runs nothing of the change; quote the line for the value in question.

## Severity

- `minor` for most: an obvious inefficiency with no measured cost.
- `major` when the review shows a consequence under a concrete trigger: quadratic time or unbounded memory on input sizes the code is documented or shown to receive.

## Not a finding

- A micro-optimisation with no measurement, such as preferring an array to a slice in cold code.
- Clear code on a cold path that could be faster.
- An append without capacity when the final length is not known.
