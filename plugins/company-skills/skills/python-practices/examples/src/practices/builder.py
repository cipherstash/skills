"""A builder whose methods return Self, so subclasses keep their own type."""

from typing import Self


class Builder:
    def __init__(self) -> None:
        self._value = 0

    def add(self, n: int) -> Self:
        self._value += n
        return self

    def multiply(self, n: int) -> Self:
        self._value *= n
        return self
