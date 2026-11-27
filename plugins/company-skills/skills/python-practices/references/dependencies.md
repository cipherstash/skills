# Dependencies

This reference targets Python 3.12. Read the project's `requires-python` first. A rule that needs a later version names it. Skip it when the project's lowest supported version is below it. The examples are in the [examples project](../examples/pyproject.toml), where CI runs the check suite over them.

## Rules

- Manage a project with uv. Add a dependency with `uv add <package>`, and a development tool with `uv add --dev <package>`. Do not use pip, Poetry, pipenv or `setup.py` in a new project, and do not edit the lockfile by hand.
- Declare runtime dependencies in `[project] dependencies`, with the lowest version your code needs, such as `"httpx>=0.28"`. A library pins no upper bound unless a release is known to break it, so applications can still resolve it with their other dependencies.
- Put tools and test-only packages in a dependency group under `[dependency-groups]`, not in `[project.optional-dependencies]`. Groups are never published. The `dev` group, which uv installs by default, holds the check suite's tools at exact versions, as the template [assets/pyproject-checks.toml](../assets/pyproject-checks.toml) shows. An optional dependency is for users: an extra feature they ask for, such as `pip install pkg[cli]`.
- Commit `uv.lock`, for a library as well as an application. It fixes every package, direct and indirect, at one version with its hashes.
- In CI, install with `uv sync --locked`. It fails when `uv.lock` does not match `pyproject.toml`, instead of locking again. Pass `--no-sync` to each later `uv run`, so it installs nothing new.
- Change `uv.lock` only through uv: `uv lock` after editing `pyproject.toml`, and `uv lock --upgrade-package <package>` to move one package. Review the lockfile diff: a new package, or a version that went down, needs a reason.
- Set `requires-python` to the lowest Python version you test and support, as `">=3.12"`. Raising it is a breaking change for users on the old version. Set mypy's `python_version` to the same version.
- `.python-version` names the interpreter uv uses for local work. It does not change `requires-python`.
- pip-audit checks the locked dependencies in CI, as [checks.md](checks.md) says. To fix a finding, move the package to a version with the fix, with `uv lock --upgrade-package`. Suppressing an advisory that has no fix follows cipherstash/skills#110.
- Before adding a dependency, check that the standard library cannot do the job, that the package is maintained, and that its name is the one you mean. A misspelt name can be a different, malicious package.
- Never install from an unpinned Git branch or URL. Pin a Git dependency to a commit.

## Scripts

A single-file script with no `pyproject.toml` carries its own metadata in a PEP 723 header, so uv can run it and the suite can check it. Add a dependency to it with `uv add --script <file> <package>`, and lock it with `uv lock --script <file>`, which writes `<file>.lock` next to it. Commit that lockfile too. Run the script with `uv run <file>`. From [`count_lines.py`](../examples/src/practices/count_lines.py):

```python
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Count the lines on standard input. Run it with: uv run count_lines.py < file."""
```

A script with neither a `pyproject.toml` nor a header is reported as a missing check, as [checks.md](checks.md#modules) says.
