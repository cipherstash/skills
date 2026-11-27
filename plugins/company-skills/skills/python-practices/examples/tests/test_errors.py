"""Tests for the examples that references/errors.md quotes."""

import asyncio
import logging

import pytest

import practices
from practices.cancel import heartbeat
from practices.config import ConfigError, load_port
from practices.validation import problems


def test_a_wrapped_error_keeps_its_cause() -> None:
    with pytest.raises(ConfigError, match="'eighty'") as caught:
        load_port("eighty")
    assert isinstance(caught.value.__cause__, ValueError)


def test_a_valid_port_loads() -> None:
    assert load_port("8080") == 8080


def test_except_star_takes_every_error_in_the_group() -> None:
    assert problems({"name": "", "email": "nobody"}) == [
        "name is empty",
        "email has no @",
    ]
    assert problems({"name": "Ada", "email": "ada@example.com"}) == []


def test_a_cancelled_task_cleans_up_and_stays_cancelled() -> None:
    beats: list[str] = []

    async def main() -> bool:
        task = asyncio.create_task(heartbeat(beats, interval=3600))
        await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        return task.cancelled()

    assert asyncio.run(main()) is True
    assert beats == ["beat", "stopped"]


def test_the_library_adds_only_a_null_handler() -> None:
    handlers = logging.getLogger(practices.__name__).handlers
    assert [type(handler) for handler in handlers] == [logging.NullHandler]
