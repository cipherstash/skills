# Step: concurrency and async

Area 5, medium priority. Read this, and python-practices' `references/async.md`, before reviewing the change's tasks, threads, locks, and event loops. When the change is in a pyo3 or maturin package, also read `references/native-extensions.md`. It covers releasing the GIL and free-threading in Rust code.

The practices references hold the rules and working examples. This file says what to look for in a change, what evidence shows it, and what is not a finding.

## Contents

- [Who starts, stops, and waits](#who-starts-stops-and-waits)
- [Tasks nothing keeps or awaits](#tasks-nothing-keeps-or-awaits)
- [Waits with no deadline, and a blocked event loop](#waits-with-no-deadline-and-a-blocked-event-loop)
- [Shared state](#shared-state)
- [Deadlocks](#deadlocks)
- [Evidence](#evidence)
- [Version-sensitive rules](#version-sensitive-rules)
- [Not a finding](#not-a-finding)

## Who starts, stops, and waits

List each task, thread, lock, queue, and shared resource that the change adds or alters. For each, write down who starts it, who stops it, who waits for it, and who closes what it uses. Follow the error, cancellation, and early-return paths as well as success. Most concurrency defects show up as a gap in that list.

## Tasks nothing keeps or awaits

Report a task the change creates, with `asyncio.create_task` or `loop.create_task`, when:

- nothing keeps a reference to it. The event loop holds only a weak one, so the task can be destroyed mid-run;
- nothing awaits it before what it needs goes away. An example is a client that the task's own `async with` block closes, or `asyncio.run` returning and cancelling it;
- its exception is never read, so a failure is only logged as "Task exception was never retrieved", if at all.

Also report `asyncio.gather` without `return_exceptions=True` where one failure leaves the other tasks running, and a `TaskGroup` replaced by `gather` with no reason. Cite the practices rules: run concurrent tasks in an `asyncio.TaskGroup`, and keep a reference to every task until it is done.

The trigger is the normal path, or a failure in one task. The consequence is work that never finishes, a result that is empty or partial, and an error the caller never sees. This is `major`, as the finding contract says for a dropped error or a task leak.

## Waits with no deadline, and a blocked event loop

Report a changed wait on the network, a queue, a lock, or a task, where the peer can hang and nothing sets a deadline. It has no `asyncio.timeout`, and its client sets no timeout.

Report an async function that takes a `timeout` parameter, as ruff's `ASYNC109` flags: the caller sets the deadline.

Report a blocking call inside `async def`, as ruff's `ASYNC` rules flag. Examples are `time.sleep`, a blocking HTTP client, `open`, and `subprocess.run`. It stops every other task on the loop while it runs. Report an event loop created or run by hand, other than one `asyncio.run` at the program's entry point.

## Shared state

Write threaded code as if every build were free-threaded, as the practices reference says. Report state that more than one thread or task changes, with no `threading.Lock` or `asyncio.Lock` around it:

- mutable state at module level that a function changes, such as a cache or a counter. Cite the practices rule: keep no mutable state at module level;
- a read-modify-write that spans an `await`, such as reading a count, awaiting, and writing it back;
- `x += 1`, `d[k] = d.get(k, 0) + 1`, and check-then-set on shared values. Each is several steps, under the GIL too;
- a list or dict iterated while another thread changes it, and an `asyncio` object shared between threads.

The consequence is lost updates or a `RuntimeError` such as "dictionary changed size during iteration", varying from run to run. It is `major` when the review shows two threads or tasks reaching the state. It is `minor` when only the practices rule is broken, such as module-level state that a single-threaded script changes.

## Deadlocks

Report a wait that can never end:

- two locks taken in different orders on different paths;
- a lock held across an `await` that waits for a task that needs the same lock;
- a `queue.Queue.join` or `asyncio.Queue.join` whose workers stop before calling `task_done`;
- a coroutine called from a thread with `asyncio.run` while a loop runs there, where `asyncio.run_coroutine_threadsafe` was meant;
- in a native extension, a Rust lock held while calling back into Python.

## Evidence

- ruff's `ASYNC` and `RUF006` rules: quote the code and the line. `RUF006` flags a `create_task` result that nothing stores.
- Reading: no Python tool finds a data race, as python-practices' `references/checks.md` says. Name the threads or tasks that reach the state, and the lines they reach it on.
- A test: to show a lost task or a race, you may add a test in the temporary worktree, as `checks.md` describes. Quote its output. A race may not happen on every run. A run that shows it is evidence; a run that does not show it is not evidence that there is none.

## Version-sensitive rules

Read the module's floor from step 3 before you flag a rule or suggest a fix. `asyncio.TaskGroup` and `asyncio.timeout` need Python 3.11. Below 3.11, flag none of the rules that need them, and suggest `asyncio.wait_for` and a kept set of tasks instead. The free-threaded build needs Python 3.13.

## Not a finding

- A task created inside a `TaskGroup`. The group keeps and awaits it.
- A background task with a documented owner that keeps it and cancels it on shutdown.
- `asyncio.gather` where every task must run to the end whatever the others do, with each result checked for `BaseException`.
- Module-level state that nothing changes after import, such as a constant or a compiled regular expression.
- A `threading.Lock` where an `asyncio.Lock` would also work, when the code is correct. That is a design preference.
- A swallowed `CancelledError`. That belongs to the error handling area.
