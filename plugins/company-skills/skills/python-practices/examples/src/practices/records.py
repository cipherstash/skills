"""A TypedDict with a key that may be missing."""

from typing import NotRequired, TypedDict


class User(TypedDict):
    """A user record as the API sends it."""

    id: int
    name: str
    email: NotRequired[str]


def contact(user: User) -> str:
    """Return the user's email address, or their name when they have none."""
    return user.get("email", user["name"])
