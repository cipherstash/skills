"""A TypedDict with a key that may be missing."""

from typing import NotRequired, TypedDict


class UserDict(TypedDict):
    id: int
    name: str
    email: str
    age: NotRequired[int]  # Optional field


def create_user(data: UserDict) -> None:
    print(data["name"])  # Type-safe access
