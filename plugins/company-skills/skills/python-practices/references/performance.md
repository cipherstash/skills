# Performance

This reference targets Python 3.12. Read the project's `requires-python` first. A rule that needs a later version names it. Skip it when the project's lowest supported version is below it. It states its rules in prose and has no examples. ruff's `PERF` rules, which the suite runs, flag some of these.

## Measure first

- Make code correct and clear first. Change it for speed only when a measurement shows it is too slow, and keep the measurement in the pull request.
- Find where the time goes with a profiler before changing anything: `cProfile` for a whole run, or a sampling profiler such as py-spy for a running process. Time a small piece with `timeit`.
- A benchmark runs on the same machine, with the same Python, before and after the change. Report the change, not only the new number.

## Algorithms and data

- Pick the data structure for the operation you repeat. Test membership in a `set` or `dict`, not a `list`. Take from the front of a queue with `collections.deque`, not `list.pop(0)`. Use `heapq` for a running minimum or top N.
- Do not repeat work inside a loop. Move a call, an attribute lookup on a large object, or a compiled regular expression out of it.
- Build a string from many parts with `"".join(parts)`, not `+=` in a loop.
- Use a comprehension, not a loop that calls `append`, as ruff's `PERF401` asks. Use a generator expression when the caller only iterates once, so the whole list is never held in memory.
- Read a large file or response in chunks or lines, not all at once.
- Use the standard library's built-ins, such as `sum`, `min`, `max`, `sorted`, `any` and `all`. They run in C.
- Cache a pure function's result with `functools.cache` or `lru_cache` only when the same arguments recur. Return an immutable value, as [data-modelling.md](data-modelling.md) says. Bound the cache with `maxsize` when the arguments vary without limit.
- Give a class that has many instances `__slots__`, or `@dataclass(slots=True)`, to save memory.

## I/O and concurrency

- Most slow Python services wait on I/O. Fix the waits first: batch requests, reuse one client and its connection pool, and query only the rows and columns you need.
- Run independent I/O concurrently with `asyncio.TaskGroup`, or a thread pool for blocking libraries, bounded as [async.md](async.md) says.
- Threads do not speed up CPU-bound Python on a build with the GIL. Use `concurrent.futures.ProcessPoolExecutor`, a native extension, or a library such as NumPy that releases the GIL. [native-extensions.md](native-extensions.md) covers writing one.
- Never block an event loop with CPU-bound work. Hand it to a process pool with `loop.run_in_executor`, and await the result.

## What not to do

- Do not trade readability for a gain you have not measured, such as caching a global in a local variable or avoiding a function call.
- Do not add a cache, a pool, or a background thread without a way to bound and close it.
