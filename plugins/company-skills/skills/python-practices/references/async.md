# Async and threads

This reference targets Python 3.12. Read the project's `requires-python` first. A rule that needs a later version names it. Skip it when the project's lowest supported version is below it. The examples are in the [examples project](../examples/pyproject.toml), where CI runs the check suite over them.

## Rules

- Run concurrent tasks in an `asyncio.TaskGroup`. When one fails, the group cancels the rest and raises an `ExceptionGroup`, which [errors.md](errors.md) handles with `except*`. Use `asyncio.gather` only when every task must run to the end whatever the others do. Then check each result for `BaseException`, since a cancelled task comes back as a `CancelledError` value. Open a resource the tasks share, such as a client, outside the group, so it outlives them. Put a deadline on a wait with `async with asyncio.timeout(...)`. Give an async function no `timeout` parameter, which ruff's `ASYNC109` flags: the caller sets the deadline.
- Bound concurrency with an `asyncio.Semaphore`. Guard a read-modify-write that spans an `await` with an `asyncio.Lock`. Release what a task holds in `finally` or an async context manager, so a cancelled task still cleans up. Keep a reference to every task you create until it is done. The event loop holds only a weak one, so a task nothing refers to can be destroyed mid-run. Create tasks only inside a running coroutine. Never block the event loop. Run a blocking call with `asyncio.to_thread`. ruff's `ASYNC` rules flag `time.sleep`, blocking HTTP, and `open` in async code. Start a program with one `asyncio.run(main())`. Never create or run an event loop by hand.

## Examples

A task group returns once every task is done. From [`concurrency.py`](../examples/src/practices/concurrency.py):
```python
async def process_batch(items: list[int]) -> list[int]:
    async with asyncio.TaskGroup() as group:
        tasks = [group.create_task(square(item)) for item in items]
    return [task.result() for task in tasks]
```

The deadline is a module constant, not a parameter. When it passes, the wait raises the built-in `TimeoutError`. From [`concurrency.py`](../examples/src/practices/concurrency.py):
```python
async def first_reply(replies: asyncio.Queue[str]) -> str:
    async with asyncio.timeout(REPLY_SECONDS):
        return await replies.get()
```

From [`concurrency.py`](../examples/src/practices/concurrency.py):
```python
class RateLimiter:
    def __init__(self, max_concurrent: int) -> None:
        self._semaphore = asyncio.Semaphore(max_concurrent)

    async def run[T](self, job: Callable[[], Awaitable[T]]) -> T:
        async with self._semaphore:
            return await job()
```

Without the lock, two tasks read the same count across the `await`, and one update is lost. From [`concurrency.py`](../examples/src/practices/concurrency.py):
```python
class Counters:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._counts: dict[str, int] = {}

    async def add(self, key: str, amount: int) -> int:
        async with self._lock:
            current = self._counts.get(key, 0)
            await asyncio.sleep(0)
            self._counts[key] = current + amount
            return self._counts[key]
```

From [`concurrency.py`](../examples/src/practices/concurrency.py):
```python
@asynccontextmanager
async def transaction[S: Session](session: S) -> AsyncIterator[S]:
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()
```

A task that no group owns goes in a set, and leaves it when it is done. Call `spawn` from inside a coroutine. From [`concurrency.py`](../examples/src/practices/concurrency.py):
```python
class BackgroundTasks:
    def __init__(self) -> None:
        self._tasks: set[asyncio.Task[None]] = set()

    def spawn(self, coro: Coroutine[None, None, None]) -> None:
        task = asyncio.create_task(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def shutdown(self) -> None:
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
```

## Threads and free-threading

Python 3.13 and later have a free-threaded build with no GIL. Write threaded code as if every build were free-threaded: the GIL never made a compound operation atomic. No suite tool finds a data race, as [checks.md](checks.md#no-race-detector) says, so review checks these rules:
- Keep no mutable state at module level. Pass state in, or hold per-request state in a `ContextVar`, which each thread and each task sees on its own.
- Guard state that threads share with a `threading.Lock`. `x += 1`, `d[k] = d.get(k, 0) + 1`, and check-then-set are each several steps.
- Iterate over a copy of a list or dict that another thread may change. Never share an `asyncio` object between threads. Hand work to a loop with `asyncio.run_coroutine_threadsafe`.
- An extension module that does not declare free-threading support turns the GIL back on. [native-extensions.md](native-extensions.md) says how to declare it.

From [`concurrency.py`](../examples/src/practices/concurrency.py):
```python
request_id: ContextVar[str | None] = ContextVar("request_id", default=None)


def tagged(message: str) -> str:
    rid = request_id.get()
    return message if rid is None else f"[{rid}] {message}"
```
