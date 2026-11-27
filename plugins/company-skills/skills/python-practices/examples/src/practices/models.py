"""Data types: frozen dataclasses, default factories, enums, and ExitStack."""

import math
from contextlib import ExitStack
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


@dataclass(frozen=True)
class Point:
    x: float
    y: float

    def distance(self, other: "Point") -> float:
        return math.hypot(self.x - other.x, self.y - other.y)


@dataclass
class ShoppingCart:
    user_id: int
    items: list[str] = field(default_factory=list)


class Status(Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


def read_all(paths: list[Path]) -> list[str]:
    """Read every file, holding them all open, and close each one on exit."""
    with ExitStack() as stack:
        files = [stack.enter_context(path.open(encoding="utf-8")) for path in paths]
        return [file.read() for file in files]
