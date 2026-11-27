"""An overloaded function whose return type follows its argument type."""

from typing import overload


@overload
def double(value: int) -> int: ...
@overload
def double(value: str) -> str: ...
def double(value: int | str) -> int | str:
    """Return the number times two, or the string twice."""
    return value * 2
