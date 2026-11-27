# Errors and logging

This reference targets Python 3.12. Read the project's `requires-python` first. A rule that needs a later version names it. Skip it when the project's lowest supported version is below it. The examples are in the [examples project](../examples/pyproject.toml), where CI runs the check suite over them.

## Rules

- Catch the narrowest exception that you can handle, at the place that can handle it. Never write a bare `except:`. Catch `Exception` only at a boundary, such as a request handler or a worker loop, and log or re-raise there. ruff's `BLE001` flags the rest.
- Inside `except`, raise a new error with `raise NewError(...) from error`, so the cause stays in the traceback. ruff's `B904` flags a raise without `from`. Use `from None` only when the cause would mislead the reader.
- Re-raise the same error with a bare `raise`, not `raise error`.
- Define an error class for each failure that callers handle differently, and give a library one base class for the rest. Build the message in the class's `__init__`, from the values passed in, as ruff's `TRY003` asks.
- To add context without changing the type, call `error.add_note(...)` and re-raise.
- Handle an error once: raise it or log it, not both.

## Chaining

An error raised from another keeps it as `__cause__`. From [`config.py`](../examples/src/practices/config.py):

```python
class ConfigError(Exception):
    """A configuration value could not be read."""

    def __init__(self, key: str, value: str) -> None:
        super().__init__(f"{key} is not valid: {value!r}")


def load_port(text: str) -> int:
    """Read a port number from the configuration."""
    try:
        return int(text)
    except ValueError as error:
        raise ConfigError("port", text) from error
```

## Several errors at once

When several independent things fail and the caller needs every failure, raise an `ExceptionGroup`. `asyncio.TaskGroup` raises one too. Handle a group with `except*`, not `except`. Each `except*` clause gets the subgroup of errors that match its type, and an unmatched error goes on up. A clause cannot `return`, `break`, or `continue`, so set a variable in it instead.

Give the group a one-word message, such as `"invalid"`, and let its errors carry the detail. From [`validation.py`](../examples/src/practices/validation.py):

```python
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
```

## Cancellation

`asyncio.CancelledError` is a `BaseException`, so `except Exception` does not catch it. `TaskGroup`, `asyncio.timeout`, and task cancellation all depend on it reaching the event loop.

Put cleanup in `finally` where you can. When you must catch `CancelledError`, clean up and re-raise it. Never swallow it. From [`cancel.py`](../examples/src/practices/cancel.py):

```python
async def heartbeat(beats: list[str], interval: float) -> None:
    """Record a beat every interval seconds until cancelled."""
    try:
        while True:
            beats.append("beat")
            await asyncio.sleep(interval)
    except asyncio.CancelledError:
        beats.append("stopped")
        raise
```

## Logging

- Get a module's logger with `logging.getLogger(__name__)`.
- A library adds only a `NullHandler`, once, to its top-level package's logger. It never calls `logging.basicConfig`, and never adds another handler or sets a level. The application configures logging once, at its entry point.
- Call `logger.exception(...)` only inside `except`, where it logs the traceback. Elsewhere, use `logger.error(...)`.
- Pass values as arguments, as in `logger.info("loaded %s", path)`, not in an f-string, so the message is built only when it is logged.
- Keeping secrets out of logs is a security rule. It is not in this reference.

The package's `__init__.py` adds the `NullHandler`. From [`__init__.py`](../examples/src/practices/__init__.py):

```python
# Package-level configuration
import logging

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())
```
