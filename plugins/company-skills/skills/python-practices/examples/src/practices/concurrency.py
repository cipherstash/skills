"""Task groups, timeouts, bounding, locks, cleanup, and task references."""

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable, Coroutine
from contextlib import asynccontextmanager
from contextvars import ContextVar
from typing import Protocol

REPLY_SECONDS = 5.0


async def square(item: int) -> int:
    if item < 0:
        raise ValueError(item)
    await asyncio.sleep(0)
    return item * item


async def process_batch(items: list[int]) -> list[int]:
    async with asyncio.TaskGroup() as group:
        tasks = [group.create_task(square(item)) for item in items]
    return [task.result() for task in tasks]


async def first_reply(replies: asyncio.Queue[str]) -> str:
    async with asyncio.timeout(REPLY_SECONDS):
        return await replies.get()


class RateLimiter:
    def __init__(self, max_concurrent: int) -> None:
        self._semaphore = asyncio.Semaphore(max_concurrent)

    async def run[T](self, job: Callable[[], Awaitable[T]]) -> T:
        async with self._semaphore:
            return await job()


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


class Session(Protocol):
    async def commit(self) -> None: ...
    async def rollback(self) -> None: ...
    async def close(self) -> None: ...


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


request_id: ContextVar[str | None] = ContextVar("request_id", default=None)


def tagged(message: str) -> str:
    rid = request_id.get()
    return message if rid is None else f"[{rid}] {message}"
