# Data types

This reference targets Python 3.12. Read the project's `requires-python` first. A rule that needs a later version names it. Skip it when the project's lowest supported version is below it. The examples are in the [examples project](../examples/pyproject.toml), where CI runs the check suite over them.

## Rules

- Model a record as a `@dataclass`. Make it `frozen=True` unless something must change it after it is built. A frozen dataclass whose fields are all immutable, such as tuples and other frozen dataclasses, is hashable and safe to share between tasks and threads. Freezing is shallow: a list field can still change, and hashing the instance raises `TypeError`. Change one with `dataclasses.replace`.
- Give a dataclass field a mutable default only through `field(default_factory=...)`. A plain `= []` would share one list between every instance, so `dataclass` rejects it when the class is defined. Never give a function parameter a mutable default either: ruff's `B006` flags it. Default to `None` and build the value inside.
- Use `TypedDict` for a dict whose shape is fixed by something outside your code, such as JSON. Use a dataclass for your own records. [typing.md](typing.md) covers `TypedDict`.
- Use an `Enum` for a closed set of values, not string constants. Read a value back with `Status(value)`, which raises `ValueError` for an unknown one. Match on the members, and end the match with `assert_never`, as [typing.md](typing.md) shows.
- Validate in `__post_init__`, and raise there, so no invalid instance exists.
- A function cached with `functools.cache` or `lru_cache` returns the same object to every caller. Return an immutable value, such as a tuple or a frozen dataclass, so no caller can change another's result.
- Open a resource with `with`. When the number of resources is known only at run time, enter each one on a `contextlib.ExitStack`. It closes all of them on exit, in reverse order, even when one raises.
- Use `pathlib.Path` for file paths. Do not test `path.exists()` before reading: the file can change between the two calls. Read it, and handle `FileNotFoundError`.

## Examples

From [`models.py`](../examples/src/practices/models.py):

```python
@dataclass(frozen=True)
class Point:
    x: float
    y: float

    def distance(self, other: "Point") -> float:
        return math.hypot(self.x - other.x, self.y - other.y)
```

Each cart gets its own list. From [`models.py`](../examples/src/practices/models.py):

```python
@dataclass
class ShoppingCart:
    user_id: int
    items: list[str] = field(default_factory=list)
```

From [`models.py`](../examples/src/practices/models.py):

```python
class Status(Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
```

If the second file is missing, the stack still closes the first. From [`models.py`](../examples/src/practices/models.py):

```python
def read_all(paths: list[Path]) -> list[str]:
    """Read every file, holding them all open, and close each one on exit."""
    with ExitStack() as stack:
        files = [stack.enter_context(path.open(encoding="utf-8")) for path in paths]
        return [file.read() for file in files]
```
