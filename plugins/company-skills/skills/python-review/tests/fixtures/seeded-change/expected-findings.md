# Seeded-defect fixture: expected findings

A sample Python change with one planted defect in each of the two areas this skill reviews, and the findings a correct review must report. Run it by hand: nothing in CI drives an agent. `tests/test_fixture.py` checks that each location below is exactly the line it quotes, that the base is clean, and that each defect comes from the change. Where ruff and mypy are installed, it also checks that each tool reports its defect at the head and nothing at the base.

## Contents

- [The change](#the-change)
- [Run it](#run-it)
- [Checks a correct review reports](#checks-a-correct-review-reports)
- Findings P1 and P2, one per area
- [May report](#may-report)
- [Must not report](#must-not-report)

## The change

`base/` is a script, `postage.py`, with a PEP 723 header (`requires-python = ">=3.12"`, no dependencies). It prints the postage for a parcel from a zone and a weight in grams, using rates built into the script. `head/` is the same script after a change titled "postage: read the rates from a file and accept kilograms". It:

- adds `load_rates`, which reads the rates from a JSON file;
- lets `parse_grams` read a weight in kilograms, such as `1.5kg`;
- types `postage_cents`' rates as a `Mapping`, imported under `TYPE_CHECKING`;
- takes the rate file's path as the first argument.

The finding IDs below are labels for this file. A report numbers its findings most severe first, so its IDs can differ.

## Run it

Build a repository with the change as its last commit, in a scratch directory:

```sh
fixture=<python-review skill dir>/tests/fixtures/seeded-change
work=$(mktemp -d)
cp -R "$fixture/base/." "$work"
cd "$work"
git init -q && git add -A && git commit -qm "postage: price a parcel by zone and weight"
cp -R "$fixture/head/." "$work"
git add -A && git commit -qm "postage: read the rates from a file and accept kilograms"
```

Then, in a session started in `$work`, ask for a review of the last commit, for example "Review my last commit for Python problems." Load the skill from a copy of the plugin with every skill's `tests/` folder removed, so the review cannot read this file.

## Checks a correct review reports

With ruff and mypy installed or fetched, and no network allowed for `pip-audit` or `semgrep`:

- The module is the script `postage.py`, with its PEP 723 header. Its floor, read from `requires-python`, is 3.12.
- The change touches no file on the execution surface. The script has no tests, so `pytest` is recorded as not run, with that reason.
- The base commit has no ruff or mypy configuration. So ruff runs with `--isolated`, the rule families python-practices' check suite selects, and `--target-version py312`. mypy runs with `--config-file=`, `--strict`, and `--python-version 3.12`. The report says so.
- `ruff format --check` passes.
- `ruff check` fails with one violation: `B904` at `postage.py:36`, which is P2.
- `mypy --strict` fails with one error: `Returning Any from function declared to return "dict[str, int]"  [no-any-return]` at `postage.py:25`, which is P1. The script has no dependencies, so mypy sees every type, and no missing import is a limit.
- `pip-audit` and `semgrep` are not run: they need the network. These are limits.
- The repository has no remote and no CI, so CI's results are `not read`, a limit.
- The areas reviewed are Error handling and Typing. The report lists `references/step-error-handling.md` with python-practices `references/errors.md`, and `references/step-typing.md` with python-practices `references/typing.md`, as read. It lists the other nine areas as not reviewed, `no step reference`. If python-practices could not be loaded, the review says so as a limit instead.

The verdict is `REQUEST_CHANGES`: P1 is major.

## P1 · major · typing

- Location: `head/postage.py:25`
- Line: `return json.loads(path.read_text(encoding="utf-8"))`
- Cause: the change adds `load_rates`, annotated `-> dict[str, int]`, which returns the `Any` from `json.loads` with no check of its shape.
- Trigger and consequence: a rate file whose value is a string, such as `{"local": "45"}`, passes through as a `dict[str, int]`. `postage_cents` then multiplies the string, so `postage.py rates.json local 250` prints `454545` as the postage, with exit status 0. A file holding a JSON list, or a missing zone key in a non-object, fails later with a `TypeError` far from the cause.
- Rule: python-practices typing, "Do not use `Any` where a type is known. Take `object` for a value of unknown type, and narrow it before use."
- Evidence: mypy `no-any-return` at line 25 (observed); the path to `postage_cents` read at lines 52 and 46.
- Major, not minor: the value comes from a file outside the process, and the wrong postage is printed.
- A correct fix decodes into `object`, checks that it is a `dict` whose keys are `str` and whose values are `int` (and not `bool`), and raises `PostageError` otherwise.

## P2 · minor · error handling

- Location: `head/postage.py:36`
- Line: `raise PostageError("weight", text)`
- Cause: the change rewrites the `except` in `parse_grams` and drops the `as error` and `from error` the base had, so the `PostageError` no longer carries the `ValueError` or `OverflowError` as its cause.
- Rule: python-practices errors, "Inside `except`, raise a new error with `raise NewError(...) from error`, so the cause stays in the traceback."
- Evidence: ruff `B904` at line 36 (observed). Nothing in the script reads `__cause__`, so the severity is minor.
- A correct fix restores `except (ValueError, OverflowError) as error:` and `raise PostageError("weight", text) from error`.

## May report

Any of these is correct, under the area named, and does not change the verdict:

- The script has no tests, so `parse_grams`' new kilogram path, such as `1.5kg` and `nankg`, is untested (testing and coverage, not reviewed here).
- `main` unpacks `argv` with no usage message, so a missing argument raises `ValueError` (correctness and edge cases, not reviewed here).

## Must not report

- `head/postage.py:42`: the quoted annotation `"Mapping[str, int]"`. It names an import under `TYPE_CHECKING`, so below Python 3.14 the quotes are needed. Removing them is a 3.14 rule, above the 3.12 floor.
- `head/postage.py:38`: `raise PostageError("weight", text)` after the `try`. It is outside the `except`, so it has no cause to keep.
- `print` in `main`. The file is a script, and printing the result is its job.
- A suggestion to import `TypeIs` from `typing`, or any other fix that needs Python 3.13 or later.
