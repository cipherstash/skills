"""A match that mypy proves covers every member of an Enum."""

from enum import Enum
from typing import assert_never


class Status(Enum):
    """An account's status."""

    ACTIVE = "active"
    SUSPENDED = "suspended"


def label(status: Status) -> str:
    """Return the label shown for a status."""
    match status:
        case Status.ACTIVE:
            return "active"
        case Status.SUSPENDED:
            return "suspended"
        case _:
            assert_never(status)
