# Project structure, naming and the public API

This reference targets Python 3.12. Read the project's `requires-python` first. A rule that needs a later version names it. Skip it when the project's lowest supported version is below it. The examples are in the [examples project](../examples/pyproject.toml), where CI runs the check suite over them.

## Layout

Put the package under `src/`, so tests import the installed package, not the files beside them. Ship a `py.typed` file in the package, so type checkers read its annotations (PEP 561). Keep tests in `tests/`, outside the package.

```text
myproject/
├── pyproject.toml
├── uv.lock
├── src/
│   └── myproject/
│       ├── __init__.py
│       ├── py.typed
│       └── core.py
└── tests/
    ├── conftest.py
    └── test_core.py
```

A command-line tool is an entry in `[project.scripts]` that names a function, never a script file that installs itself. From [`pyproject.toml`](../examples/pyproject.toml):

```toml
[project.scripts]
practices-version = "practices.about:main"
```

Read the package's own version from its installed metadata. `pyproject.toml` is not in the wheel, so code cannot read it there. From [`about.py`](../examples/src/practices/about.py):

```python
def package_version() -> str:
    return version("practices")
```

Do not keep the version in a second place, such as a hand-written `__version__`, which can drift from `pyproject.toml`.

## Naming and style

- Format with `ruff format`, and leave its output as it is. Do not hand-align code or turn the formatter off for a block.
- Follow PEP 8 names: `snake_case` for functions, methods, variables and modules, `PascalCase` for classes and type aliases, and `UPPER_SNAKE_CASE` for module constants. An error class ends in `Error`.
- Name a thing for what it is or does, not its type: `users`, not `user_list`. A function that returns `bool` reads as a question: `is_valid`, `has_access`.
- A leading underscore marks a name as private to its module or class. Use one underscore, not two, unless you need name mangling.
- Import at the top of the file. ruff's `I` rules sort the imports. A name used only in annotations goes under `if TYPE_CHECKING:`, as ruff's `TC` rules ask.
- Use `pathlib.Path` for paths, as ruff's `PTH` rules ask. `os.path` is still supported, so leave working code alone, but do not mix the two in one module.
- Use f-strings for formatting, except in a logging call, which takes `%s` arguments so the message is built only when it is logged.

## Docstrings

Give every public module, class and function a docstring. No style is required, and the suite has no ruff `D` rules. Say what the name does and what a caller must know, such as the errors it raises, in plain sentences. Do not repeat the types the annotations already give. A private helper needs a docstring only when its name and types do not explain it.

## The public API

- A package's public API is the names in its `__init__.py` and in modules without a leading underscore. List them in each public module's `__all__`, and re-export them from `__init__.py`, so users import from the package, not from where a name is defined.
- Removing or renaming a public name, removing a parameter, making an optional parameter required, narrowing a parameter's type, or widening a return type breaks users. So does raising `requires-python` or dropping a dependency's old version. Each needs a new major version, or a deprecation first.
- To deprecate a name, keep it working for at least one release, and decorate it with `warnings.deprecated` (Python 3.13 and later, or `typing_extensions.deprecated` below that), so callers get a `DeprecationWarning` and type checkers flag them.
- Make a parameter keyword-only, after `*`, when its meaning is not plain from its position. That lets you add or reorder parameters later without breaking callers.
- The griffe advisory check in [checks.md](checks.md#advisory-checks) lists the public API changes that can break users on every pull request.
