# Step: dependency management

Area 9, medium priority. Read this, and python-practices' `references/dependencies.md`, before reviewing a change to the files below. When the change is in a pyo3 or maturin package, also read `references/native-extensions.md`. It covers the locked build backend and `Cargo.lock`.

- `[project] dependencies` and dependency groups in `pyproject.toml`;
- `uv.lock`, `requirements*.txt`, and `.python-version`;
- a PEP 723 script header, and a script's `<file>.lock`;
- imports of new packages.

The practices references hold the rules and commands. This file says what to look for, how to get evidence without changing the tree, and what is not a finding. The review fetches nothing unasked, except a suite tool at its pinned version.

## Contents

- [What to report](#what-to-report)
- [A lockfile out of step](#a-lockfile-out-of-step)
- [Known vulnerabilities](#known-vulnerabilities)
- [Severity](#severity)
- [Version-sensitive rules](#version-sensitive-rules)
- [Not a finding](#not-a-finding)

## What to report

- **A lockfile out of step**: see [A lockfile out of step](#a-lockfile-out-of-step). It is one of these:
  - a `uv.lock` that no longer matches `pyproject.toml`;
  - a `uv.lock` edited by hand;
  - a project or script with dependencies and no committed lockfile.
- **Dependencies with known vulnerabilities**: see [Known vulnerabilities](#known-vulnerabilities).
- **A dependency from an unpinned source**: a Git branch or tag, a URL, or a local path outside the repository. Look in `[project] dependencies`, `[tool.uv.sources]`, and script headers. A Git dependency is pinned only to a commit.
- **A new dependency** with no reason in the change, when:
  - the standard library or an existing dependency already does the job;
  - its name is close to a well-known package's. It can be a different, malicious package;
  - it is unmaintained.
- **Version bounds**:
  - a runtime dependency with no lower bound;
  - an upper bound in a library, with no known break behind it;
  - a tool of the check suite not at an exact version in the `dev` group.
- **The wrong place**: a tool or test-only package in `[project] dependencies` or `[project.optional-dependencies]`, where a dependency group was meant.
- **`requires-python`** raised with no note that it breaks users on the old version, or out of step with mypy's `python_version`. A raised floor is also a breaking change.
- **Many packages upgraded in one change**, as `uv lock --upgrade` does, with no reason given. The change cannot be reviewed package by package.

## A lockfile out of step

`uv lock --check --offline` is the evidence. It reports whether `uv.lock` matches `pyproject.toml`, writes nothing, and reads only uv's cache. It runs without `UV_NO_CONFIG`, so it reads the resolver settings in `[tool.uv]` and `uv.toml`, as CI does. When the change edits those settings, `checks.md` does not run it, and the review reads the `uv.lock` diff. For a script with a PEP 723 header, the same check is `uv lock --check --offline --script <file>`, against `<file>.lock`. `checks.md` runs both.

`uv lock --check` resolves the project's own metadata. When that metadata is dynamic, or comes from a build backend, it runs the backend.

So `uv lock --check` waits for the user's yes when the change touches the build backend or dynamic metadata, as `checks.md` lists them on the execution surface. Otherwise the review reads the `uv.lock` diff. Quote each package added, each version that went down, and each source that changed. Say whether `pyproject.toml` explains it.

A failure because a package is not in uv's cache is a limit, not a finding. `Unable to find lockfile` for a script with dependencies is evidence that its lockfile is missing.

## Known vulnerabilities

`pip-audit` checks the locked dependencies against the vulnerability service, over the network. `checks.md` runs it only when the user allows the network, on the output of `uv export --frozen`. That reads `uv.lock` only and runs no build backend. Otherwise record it as not run, with the reason, and the command the user can run.

When it runs, report as a finding each vulnerability in a package the change adds, upgrades, or makes reachable. Give its ID, the package, its version, and the fixed version. A vulnerability in a package the change does not touch goes under the checks as context. Suppressing an advisory that has no fix follows the rule python-practices' `references/checks.md` names, never a reason in the change.

Without `pip-audit`, review a new or upgraded dependency by reading. Name the package and version, and say the vulnerability check is a limit.

## Severity

- `critical`: a known vulnerability in a package the code calls with untrusted input.
- `major`:
  - a known vulnerability with no shown path from untrusted input;
  - a dependency from an unpinned branch or from a path outside the repository, when the build or the run needs it;
  - a lockfile that `uv sync --locked` in CI will reject.
- `minor`:
  - a missing or stale lockfile with no other consequence shown;
  - a missing lower bound, or a dependency in the wrong place;
  - a new dependency the standard library could replace.

## Version-sensitive rules

Read the module's floor from step 3 before you flag a rule or suggest a fix. A dependency that the standard library replaces only above the floor, such as `tomli` before `tomllib` in 3.11, is not a finding.

## Not a finding

- An available upgrade with no fix, vulnerability, or reason behind it.
- A transitive package that `uv.lock` adds because a direct dependency needs it.
- A dependency check that could not run. That is a limit.
- A suite tool that the repository's CI does not install. That is a line in the report's check suite section.
