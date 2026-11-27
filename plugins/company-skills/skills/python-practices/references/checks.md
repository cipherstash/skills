# Python check suite

The Python check suite is the set of checks that gate every pull request in a Python project. They run in CI, and CI is the gate. Run any of these tools locally when it helps you get a change right, but do not treat a local run as the gate.

This reference targets Python 3.12. Read the project's `requires-python` first. Where a rule needs a later version, the rule names it. Skip a rule whose version is above the project's lowest supported version.

## Pinned versions

Every tool version is pinned. A repository's CI uses these versions.

| Tool | Version | Package |
| --- | --- | --- |
| ruff | `0.17.6` | `ruff` on PyPI |
| mypy | `2.4.1` | `mypy` on PyPI |
| pytest | `9.2.0` | `pytest` on PyPI |
| pytest-cov | `7.1.0` | `pytest-cov` on PyPI |
| hypothesis | `6.170.17` | `hypothesis` on PyPI |
| pip-audit | `2.10.1` | `pip-audit` on PyPI |
| uv | `0.13.10` | `uv` on PyPI |
| semgrep | `1.186.0` | `semgrep` on PyPI |

ruff, mypy, pytest, pytest-cov, Hypothesis, and pip-audit are exact versions in the project's `dev` dependency group. A committed `uv.lock` fixes them, and CI installs it with `uv sync --locked`. Later `uv run` commands pass `--no-sync`, so they do not lock again. The workflow pins uv through the `version` input of `astral-sh/setup-uv`. semgrep has one pin for every language. CI installs it with `pip install semgrep==<version>`.

Start from the template [assets/pyproject-checks.toml](../assets/pyproject-checks.toml). The template has the `dev` group and the ruff, mypy, pytest, and coverage settings. Its `dev` group also pins pytest-asyncio, which runs async tests, as [testing.md](testing.md) says. pytest-asyncio is a test dependency, not a check.

Two things float by choice. CI uses the latest stable CPython, through `actions/setup-python` with `python-version: "3.x"`, and sets `UV_PYTHON_DOWNLOADS: never` so uv uses it. semgrep reads the latest `p/python` ruleset. Either can fail a pull request that did not cause the finding. Fix the finding.

## The checks

- **Format**: `ruff format --check`.
- **Lint**: `ruff check`. Select at least the rule families `E`, `F`, `W`, `I`, `B`, `UP`, `S`, `SIM`, `RUF`, `PT`, `ASYNC`, `DTZ`, `BLE`, `TRY`, `PTH`, `PGH`, `C4`, `PERF`, `RET`, and `TC`. A project may add families but not drop these. Tests may ignore only `S101`, `S105`, and `S106`. `S` stands in for Go's gosec.
- **Type check**: `mypy --strict` over the source and the tests. No other type checker counts. Set `python_version` to the lowest version in `requires-python`.
- **Tests and coverage**: `pytest --cov --cov-branch`. Coverage is reported, with no threshold.
- **Vulnerabilities**: `uv export --locked --no-emit-project --output-file requirements.txt`, then `pip-audit --strict --disable-pip --requirement requirements.txt`. The export has hashes, so pip-audit installs nothing. Suppressing an advisory that has no fix follows cipherstash/skills#110. Move to `uv audit` once it leaves preview.
- **SAST**: semgrep, from the repository root, with `p/python` plus the repository's own rules in `.semgrep/` when that directory exists, and `--error`. A root `.semgrepignore` replaces semgrep's default list. That list skips test directories. Leave the test entries out of it, so semgrep scans the tests too.

## Untrusted input

Untrusted input is bytes from outside the process, such as a request body, a file, or a message. A function that parses or decodes it needs a Hypothesis `@given` test, with an `@example` seed for each known-bad input.

Pull request CI runs `pytest --hypothesis-profile=ci`. Hypothesis 6.170.17's built-in `ci` profile sets `derandomize=True`, `database=None`, and `deadline=None`. It keeps the default bound of `max_examples=100`, so each run tries the same inputs. HypoFuzz or Atheris may run the same tests on a schedule, never in pull request CI.

A property test is not coverage-guided, so this rule is weaker than Go's Fuzz targets. CI cannot tell that a test is missing, so code review enforces the rule.

## No race detector

Nothing in Python gates like Go's `-race`. No tool finds data races in threaded or free-threaded code. The suite has no free-threaded test job.

## Modules

A module is a `pyproject.toml` project, or a script with a PEP 723 `# /// script` header. Each one gets the full suite. A script with neither is reported as a missing check, and ruff still runs on it.

## When a check is in place

A check is in place when it is a GitHub Actions step that:

- runs on `pull_request`;
- blocks: nothing ignores the tool's exit status. That means no `continue-on-error`, no `|| true`, no shell without `-e`, and no pipe under the default shell, since it sets no `pipefail`;
- covers every module, except test fixtures that contain planted defects;
- pins its version, as the table above says. A version range with no locked install is not pinned.

These Python changes also weaken a check, and do not count:

- `ruff check --exit-zero`, `--fix` in CI, dropping a required family, a broad `per-file-ignores`, or `extend-exclude` over source;
- mypy without `--strict`, or with `ignore_errors`, `follow_imports = "skip"`, `ignore_missing_imports` for the whole project, or a narrower list of files;
- a new `--deselect`, `-k`, `--ignore`, or `-p no:` in pytest's `addopts`, or `--no-cov`;
- dropping `--strict` from pip-audit, or adding `--ignore-vuln` outside #110's rule;
- a semgrep run without `--error`, or a `.semgrepignore` entry that skips source or tests.

## Execution surface

Running the suite runs the project's own code through these files and settings:

- `conftest.py`, `pytest_plugins`, and pytest's `addopts` or plugin settings;
- `.pth` files, `sitecustomize.py`, and `usercustomize.py`;
- compiled `.so` and `.pyd` files;
- the build backend and its hooks, `setup.py`, and dynamic metadata in `pyproject.toml`;
- entry points;
- mypy `plugins =`;
- any Rust crate that a pyo3 or maturin package builds;
- every test file.

ruff, semgrep, pip-audit on an exported lockfile, and griffe only read code.

## Advisory checks

An advisory check runs on every pull request and reports, but never blocks the merge. It is not part of the suite.

| Tool | Version | Package | Evidence |
| --- | --- | --- | --- |
| griffe | `2.4.1` | `griffe` on PyPI | `griffe check <package> --search src --against origin/<base branch>` lists public API changes that can break users |

Run it with `uvx griffe@2.4.1`, from a checkout with the base branch's history (`fetch-depth: 0`), on a step with `continue-on-error: true`.

## Exemptions

A repository may leave a check out only through an exemption architecture decision record (ADR). The ADR is in `docs/adr/` on the default branch, added through an issue and a reviewed pull request. The ADR names each check and module it exempts, gives the reason, and links the issue and pull request. A pull request cannot exempt itself by adding one.
