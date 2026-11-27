"""Tests for the examples that references/security.md quotes."""

import logging
import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from practices.accounts import User
from practices.security import (
    Secret,
    add_user,
    blob_id,
    connect,
    find_user,
    new_token,
    token_matches,
)


@pytest.fixture
def db() -> Iterator[sqlite3.Connection]:
    conn = connect(":memory:")
    yield conn
    conn.close()


def test_a_parameterized_query_treats_input_as_a_value(db: sqlite3.Connection) -> None:
    user_id = add_user(db, "Ada", "ada@example.com")
    assert find_user(db, "ada@example.com") == User(user_id, "Ada", "ada@example.com")
    assert find_user(db, "' OR '1'='1") is None


def test_a_token_has_the_length_asked_for() -> None:
    first, second = new_token(), new_token()
    assert len(first) == len(second) == 32
    assert first != second


def test_tokens_compare_in_constant_time() -> None:
    token = new_token()
    assert token_matches(token, token)
    assert not token_matches(bytes(32), token)


def test_subprocess_takes_a_hostile_name_as_one_argument(tmp_path: Path) -> None:
    path = tmp_path / "; rm -rf ~"
    path.write_bytes(b"hello\n")
    # The blob ID Git gives the bytes b"hello\n".
    assert blob_id(path) == "ce013625030ba8dba906f756967f9e9ca394464a"


def test_a_secret_stays_out_of_repr_str_and_logs(
    caplog: pytest.LogCaptureFixture,
) -> None:
    secret = Secret("hunter2")
    caplog.set_level(logging.INFO)
    logging.getLogger("test").info("loaded %s, %r", secret, secret)
    for text in (repr(secret), str(secret), f"{secret}", caplog.text):
        assert "hunter2" not in text
    assert secret.reveal() == "hunter2"
