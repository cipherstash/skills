"""Tests for the examples that references/async.md quotes."""

import asyncio
import gc
from unittest.mock import AsyncMock

import pytest

from practices import concurrency
from practices.concurrency import (
    BackgroundTasks,
    Counters,
    RateLimiter,
    first_reply,
    process_batch,
    request_id,
    tagged,
    transaction,
)


@pytest.mark.asyncio
async def test_a_task_group_returns_every_result_in_order() -> None:
    assert await process_batch([1, 2, 3]) == [1, 4, 9]


@pytest.mark.asyncio
async def test_a_task_group_cancels_the_rest_when_one_fails() -> None:
    with pytest.raises(ExceptionGroup) as caught:
        await process_batch([1, -1, 2])
    assert caught.group_contains(ValueError, match="-1")


@pytest.mark.asyncio
async def test_a_timeout_gives_up_waiting(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(concurrency, "REPLY_SECONDS", 0.01)
    replies: asyncio.Queue[str] = asyncio.Queue()
    with pytest.raises(TimeoutError):
        await first_reply(replies)
    replies.put_nowait("pong")
    assert await first_reply(replies) == "pong"


@pytest.mark.asyncio
async def test_a_semaphore_bounds_how_many_jobs_run_at_once() -> None:
    limiter = RateLimiter(max_concurrent=2)
    running, peak = 0, 0

    async def job() -> None:
        nonlocal running, peak
        running += 1
        peak = max(peak, running)
        await asyncio.sleep(0.01)
        running -= 1

    async with asyncio.TaskGroup() as group:
        for _ in range(6):
            group.create_task(limiter.run(job))
    assert peak == 2


@pytest.mark.asyncio
async def test_a_lock_keeps_every_update() -> None:
    counters = Counters()
    async with asyncio.TaskGroup() as group:
        adds = [group.create_task(counters.add("hits", 1)) for _ in range(50)]
    assert sorted(add.result() for add in adds) == list(range(1, 51))


@pytest.mark.asyncio
async def test_a_transaction_commits_then_closes() -> None:
    session = AsyncMock()
    async with transaction(session):
        pass
    session.commit.assert_awaited_once_with()
    session.rollback.assert_not_awaited()
    session.close.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_a_transaction_rolls_back_on_error_then_closes() -> None:
    session = AsyncMock()
    with pytest.raises(KeyError):
        async with transaction(session):
            raise KeyError("id")
    session.commit.assert_not_awaited()
    session.rollback.assert_awaited_once_with()
    session.close.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_a_background_task_runs_with_no_other_reference() -> None:
    tasks = BackgroundTasks()
    done = asyncio.Event()

    async def job() -> None:
        await asyncio.sleep(0)
        done.set()

    tasks.spawn(job())
    gc.collect()
    async with asyncio.timeout(1):
        await done.wait()


@pytest.mark.asyncio
async def test_shutdown_cancels_what_is_still_running() -> None:
    tasks = BackgroundTasks()
    stopped = asyncio.Event()

    async def job() -> None:
        try:
            await asyncio.sleep(3600)
        finally:
            stopped.set()

    tasks.spawn(job())
    await asyncio.sleep(0)
    await tasks.shutdown()
    assert stopped.is_set()


@pytest.mark.asyncio
async def test_each_task_sees_its_own_context_var() -> None:
    async def handle(rid: str) -> str:
        request_id.set(rid)
        await asyncio.sleep(0)
        return tagged("done")

    async with asyncio.TaskGroup() as group:
        first = group.create_task(handle("a"))
        second = group.create_task(handle("b"))
    assert (first.result(), second.result()) == ("[a] done", "[b] done")
    assert tagged("idle") == "idle"
