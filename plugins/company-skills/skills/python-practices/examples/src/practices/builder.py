"""A builder whose methods return Self, so subclasses keep their own type."""

from typing import Self


class Request:
    """An HTTP request, built one header at a time."""

    def __init__(self) -> None:
        self.headers: dict[str, str] = {}

    def with_header(self, name: str, value: str) -> Self:
        self.headers[name] = value
        return self


class AuthRequest(Request):
    """A request that carries a bearer token."""

    def with_token(self, token: str) -> Self:
        return self.with_header("Authorization", f"Bearer {token}")
