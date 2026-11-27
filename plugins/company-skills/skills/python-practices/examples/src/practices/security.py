"""Queries, tokens, subprocesses and secrets that handle untrusted input safely."""

import hmac
import secrets
import shutil
import sqlite3
import subprocess
from pathlib import Path

from practices.accounts import User

TOKEN_BYTES = 32


def connect(database: str) -> sqlite3.Connection:
    """Open the database and create the users table."""
    conn = sqlite3.connect(database)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, name, email)"
    )
    return conn


def add_user(conn: sqlite3.Connection, name: str, email: str) -> int:
    query = "INSERT INTO users (name, email) VALUES (?, ?) RETURNING id"
    (user_id,) = conn.execute(query, (name, email)).fetchone()
    return int(user_id)


def find_user(conn: sqlite3.Connection, email: str) -> User | None:
    query = "SELECT id, name, email FROM users WHERE email = ?"
    row = conn.execute(query, (email,)).fetchone()
    return None if row is None else User(*row)


def new_token() -> bytes:
    return secrets.token_bytes(TOKEN_BYTES)


def token_matches(given: bytes, expected: bytes) -> bool:
    return hmac.compare_digest(given, expected)


class MissingToolError(Exception):
    def __init__(self, name: str) -> None:
        super().__init__(f"{name} is not on PATH")


def blob_id(path: Path) -> str:
    """Return the Git blob ID of the file at path."""
    git = shutil.which("git")
    if git is None:
        raise MissingToolError("git")
    result = subprocess.run(  # noqa: S603  # An argument list with no shell.
        [git, "hash-object", "--", str(path)],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


class Secret:
    """A value that never appears in repr, str, or a log line."""

    __slots__ = ("_value",)

    def __init__(self, value: str) -> None:
        self._value = value

    def __repr__(self) -> str:
        return "Secret('[REDACTED]')"

    __str__ = __repr__

    def reveal(self) -> str:
        return self._value
