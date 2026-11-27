# Behavior cases

This is a background convention skill: it is applied while the agent writes Python, not invoked by name. A Python review skill may also load it to read its references.

## Should activate

- "Add a `retry` decorator to `client/http.py` that keeps the wrapped function's signature." (in a Python package) The agent writes it with `def retry[**P, R]` and `functools.wraps`, not a `TypeVar` or `ParamSpec` declaration.
- "`load_settings` swallows the `KeyError`; make it raise something useful." The agent raises its own error class with `raise ... from error`.
- "Add a `ConfigError` type to our Python SDK and use it when the YAML is bad."
- "This worker catches `Exception` and keeps going, but it never stops when we cancel it." The agent lets `asyncio.CancelledError` through, re-raising it after any cleanup.
- "Run these three uploads with a `TaskGroup` and tell the caller which ones failed." The agent handles the `ExceptionGroup` with `except*`.
- "Set up logging for our Python library." The agent adds only a `NullHandler` and does not call `logging.basicConfig`.
- "Add a `scripts/bump_version.py` helper to this Rust repository." The agent applies the Python rules to the script and gives it a PEP 723 header.
- "mypy fails on `def first(items: list) -> Any`; fix the types." in a project whose `requires-python` is `>=3.12`.
- "Add a GitHub Actions job that checks our Python package." The agent reads `references/checks.md` and adds the suite's checks at their pinned versions.
- "Add a decoder for the upload format clients send to `ingest/parse.py`." The agent adds a Hypothesis `@given` test with `@example` seeds.
- "Tidy up the types in this module." in a Python repository, with no module named. The agent asks which module, or reads the project's `requires-python` and mypy config before changing code.

## Should not activate

- "Review this Python pull request for typing problems." Reviewing Python is not this skill's job.
- "Add a retry with backoff to this TypeScript fetch wrapper."
- "Fix the error handling in this Rust crate's client." Rust conventions are in `rust-sdk-dx`.
- "Clean up the cells in `analysis.ipynb`." Notebooks are out of scope.
- "Speed up the `.pyx` extension in `fastpath/`." Cython is out of scope.
- "Write a Go client for our Python service's HTTP API." Go conventions are in `golang-practices`.

## Expected behavior

- The agent reads `requires-python` before applying a version-sensitive rule. On a project whose floor is 3.12 it imports `TypeIs` from `typing_extensions`, not `typing`, and it skips a rule that needs 3.13 or 3.14 when the floor is below it.
- The agent reads `references/typing.md` before writing annotations, generics or mypy configuration, and `references/errors.md` before writing exception handling or logging. It reads `references/checks.md` before calling a change done, and before editing a Python CI job. It does not load references for areas the change does not touch.
- Every function the agent writes, in source and tests, has full annotations and passes `mypy --strict`.
- Generics use PEP 695 syntax. The agent writes no `TypeVar`, `Generic` or `TypeAlias`.
- A new error is raised with `raise ... from error` inside `except`. A custom error builds its message in its own `__init__`.
- No code the agent writes swallows `asyncio.CancelledError` or catches bare `except:`.
- Library code adds only a `NullHandler` and never configures logging. `logger.exception` appears only inside `except`.
- A CI job the agent writes pins each suite tool at the version in `references/checks.md`, installs with `uv sync --locked`, and has no step that ignores an exit status. It runs `griffe check` as an advisory step that does not block.
- The agent formats with `ruff format` and may run any suite tool that helps it get the change right. CI stays the gate.
- The agent does not invent packages, helpers or repository paths that are not in the user's codebase.
