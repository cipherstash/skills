# Typing

This reference targets Python 3.12 and mypy 2.4.1. Read the project's `requires-python` first. A rule that needs 3.13 or 3.14 names that version. Skip it when the project's lowest supported version is below it. The examples are in the [examples project](../examples/pyproject.toml), where `mypy --strict` checks them and their tests.

## Contents

- [Rules](#rules)
- [Structural types](#structural-types)
- [Signatures](#signatures)
- [Generics](#generics)
- [Narrowing](#narrowing)
- [mypy configuration](#mypy-configuration)

## Rules

- Annotate every parameter and return type, in source and tests. `mypy --strict` runs over both, so an untyped test or fixture fails CI.
- Take abstract collections from `collections.abc`, such as `Sequence`, `Mapping`, and `Iterable`, as parameters. Return concrete types, such as `list` and `dict`.
- Use `Literal["a", "b"]` for a small fixed set of strings. Write `X | None`, not `Optional[X]`, and the built-in generics `list[int]` and `dict[str, int]`, not `typing.List`. ruff's `UP` rules enforce both.
- Write generics in PEP 695 syntax: `def f[T](...)`, `class C[K, V]:`, and `type Alias = ...`. Never declare a `TypeVar`, subclass `Generic`, or annotate `TypeAlias`. ruff's `UP040`, `UP046`, and `UP047` fail on them at 3.12.
- Do not use `Any` where a type is known. Take `object` for a value of unknown type, and narrow it before use. A `cast` needs a comment saying why it is true. Every `# type: ignore` names its error code, as in `# type: ignore[arg-type]`, with a comment saying why. ruff's `PGH003` rejects a bare one.
- Put an import that only annotations use under `if TYPE_CHECKING:`, as ruff's `TC` rules say. Below 3.14, an annotation that names such an import, or a class not yet defined, is quoted. From 3.14 annotations are evaluated lazily, so the quotes are not needed.
- A type parameter default, as in `class Box[T = int]:`, needs 3.13. `typing.ReadOnly` for `TypedDict` keys needs 3.13.

## Structural types

Use a `Protocol` when callers only need a few methods. A class satisfies it by having them, without naming it, so `render(Circle(2.0, "red"))` type-checks for `def render(shape: Drawable)`. Add `@runtime_checkable` only when code must test it with `isinstance`. That test checks that the methods exist, not their signatures. From [`protocols.py`](../examples/src/practices/protocols.py):

```python
class Drawable(Protocol):
    def draw(self) -> str: ...

    @property
    def color(self) -> str: ...


class Circle:
    def __init__(self, radius: float, color: str) -> None:
        self.radius = radius
        self._color = color

    def draw(self) -> str:
        return f"Drawing {self._color} circle"

    @property
    def color(self) -> str:
        return self._color
```

Type a dict that comes from outside, such as decoded JSON, with a `TypedDict`. Mark a key that may be missing with `NotRequired`, and read it with `.get`. For data your own code creates, use a dataclass instead. From [`records.py`](../examples/src/practices/records.py):

```python
class UserDict(TypedDict):
    id: int
    name: str
    email: str
    age: NotRequired[int]  # Optional field
```

## Signatures

Annotate a method that returns its own instance with `Self`, so a subclass keeps its type through a chain of calls. From [`builder.py`](../examples/src/practices/builder.py):

```python
class Builder:
    def __init__(self) -> None:
        self._value = 0

    def add(self, n: int) -> Self:
        self._value += n
        return self

    def multiply(self, n: int) -> Self:
        self._value *= n
        return self
```

Use `@overload` when the return type depends on the argument types. The undecorated implementation comes last and accepts every overload's arguments. From [`overloads.py`](../examples/src/practices/overloads.py):

```python
@overload
def process(data: str) -> str: ...
@overload
def process(data: int) -> int: ...
def process(data: str | int) -> str | int:
    if isinstance(data, str):
        return data.upper()
    return data * 2
```

## Generics

A decorator takes the wrapped function's parameters as a `ParamSpec`, `**P`, so callers keep its signature. Use `functools.wraps` to keep its name and docstring. From [`decorators.py`](../examples/src/practices/decorators.py):

```python
def logging_decorator[**P, R](func: Callable[P, R]) -> Callable[P, R]:
    @functools.wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        print(f"Calling {func.__name__}")
        return func(*args, **kwargs)

    return wrapper
```

A generic class lists its type parameters after its name. From [`cache.py`](../examples/src/practices/cache.py):

```python
class Cache[K, V]:
    def __init__(self) -> None:
        self._data: dict[K, V] = {}

    def get(self, key: K) -> V | None:
        return self._data.get(key)

    def set(self, key: K, value: V) -> None:
        self._data[key] = value
```

## Narrowing

A function that checks a type returns `TypeIs[T]`, not `bool`. A `bool` narrows nothing. `TypeIs` narrows to `T` when it returns true, and away from `T` when it returns false, so it must return true only when the value really is a `T`. `TypeIs` is in `typing` from 3.13. Below that, import it from `typing_extensions`.

A check of a list's items cannot prove its type when the item type is already known: an empty `list[int]` passes, and mypy then treats the true branch as unreachable and checks nothing in it. So call this guard only on a `list[Any]`, such as decoded JSON. To narrow a list whose item type is known, use `TypeGuard`, which narrows only the true branch. From [`guards.py`](../examples/src/practices/guards.py):

```python
def is_string_list(val: list[Any]) -> TypeIs[list[str]]:
    """Runtime check for list of strings."""
    return all(isinstance(x, str) for x in val)
```

End an `if` chain or a `match` over an `Enum`, a `Literal`, or a union with `assert_never`. mypy then fails when a new value has no branch. From [`exhaustive.py`](../examples/src/practices/exhaustive.py):

```python
def handle_mode(mode: Literal["read", "write"]) -> str:
    if mode == "read":
        return "Reading"
    if mode == "write":
        return "Writing"
    # Mypy will error if mode can be anything else
    assert_never(mode)
```

## mypy configuration

Set `python_version` to the lowest version in `requires-python`, and `strict = true`. Add no flag that `strict` already sets. The rest of the suite's settings are in [checks.md](checks.md). From [`pyproject.toml`](../examples/pyproject.toml):

```toml
[tool.mypy]
python_version = "3.12"
strict = true
```
