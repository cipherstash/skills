"""A TypeIs guard, which narrows the type in both branches."""

from typing_extensions import TypeIs


def is_str_list(value: object) -> TypeIs[list[str]]:
    """Report whether value is a list whose items are all strings."""
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


def join_names(value: object) -> str:
    """Join a list of names with commas, or show any other value as it is."""
    if is_str_list(value):
        return ", ".join(value)
    return repr(value)
