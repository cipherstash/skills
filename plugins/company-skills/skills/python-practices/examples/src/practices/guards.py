"""A TypeIs guard, which narrows the type in both branches."""

from typing import Any

from typing_extensions import TypeIs


def is_string_list(val: list[Any]) -> TypeIs[list[str]]:
    """Runtime check for list of strings."""
    return all(isinstance(x, str) for x in val)
