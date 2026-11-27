"""Raising every error at once in an ExceptionGroup, and handling it with except*."""

from collections.abc import Mapping


def validate(record: Mapping[str, str]) -> None:
    """Raise an ExceptionGroup of every problem with record."""
    errors: list[ValueError] = []
    if not record.get("name"):
        errors.append(ValueError("name is empty"))
    if "@" not in record.get("email", ""):
        errors.append(ValueError("email has no @"))
    if errors:
        raise ExceptionGroup("invalid", errors)


def problems(record: Mapping[str, str]) -> list[str]:
    """Return a message for each problem with record."""
    found: list[str] = []
    try:
        validate(record)
    except* ValueError as group:
        found = [str(error) for error in group.exceptions]
    return found
