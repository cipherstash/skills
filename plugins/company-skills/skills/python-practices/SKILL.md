---
name: python-practices
description: Applies CipherStash conventions for writing Python — type annotations and mypy, errors and logging, tests with pytest and Hypothesis, asyncio and threads, dataclasses and enums, security, dependencies with uv, project layout and the public API, performance, pyo3 and maturin extensions, and the Python check suite (ruff, mypy, pytest with coverage, pip-audit, semgrep) with its pinned versions. Use when writing or changing Python in any repository, including a script in a Rust, Go or TypeScript repository — .py and .pyi files, tests, pyproject.toml, uv.lock, requirements*.txt or .python-version — such as adding a function, class, error type, test, async task, SQL query, dependency, package entry point, or CI step for Python. Does not apply to other languages, Jupyter notebooks, Cython, or reviewing a Python change.
user-invocable: false
---

# Python practices

Rules for writing Python. Apply them to every Python change, and read the reference for each area the change touches before writing code in it.

## Rules

### Versions and the suite

- Read `requires-python` in the project's `pyproject.toml`, or in a script's PEP 723 header, before applying a version-sensitive rule. The references target Python 3.12 and name the version of any rule that needs a later one. Skip a rule above the project's lowest supported version.
- If the repository's own guidance differs from these rules, follow the repository. Say that you did.
- The Python check suite in [references/checks.md](references/checks.md) lists the checks CI runs on every pull request. Before calling a change done, run any suite tool that helps you get it right. CI is the gate.
- Format with `ruff format`. Lint with `ruff check`.
- A script with no `pyproject.toml` gets a PEP 723 header, so the suite can check it.

### Typing

- Annotate every parameter and return type, in source and tests, so `mypy --strict` passes.
- Write generics in PEP 695 syntax: `def f[T]`, `class C[T]`, `type Alias = ...`. Never `TypeVar`, `Generic`, or `TypeAlias`.
- Write `X | None` and `list[int]`, not `Optional` or `typing.List`.
- Take `object`, not `Any`, for a value of unknown type, and narrow it. A type check function returns `TypeIs`, not `bool`.
- Every `# type: ignore` names its error code and says why.

### Errors

- Catch the narrowest exception you can handle. No bare `except:`, and `except Exception` only at a boundary.
- Raise a new error inside `except` with `raise ... from error`.
- Handle an `ExceptionGroup`, including one from `asyncio.TaskGroup`, with `except*`.
- Never swallow `asyncio.CancelledError`. Catch it only to clean up, then re-raise it.
- Handle an error once: raise it or log it, not both.

### Logging

- A library adds only a `NullHandler` to its package logger. The library never calls `logging.basicConfig`.
- Call `logger.exception` only inside `except`.

### Tests

- Write pytest functions with annotated fixtures. Give each `parametrize` case an id. Mock an awaitable with `AsyncMock`, and mark an async test `@pytest.mark.asyncio`.
- A function that parses or decodes untrusted input gets a Hypothesis `@given` test with `@example` seeds, as [references/checks.md](references/checks.md) says.
- Coverage is reported with no threshold.

### Async and threads

- Run concurrent tasks in an `asyncio.TaskGroup`, not `gather`. Put deadlines on waits with `asyncio.timeout`.
- Keep a reference to every task until it is done.
- Keep no mutable state at module level. Guard state shared between threads with a lock, even under the GIL.

### Data, security and dependencies

- Model records as frozen dataclasses. A mutable field default goes through `field(default_factory=...)`.
- Pass values to SQL as parameters. Make tokens with `secrets` and an explicit length, and compare them with `hmac.compare_digest`. Run programs with an argument list and no shell.
- Never load untrusted input with `pickle` or `yaml.load`, or pass it to `eval`. Keep secrets out of `repr` and logs.
- Manage dependencies with uv. Commit `uv.lock`, and install it in CI with `uv sync --locked`.

## References

Read the reference for each area the change touches. Each one states the Python version it targets. The references quote their examples from the [examples project](examples/pyproject.toml), where the check suite runs over them in CI.

| Read | When the change involves |
| --- | --- |
| [references/typing.md](references/typing.md) | Annotations, `Protocol`, `TypedDict`, `Self`, `@overload`, `assert_never`, generics and `ParamSpec`, `TypeIs`, `Any` and `cast`, `# type: ignore`, mypy configuration |
| [references/errors.md](references/errors.md) | Raising, catching, chaining or re-raising exceptions, error classes, `ExceptionGroup` and `except*`, `CancelledError`, logging in a library or application |
| [references/testing.md](references/testing.md) | Tests, fixtures, `parametrize`, mocks and `AsyncMock`, async tests and fixtures, Hypothesis strategies and `@given` tests for a parser of untrusted input, pytest and coverage settings |
| [references/async.md](references/async.md) | `asyncio` tasks, `TaskGroup` and `gather`, timeouts, `Semaphore` and `Lock`, async context managers, background tasks, threads, `ContextVar`, free-threaded Python |
| [references/data-modelling.md](references/data-modelling.md) | Dataclasses, frozen records, field defaults, `Enum`, `ExitStack` and other context managers, cached results, file paths |
| [references/security.md](references/security.md) | SQL queries, tokens and `secrets`, comparing secrets, `subprocess`, `pickle`, `yaml` and `eval` on untrusted input, secrets in `repr` or logs, network calls, archives |
| [references/dependencies.md](references/dependencies.md) | Adding, upgrading or removing a dependency, uv, dependency groups, `uv.lock`, `requires-python`, `.python-version`, PEP 723 script headers, pip-audit findings |
| [references/project-structure.md](references/project-structure.md) | Package layout, `py.typed`, `[project.scripts]`, the package version, naming and formatting, docstrings, `__all__`, deprecating or changing a public name |
| [references/performance.md](references/performance.md) | Making code faster or use less memory, profiling, data structures, caching, CPU-bound work |
| [references/native-extensions.md](references/native-extensions.md) | A package with a Rust core built with pyo3 and maturin: abi3 wheels, `.pyi` stubs, the build backend, releasing the GIL, fuzzing the Rust side |
| [references/checks.md](references/checks.md) | The checks CI runs on every pull request: ruff, mypy, pytest with coverage, pip-audit, semgrep, Hypothesis for code that parses untrusted input, their pinned versions, the `pyproject.toml` template, and the griffe advisory check |
