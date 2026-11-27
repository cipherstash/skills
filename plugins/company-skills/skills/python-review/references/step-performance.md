# Step: performance

Area 8, medium priority. Read this, and python-practices' `references/performance.md`, before reviewing the change for inefficiency. The practices reference holds the rules and the profiling tools. This file says what to report and what is not a finding.

## Contents

- [What to report](#what-to-report)
- [Hot paths](#hot-paths)
- [Evidence](#evidence)
- [Severity](#severity)
- [Version-sensitive rules](#version-sensitive-rules)
- [Not a finding](#not-a-finding)

## What to report

Obvious inefficiencies in code the change adds or alters:

- **A ruff `PERF` rule on a changed line**. Cite the practices rule the code breaks, where there is one. Examples:
  - `PERF401`, a loop that calls `append` where a comprehension fits;
  - `PERF102`, `.items()` where only the keys or the values are used.
- **The wrong data structure for the operation repeated**:
  - membership tested in a `list` inside a loop, where a `set` or `dict` would do;
  - `list.pop(0)` or `insert(0, ...)` on a queue, where `collections.deque` was meant;
  - a sort to find a minimum or the top N, where `min` or `heapq` would do.
- **Repeated work in a loop**, where one call before the loop would do. Examples are `re.compile`, a file read, a database query, and a new HTTP client per item.
- **String building** with `+=` in a loop, where `"".join(parts)` was meant.
- **Quadratic work** where linear is easy: a nested loop that searches a sequence for each element.
- **Unbounded memory**:
  - a whole file, response, or query result read into memory where it could be streamed;
  - a `functools.cache`, or an `lru_cache` with no `maxsize`, on arguments that vary without limit.
- **Missing reuse**: a new client or connection per request, so no connection is reused.
- **CPU-bound work on an event loop**, or threads used to speed up CPU-bound Python on a build with the GIL.

Unbounded concurrency and blocking calls in async code also touch the concurrency area. Report each once, in the area its consequence belongs to.

## Hot paths

State why the code runs often. It may run in a loop over records or requests, or serve every request. A docstring or a caller may say so. Code that runs once at start-up is not a hot path.

## Evidence

- ruff's `PERF` rules run with the suite's families. Quote the code and the line.
- Reading: quote the line and the loop or caller that makes it hot.
- A timing, where cheap: you may add a `timeit` measurement or a test in the temporary worktree, as `checks.md` describes. Run it only where the change's code may run. Quote its numbers, and say that it was written for the review. Keep the runs short.

## Severity

- `minor` for most: an obvious inefficiency, or a `PERF` rule broken, with no measured cost.
- `major` when the review shows a cost under a concrete trigger. An example is quadratic time or unbounded memory on input sizes the code is shown to receive.

## Version-sensitive rules

Read the module's floor from step 3 before you flag a rule or suggest a fix. `@dataclass(slots=True)` needs Python 3.10, and `itertools.batched` needs 3.12. Suggest no fix above the floor.

## Not a finding

- A micro-optimisation with no measurement and no rule behind it, such as caching an attribute in a local variable.
- Clear code on a cold path that could be faster.
- A loop that `ruff check` does not flag and that runs over a few items.
