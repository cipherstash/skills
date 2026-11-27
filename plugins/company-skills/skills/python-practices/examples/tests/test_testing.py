"""Tests that references/testing.md quotes as its examples."""

import asyncio
import sqlite3
from collections.abc import AsyncIterator, Callable, Iterator
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from hypothesis import example, given
from hypothesis import strategies as st

from practices.accounts import User, display_name, is_valid_email
from practices.concurrency import BackgroundTasks
from practices.frames import FrameError, decode_frame, encode_frame
from practices.security import add_user, connect, find_user


@pytest.fixture
def db() -> Iterator[sqlite3.Connection]:
    conn = connect(":memory:")
    yield conn
    conn.close()


type MakeUser = Callable[[str], User]


@pytest.fixture
def make_user(db: sqlite3.Connection) -> MakeUser:
    def make(name: str) -> User:
        email = f"{name.lower()}@example.com"
        return User(add_user(db, name, email), name, email)

    return make


@pytest.mark.parametrize("name", ["Alice", "Bob"])
def test_a_stored_user_can_be_found(
    db: sqlite3.Connection, make_user: MakeUser, name: str
) -> None:
    user = make_user(name)
    assert find_user(db, user.email) == user


@pytest.mark.parametrize(
    ("email", "valid"),
    [
        ("user@example.com", True),
        ("invalid", False),
        ("@example.com", False),
        ("user@", False),
    ],
    ids=["valid", "no_at", "no_user", "no_domain"],
)
def test_email_validation(email: str, valid: bool) -> None:
    assert is_valid_email(email) == valid


@pytest.mark.asyncio
async def test_display_name_fetches_the_user_once() -> None:
    store = AsyncMock()
    store.fetch_user.return_value = User(1, "Alice", "alice@example.com")
    assert await display_name(store, 1) == "Alice <alice@example.com>"
    store.fetch_user.assert_awaited_once_with(1)


@pytest_asyncio.fixture
async def tasks() -> AsyncIterator[BackgroundTasks]:
    background = BackgroundTasks()
    yield background
    await background.shutdown()


@pytest_asyncio.fixture
async def job_stopped() -> AsyncIterator[asyncio.Event]:
    # Requested before tasks, so pytest tears it down after tasks.
    stopped = asyncio.Event()
    yield stopped
    assert stopped.is_set(), "the tasks fixture left the job running"


async def run_until_cancelled(stopped: asyncio.Event) -> None:
    try:
        await asyncio.sleep(3600)
    finally:
        stopped.set()


@pytest.mark.asyncio
async def test_an_async_fixture_cleans_up_after_the_test(
    job_stopped: asyncio.Event,
    tasks: BackgroundTasks,
) -> None:
    tasks.spawn(run_until_cancelled(job_stopped))
    await asyncio.sleep(0)
    assert not job_stopped.is_set()


@st.composite
def users(draw: st.DrawFn) -> User:
    name = draw(st.text(min_size=1, max_size=50))
    return User(id=draw(st.integers(min_value=1)), name=name, email=draw(st.emails()))


@given(users())
def test_every_generated_user_has_a_valid_email(user: User) -> None:
    assert is_valid_email(user.email)


@given(st.binary())
@example(b"")
@example(b"\x05abc")
@example(b"\x00")
def test_decode_frame_rejects_or_round_trips(data: bytes) -> None:
    try:
        payload = decode_frame(data)
    except FrameError:
        return
    assert encode_frame(payload) == data
