"""User accounts, which the security and testing examples share."""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class User:
    id: int
    name: str
    email: str


class UserStore(Protocol):
    async def fetch_user(self, user_id: int) -> User: ...


async def display_name(store: UserStore, user_id: int) -> str:
    """Return the user's name and email address, as a mail client shows them."""
    user = await store.fetch_user(user_id)
    return f"{user.name} <{user.email}>"


def is_valid_email(email: str) -> bool:
    """Report whether email has a local part, an @, and a domain."""
    local, at, domain = email.partition("@")
    return bool(local and at and domain)
