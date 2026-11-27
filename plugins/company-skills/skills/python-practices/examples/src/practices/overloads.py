"""An overloaded function whose return type follows its argument type."""

from typing import overload


@overload
def process(data: str) -> str: ...
@overload
def process(data: int) -> int: ...
def process(data: str | int) -> str | int:
    if isinstance(data, str):
        return data.upper()
    return data * 2
