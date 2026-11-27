"""An if chain that mypy proves covers every value of a Literal."""

from typing import Literal, assert_never


def handle_mode(mode: Literal["read", "write"]) -> str:
    if mode == "read":
        return "Reading"
    if mode == "write":
        return "Writing"
    # Mypy will error if mode can be anything else
    assert_never(mode)
