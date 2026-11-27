# Step: performance

Area 8, medium priority. Read this, and typescript-practices' `references/performance.md`, before reviewing the change for inefficiency. The practices reference holds the rules and the profiling and benchmark commands. No check of the suite measures performance, so this area rests on reading. This file says what to report and what is not a finding.

## Contents

- [What to report](#what-to-report)
- [Is it a hot path?](#is-it-a-hot-path)
- [Evidence](#evidence)
- [Severity](#severity)
- [Not a finding](#not-a-finding)

## What to report

Obvious inefficiencies in code the change adds or alters:

- **Blocking the event loop**: `readFileSync`, `writeFileSync`, `execSync`, `pbkdf2Sync`, `scryptSync`, or another synchronous I/O or crypto call in code that serves requests; CPU-heavy work, such as hashing or parsing a large document, on the main thread where a worker or native code would do.
- **Repeated setup per call**: a regular expression, a schema, an `Intl` formatter such as `Intl.NumberFormat` or `Intl.DateTimeFormat`, or a client built inside a function that runs for every item or request, where the rule builds it once at module level.
- **Quadratic work** where linear is easy: `find`, `includes`, `indexOf`, or `filter` over an array inside a loop over the same data, where a `Map` or `Set` would do; `[...acc, item]` or `{ ...acc, [key]: value }` in a `reduce`, which copies the whole accumulator on each pass.
- **String building** by adding to a string one piece at a time in a loop over a large input.
- **Native calls one item at a time**: a loop that crosses into native code once per item where the library has a bulk call, such as a bulk encrypt.
- **Extra copies**: a buffer copied again on the way through the code where `subarray()` gives a view and no native call follows; bytes turned to base64 or hex and back between two functions that both take bytes.
- **Whole reads**: a large file or response read all at once with `readFile` or `response.text()` where the code could stream it.
- **Unbounded input**: input parsed, sorted, or matched with no size limit. When the cost is a hang an attacker can cause, report it once, under security.

## Is it a hot path?

State why the code runs often: it is in a loop over records or requests, a documentation comment or caller says so, or it serves every request. Code that runs once at start-up, in a command-line tool, or in a test is not a hot path, and the synchronous APIs are fine there.

## Evidence

- Reading: quote the line and the loop or caller that makes it hot.
- A benchmark, where cheap: you may add a `*.bench.ts` file in the temporary worktree and run `vitest bench` with a short run, and quote its numbers. It runs the change's code, so it runs only where `checks.md` allows tests to run. Say that it was written for the review.
- `tsc --extendedDiagnostics` shows a type that slows the type-check, such as a deeply recursive conditional type. It needs the change's dependencies, as `tsc --noEmit` does.

## Severity

- `minor` for most: an obvious inefficiency with no measured cost.
- `major` when the review shows a consequence under a concrete trigger: quadratic time or unbounded memory on input sizes the code is documented or shown to receive, or synchronous I/O that stops every request while it runs.

## Not a finding

- A micro-optimisation with no measurement, such as a `for` loop in place of `map` in cold code.
- Clear code on a cold path that could be faster.
- A setup cost paid once, such as a formatter built when a module loads.
- A change made for speed with no measurement in the pull request. Ask for the numbers in the summary; it is not a defect.
