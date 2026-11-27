# Testing

This reference targets Python 3.12. Read the project's `requires-python` first. A rule that needs a later version names it. Skip it when the project's lowest supported version is below it. The examples are in the [examples project](../examples/pyproject.toml), where CI runs the check suite over them.

## Contents

- Rules
- Fixtures
- Parametrize
- Async tests and mocks
- Property tests
- Configuration

## Rules

- Write tests with pytest, as plain functions named `test_<behaviour>`. Use `assert`, not `self.assertEqual`. Tests may ignore ruff's `S101`, `S105` and `S106`, and nothing else.
- Annotate every test, fixture and helper, so `mypy --strict` passes over the tests as it does over the source. A fixture's return type is what the test receives: `Iterator[T]` for a fixture that yields, and the value's type otherwise.
- Test behaviour through the public interface. Mock only what crosses a process boundary, such as a network client or a clock. Patch a name where the code under test looks it up, not where it is defined.
- Use `pytest.raises(Error, match=...)` for an expected error, and keep the block to the one call that raises.
- Use `tmp_path` for files, `monkeypatch` for environment variables and module attributes, and `caplog` for log lines. Never write outside `tmp_path`.
- Register every custom marker under `markers` in `[tool.pytest.ini_options]`. `--strict-markers` fails a test with a marker that is not registered.
- Coverage is reported with `pytest --cov --cov-branch`, with no threshold. Read the missed lines and branches. Do not add a test only to raise the number.
- A function that parses or decodes untrusted input gets a Hypothesis `@given` test with `@example` seeds. See [Property tests](#property-tests).

## Fixtures

A fixture that holds a resource yields it, and cleans up after the `yield`. From [`test_testing.py`](../examples/tests/test_testing.py):

```python
@pytest.fixture
def db() -> Iterator[sqlite3.Connection]:
    conn = connect(":memory:")
    yield conn
    conn.close()
```

A factory fixture returns a function, so each test makes the values it needs. Name the function's type with a `type` alias, so tests can annotate the parameter. From [`test_testing.py`](../examples/tests/test_testing.py):

```python
type MakeUser = Callable[[str], User]
```

From [`test_testing.py`](../examples/tests/test_testing.py):

```python
@pytest.fixture
def make_user(db: sqlite3.Connection) -> MakeUser:
    def make(name: str) -> User:
        email = f"{name.lower()}@example.com"
        return User(add_user(db, name, email), name, email)

    return make
```

Put a fixture that more than one test file uses in `conftest.py`. Keep the rest in the file that uses them.

## Parametrize

Give `parametrize` its names as a tuple, and give each case an `id`, so a failure names the case. ruff's `PT006` and `PT007` check the shapes. From [`test_testing.py`](../examples/tests/test_testing.py):

```python
@pytest.mark.parametrize(
    ("email", "valid"),
    [
        ("user@example.com", True),
        ("invalid", False),
        ("@example.com", False),
        ("user@", False),
    ],
    ids=["valid", "no_at", "no_user", "no_domain"],
)
def test_email_validation(email: str, valid: bool) -> None:
    assert is_valid_email(email) == valid
```

## Async tests and mocks

pytest runs no coroutine on its own. The template's `dev` group pins pytest-asyncio for that. Mark each async test `@pytest.mark.asyncio`. Give an async fixture `@pytest_asyncio.fixture`, not `@pytest.fixture`, which pytest 9 rejects for an async function. From [`test_testing.py`](../examples/tests/test_testing.py):

```python
@pytest_asyncio.fixture
async def tasks() -> AsyncIterator[BackgroundTasks]:
    background = BackgroundTasks()
    yield background
    await background.shutdown()
```

Mock an awaitable with `AsyncMock`, and check it with the `assert_awaited_*` methods. `assert_called_*` passes even when the coroutine was never awaited. From [`test_testing.py`](../examples/tests/test_testing.py):

```python
@pytest.mark.asyncio
async def test_display_name_fetches_the_user_once() -> None:
    store = AsyncMock()
    store.fetch_user.return_value = User(1, "Alice", "alice@example.com")
    assert await display_name(store, 1) == "Alice <alice@example.com>"
    store.fetch_user.assert_awaited_once_with(1)
```

## Property tests

Build a strategy for your own type with `@st.composite`, and annotate `draw` as `st.DrawFn`. From [`test_testing.py`](../examples/tests/test_testing.py):

```python
@st.composite
def users(draw: st.DrawFn) -> User:
    name = draw(st.text(min_size=1, max_size=50))
    return User(id=draw(st.integers(min_value=1)), name=name, email=draw(st.emails()))
```

A parser of untrusted input gets a `@given` test that states a property for every input: it raises the parser's own error, or its output round-trips. Add an `@example` seed for each known-bad input, such as empty input and each bug found, so every run tries them. From [`test_testing.py`](../examples/tests/test_testing.py):

```python
@given(st.binary())
@example(b"")
@example(b"\x05abc")
@example(b"\x00")
def test_decode_frame_rejects_or_round_trips(data: bytes) -> None:
    try:
        payload = decode_frame(data)
    except FrameError:
        return
    assert encode_frame(payload) == data
```

Pull request CI runs `pytest --hypothesis-profile=ci`. That built-in profile is derandomized, so each run tries the same inputs, with the default bound of 100 examples. [checks.md](checks.md#untrusted-input) has the details. Do not set `derandomize` or `max_examples` on a single test.

## Configuration

Start from the template [assets/pyproject-checks.toml](../assets/pyproject-checks.toml). Its pytest settings fail a run on an unregistered marker, an unknown setting, a warning, or an `xfail` test that passes. It sets pytest-asyncio's fixture loop scope, which pytest-asyncio warns about when it is unset. Its coverage settings measure branches and report the missed lines, with no threshold.
