# Seeded-defect fixture: expected findings

A sample Python change with one planted defect in each of the eleven areas this skill reviews, and the findings a correct review must report. Run it by hand: nothing in CI drives an agent. `tests/test_fixture.py` checks that each location below is exactly the line it quotes, that the base is clean, and that each defect comes from the change. Where ruff, mypy, and uv are installed, it also checks that each tool reports its defects at the head and nothing at the base.

## Contents

- [The change](#the-change)
- [Run it](#run-it)
- [Checks a correct review reports](#checks-a-correct-review-reports)
- [Check suite in CI](#check-suite-in-ci)
- [Advisory checks](#advisory-checks)
- [API changes](#api-changes)
- Findings P1 to P11, one per area, most severe first
- [May report](#may-report)
- [Must not report](#must-not-report)

## The change

`base/` holds two scripts. `postage.py` has a PEP 723 header (`requires-python = ">=3.12"`, no dependencies). It prints the postage for a parcel from a zone and a weight in grams, using rates built into the script as `RATES`, which its `__all__` exports. `price_list.py` has no header. It imports `RATES` from `postage.py` and prints the price of 100 g in each zone.

`head/` is the same repository after a change titled "postage: read the rates from a file, accept kilograms, and download rate files". It:

- adds `load_rates` to `postage.py`, which reads the rates from a JSON file, and deletes `RATES`;
- lets `parse_grams` read a weight in kilograms, such as `1.5kg`;
- rewrites the charge per started 100 g in `postage_cents`, and types its rates as a `Mapping`, imported under `TYPE_CHECKING`;
- takes the rate file's path as the first argument, and prices one or more weights;
- adds `get_rates.py`, a script with a PEP 723 header that needs `httpx`, which downloads rate files.

`price_list.py` does not change.

The finding IDs below are labels for this file. A report numbers its findings most severe first, as these are, but its order within a severity can differ.

## Run it

Build a repository with the change as its last commit, in a scratch directory:

```sh
fixture=<python-review skill dir>/tests/fixtures/seeded-change
work=$(mktemp -d)
cp -R "$fixture/base/." "$work"
cd "$work"
git init -q && git add -A && git commit -qm "postage: price a parcel by zone and weight"
cp -R "$fixture/head/." "$work"
git add -A && git commit -qm "postage: read the rates from a file, accept kilograms, and download rate files"
```

Then, in a session started in `$work`, ask for a review of the last commit, for example "Review my last commit for Python problems." Load the skill from a copy of the plugin with every skill's `tests/` folder removed, so the review cannot read this file.

## Checks a correct review reports

With ruff, mypy, and uv installed or fetched, httpx not installed, and no network allowed for `pip-audit` or `semgrep`:

- The changed modules are the scripts `postage.py` and `get_rates.py`, each with its PEP 723 header. Each floor, read from `requires-python`, is 3.12. `price_list.py` is a Python file in no module.
- The change touches no file on the execution surface. The repository has no tests, so `pytest` is recorded as not run, with that reason.
- The base commit has no ruff or mypy configuration. So ruff runs with `--isolated`, the rule families python-practices' check suite selects, and `--target-version py312`. mypy runs with `--config-file=`, `--strict`, and `--python-version 3.12`. The report says so.
- `ruff format --check` fails on one line: `postage.py:33`, which is P8.
- `ruff check` fails with four violations: `S501` at `get_rates.py:24` (P1), `RUF006` at `get_rates.py:26` (P4), `B904` at `postage.py:38` (P6), and `PERF401` at `postage.py:57` (P9).
- `mypy --strict` on `postage.py` fails with one error: `Returning Any from function declared to return "dict[str, int]"  [no-any-return]` at `postage.py:27`, which is P3. On `get_rates.py` it reports `import-not-found` for `httpx` at line 11. That is a limit, not a finding: the review never installs the change's dependencies.
- `uv lock --check --offline --script get_rates.py` fails: `Unable to find lockfile at get_rates.py.lock`. That is evidence for P10. The change touches no build backend or dynamic metadata, so it runs without a yes.
- `pip-audit` is not run: it needs the vulnerability service over the network, and `get_rates.py` has no lockfile to export. `semgrep` is not run: it needs the network. These are limits.
- The repository has no remote, so CI's results are `not read`, a limit.
- All eleven areas are reviewed. For each one, the report lists its step reference and the python-practices references the areas table names as read. If python-practices could not be loaded, the review says so as a limit instead.

The verdict is `REQUEST_CHANGES`: P1 is critical, and P2 to P5 are major.

## Check suite in CI

The base and the head have no `.github/workflows/`, so no suite check is in place. A correct review lists each as one line, never as a finding:

- `ruff format --check`: no workflow step runs it.
- `ruff check`: no workflow step runs it.
- `mypy --strict`: no workflow step runs it.
- `pytest --cov --cov-branch`: no workflow step runs it.
- `pip-audit`: no workflow step runs it.
- `semgrep`: no workflow step runs it.
- `price_list.py` has neither a `pyproject.toml` nor a PEP 723 header, so no check covers it.

## Advisory checks

- `griffe check`: no workflow step runs it. One line, never a finding.

## API changes

CI runs no griffe advisory check, so the review compares the public names and `__all__` of `postage.py` at the base and the head:

- Removed: `RATES`, from the module and from `__all__`. `price_list.py` still imports it.
- Added: `load_rates`.

## P1 · critical · security

- Location: `head/get_rates.py:24`
- Line: `async with httpx.AsyncClient(verify=False) as client:`
- Cause: the change adds `get_rates.py`, whose client turns off TLS certificate checks.
- Trigger and consequence: anyone on the network path between the script and the rate server can answer in its place. The script saves their body as a rate file, and `postage.py` then charges the prices they chose.
- Rule: python-practices security, "Verify TLS. Never pass `verify=False`."
- Evidence: ruff `S501` at line 24 (observed); the saved file read by `postage.py` (inferred from reading).
- Critical, not major: the client reads from the network, and what it saves is stored and used as prices.
- A correct fix drops `verify=False`.

## P2 · major · correctness and edge cases

- Location: `head/postage.py:48`
- Line: `return rates[zone] * (grams // 100 + 1)`
- Cause: the change rewrites the charge per started 100 g from `-(-grams // 100)`, which rounds up, to `grams // 100 + 1`.
- Trigger and consequence: a weight that is an exact multiple of 100 g is charged one unit too many. `postage.py rates.json local 200` with a local rate of 45 prints `135` where the base printed `90`. The docstring says "charged per started 100 g".
- Evidence: the docstring at line 45 and the base's line, read (observed). Between multiples of 100 g, the two agree.
- A correct fix restores `rates[zone] * -(-grams // 100)`.

## P3 · major · typing

- Location: `head/postage.py:27`
- Line: `return json.loads(path.read_text(encoding="utf-8"))`
- Cause: the change adds `load_rates`, annotated `-> dict[str, int]`, which returns the `Any` from `json.loads` with no check of its shape.
- Trigger and consequence: a rate file whose value is a string, such as `{"local": "45"}`, passes through as a `dict[str, int]`. `postage_cents` then multiplies the string, so `postage.py rates.json local 250` prints `454545` as the postage, with exit status 0. A file holding a JSON list fails later with a `TypeError` far from the cause.
- Rule: python-practices typing, "Do not use `Any` where a type is known. Take `object` for a value of unknown type, and narrow it before use."
- Evidence: mypy `no-any-return` at line 27 (observed); the path to `postage_cents` read at lines 54, 57, and 48.
- Major, not minor: the value comes from a file outside the process, and the wrong postage is printed.
- A correct fix decodes into `object`, checks that it is a `dict` whose keys are `str` and whose values are `int` (and not `bool`), and raises `PostageError` otherwise.

## P4 · major · concurrency and async

- Location: `head/get_rates.py:26`
- Line: `asyncio.create_task(get_one(client, url, bodies))`
- Cause: the change starts one task per URL and keeps no reference to any of them. Nothing awaits them before the `async with` block closes the client and `get_all` returns.
- Trigger and consequence: every run. The tasks first run while the client closes, so each one fails with `RuntimeError: Cannot send a request, as the client has been closed`. That error is only logged as "Task exception was never retrieved". `get_all` returns an empty dict, no rate file is saved, and the script exits 0.
- Rule: python-practices async, "Run concurrent tasks in an `asyncio.TaskGroup`" and "Keep a reference to every task you create until it is done."
- Evidence: ruff `RUF006` at line 26 (observed); the `async with` block and the `return` at line 27, read.
- A correct fix creates the tasks in an `asyncio.TaskGroup` inside the `async with` block, so the client outlives them and a failure reaches the caller.

## P5 · major · breaking changes

- Location: `base/postage.py:11` (deleted)
- Line: `RATES = {"local": 45, "national": 80, "international": 210}`
- Cause: the change deletes `RATES` and drops it from `__all__`. The base exports it.
- Trigger and consequence: `price_list.py`, which the change does not touch, imports `RATES` from `postage`. At the head it fails at once with `ImportError: cannot import name 'RATES' from 'postage'`.
- Evidence: `__all__` at the base and the head compared (observed); the import in `price_list.py` at line 3, read. CI runs no griffe check, so the review compares the names itself.
- Major: an importer in the same repository stops working, and the scripts have no version to bump.
- A correct fix keeps `RATES`, or moves `price_list.py` to `load_rates` in the same change.

## P6 · minor · error handling

- Location: `head/postage.py:38`
- Line: `raise PostageError("weight", text)`
- Cause: the change rewrites the `except` in `parse_grams` and drops the `as error` and `from error` the base had, so the `PostageError` no longer carries the `ValueError` or `OverflowError` as its cause.
- Rule: python-practices errors, "Inside `except`, raise a new error with `raise NewError(...) from error`, so the cause stays in the traceback."
- Evidence: ruff `B904` at line 38 (observed). Nothing in the scripts reads `__cause__`, so the severity is minor.
- A correct fix restores `except (ValueError, OverflowError) as error:` and `raise PostageError("weight", text) from error`.

## P7 · minor · testing and coverage

- Location: `head/postage.py:25`
- Line: `def load_rates(path: Path) -> dict[str, int]:`
- Cause: the change adds `load_rates`, which decodes a file, and no Hypothesis `@given` test for it.
- Rule: python-practices testing, "A function that parses or decodes untrusted input gets a Hypothesis `@given` test with `@example` seeds."
- Evidence: no file in the repository imports `hypothesis` (observed).
- Minor: the rule's severity for a new parser of untrusted input with no `@given` test.
- A correct fix adds a `@given` test whose property is that `load_rates` returns a `dict[str, int]` or raises `PostageError`, with `@example` seeds for a JSON list and a string rate.

## P8 · minor · naming and style

- Location: `head/postage.py:33`
- Line: `if text.endswith('kg'):`
- Cause: the change adds a line that `ruff format` would rewrite, to `"kg"`.
- Rule: python-practices project structure, "Format with `ruff format`, and leave its output as it is."
- Evidence: `ruff format --check --diff` shows this one line (observed).
- A correct fix runs `ruff format` on the file.

## P9 · minor · performance

- Location: `head/postage.py:57`
- Line: `prices.append(postage_cents(rates, zone, parse_grams(weight)))`
- Cause: the change builds a list with a loop that calls `append`.
- Rule: python-practices performance, "Use a comprehension, not a loop that calls `append`, as ruff's `PERF401` asks."
- Evidence: ruff `PERF401` at line 57 (observed). No measurement shows a cost, so the severity is minor.
- A correct fix builds the list with a comprehension.

## P10 · minor · dependency management

- Location: `head/get_rates.py:3`
- Line: `# dependencies = ["httpx"]`
- Cause: the change adds a script that needs `httpx`, with no lower version and no committed `get_rates.py.lock`.
- Rule: python-practices dependencies, "lock it with `uv lock --script <file>`, which writes `<file>.lock` next to it. Commit that lockfile too."
- Evidence: `uv lock --check --offline --script get_rates.py` fails with `Unable to find lockfile` (observed). With no lockfile, `pip-audit` has nothing to audit.
- Minor: no run shows a release that breaks the script.
- A correct fix runs `uv lock --script get_rates.py` and commits `get_rates.py.lock`. Naming the lowest version the script needs, such as `"httpx>=0.28"`, is also correct.

## P11 · minor · documentation

- Location: `head/postage.py:52`
- Line: `"""Print the postage for the zone and weight in argv."""`
- Cause: the change makes `main` read a rate file as its first argument and price one or more weights, and leaves its docstring as it was.
- Rule: python-practices project structure, "Say what the name does and what a caller must know".
- Evidence: the docstring and the unpacking at line 53, read (observed).
- A correct fix says that `argv` is the rate file, the zone, and one or more weights.

## May report

Any of these is correct, under the area named, and does not change the verdict:

- `postage.py` has no tests, so `parse_grams`' new kilogram path, such as `1.5kg` and `nankg`, is untested (testing and coverage).
- `main` unpacks `argv` with no usage message, so a missing argument raises `ValueError` (correctness and edge cases).
- `get_all` starts one download per URL with no bound on how many run at once (concurrency and async). It shares P4's root cause, so it may be merged into P4.
- `get_rates.py` writes `rates-<n>.json` into the working directory, replacing any file of that name (correctness and edge cases).

## Must not report

- `head/postage.py:44`: the quoted annotation `"Mapping[str, int]"`. It names an import under `TYPE_CHECKING`, so below Python 3.14 the quotes are needed. Removing them is a 3.14 rule, above the 3.12 floor.
- `postage_cents` taking a `Mapping` where the base took a `dict`, as a breaking change. A wider parameter type breaks no caller.
- `head/postage.py:40`: `raise PostageError("weight", text)` after the `try`. It is outside the `except`, so it has no cause to keep.
- `print` in either `main`. The files are scripts, and printing the result is their job.
- mypy's `import-not-found` for `httpx` as a finding. It is a limit.
- A missing suite check, or `price_list.py` having no header, as a finding. Each is a line under the check suite in CI.
- The missing griffe check as a finding. It is a line under the advisory checks.
- A suggestion to import `TypeIs` from `typing`, or any other fix that needs Python 3.13 or later.
