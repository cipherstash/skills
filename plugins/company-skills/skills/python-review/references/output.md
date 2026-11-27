# Output format

Read this in step 8. The review's output goes to the user in the conversation. It is not written to the repository or posted anywhere.

## Contents

- [Report shape](#report-shape)
- [Fields](#fields)
- [Handing on](#handing-on)

## Report shape

Use this shape. Keep every section, even when it is empty, so a reader can see what the review covered.

````markdown
# Python review: <target as given>

Reviewed `<base short SHA>`..`<head short SHA>` (full: `<base SHA>`..`<head SHA>`) in `<repository path or PR URL>`
Python floor: 3.12 (`requires-python = ">=3.12"` in `pyproject.toml`)
Source: python-review · <model ID, or unknown> · host <Claude Code, Codex, or unknown>
Skills: `python-review`, `python-practices`

## Checks

| Check | Scope | Outcome |
| --- | --- | --- |
| `ruff format --check --diff --no-cache --config pyproject.toml` | changed files | passed |
| `ruff check --no-cache --no-fix --output-format=concise --config pyproject.toml` | changed files | failed: `mailer/templates.py:12:44: PGH003 Use specific rule codes when ignoring type issues` |
| `mypy --strict --cache-dir=<tmp>/mypy --config-file pyproject.toml` | `src tests` | failed: 2 `import-not-found` errors for `jinja2` at `mailer/templates.py:3`, a limit |
| `pytest --cov --cov-branch` | `tests` | not run: the change touches the execution surface (`tests/conftest.py`), and the user did not say yes. Command: `COVERAGE_FILE=<tmp>/.coverage pytest -c <tmp>/pytest.ini --rootdir <module root> -p no:cacheprovider --cov --cov-branch --cov-report=term-missing --cov-config=<tmp>/coveragerc <module root>/tests` |
| `pip-audit` | `uv.lock` | not run: needs the vulnerability service over the network |
| `semgrep` | changed files | not run: not installed |
| `mypy --strict` in CI | `src tests` | failed: job `python-checks` on the head commit, `<run URL>` |
| `ruff check` in CI | `.` | passed: job `python-checks` on the head commit, `<run URL>` |

## Coverage and limits

- Areas reviewed: both with a step reference, in priority order, with the files read for each:
  1. Error handling: read `references/step-error-handling.md`, python-practices `references/errors.md`
  4. Typing: read `references/step-typing.md`, python-practices `references/typing.md`
- Areas not reviewed: Correctness and edge cases, Testing and coverage, Concurrency and async, Naming and style, Security, Performance, Dependency management, Documentation, and Breaking changes: no step reference.
- Execution surface: `tests/conftest.py` changed; `pytest` not run without a yes.
- Limits: mypy ran without the change's dependencies, so calls into `jinja2` were read as `Any`; `pytest` not run; `pip-audit` and `semgrep` not run.

## Findings

### P1 · major · `mailer/worker.py:52` · cancellation swallowed in the send loop

- Area: error handling
- Cause: the change wraps the loop in `drain_queue` in `except asyncio.CancelledError:`, which logs "worker stopping" and returns with no `raise`.
- Trigger and consequence: `mailer/main.py:30` runs `drain_queue` under `asyncio.timeout(30)`. When the time runs out, the coroutine returns normally, so no `TimeoutError` is raised. `main` then marks the batch as sent while its messages are still on the queue.
- Rule: python-practices errors, "When you must catch `CancelledError`, clean up and re-raise it. Never swallow it."
- Evidence: the handler read at `mailer/worker.py:50-54`, and the timeout at `mailer/main.py:30` (observed). No tool reports a `CancelledError` caught by name and swallowed; the consequence is inferred from how `asyncio.timeout` works.
- Fix: log, then re-raise with a bare `raise`, or move the log line into a `finally` block.
- Source: python-review · <model ID>

### P2 · minor · `mailer/templates.py:12` · `# type: ignore` with no error code

- Area: typing
- Cause: the change adds a bare `# type: ignore`, with no comment, to the call `Template(source).render(**fields)`.
- Rule: python-practices typing, "Every `# type: ignore` names its error code, as in `# type: ignore[arg-type]`, with a comment saying why."
- Evidence: ruff `PGH003` at `mailer/templates.py:12` (observed). The review shows no defect that the ignore hides, so the severity is minor.
- Fix: name the error code mypy reports on that line, with a comment saying why it is safe to ignore, or remove the ignore if it hides nothing.
- Source: python-review · <model ID>

Next: `review-cross-check`, `review-post`, `review-fix`, if you ask.

## Verdict

REQUEST_CHANGES: <one to three sentences: what blocks the change, and any limit the reader must know.>
````

## Fields

- **Reviewed**: full SHAs for base and head. For uncommitted changes, write `HEAD <SHA> plus uncommitted changes`. A snapshot has no commit for `review-post` to post against, so say the user must commit before posting.
- **Python floor**: one line per module when the change touches several, with where the floor came from. Write `3.12 (no requires-python)` where the module has none.
- **Checks**: one row per check, with the exact command and scope. The outcome is `passed`, `failed: <evidence>`, or `not run: <reason>`, as `checks.md` defines them. A check run with replacement flags, because the change edits the tool's config, says so. A check CI ran on the head commit is its own row, with the job, CI's outcome, and the run's URL. A local run of a suite tool is evidence for a finding, not the gate's result. Write `CI's results: not read: <reason>` under the table when they could not be read.
- **Coverage and limits**: every area of the eleven is listed once, as reviewed or not reviewed with the reason: left out at the user's request, `no step reference`, or `step reference not read`. A reviewed area lists the files read for it in step 6: its step reference and each python-practices reference, by path. An area is reviewed only if its step reference was read; otherwise it is listed as not reviewed, `step reference not read`, with no findings under it. A python-practices reference the table names for a reviewed area but not read is a limit of that area. If the skill could not be loaded, write `python-practices not loaded:` and the references not read under limits. List each changed file on the execution surface, or `Execution surface: not touched.` Every check not run is a limit, as is mypy without the change's dependencies, and any change to the user's tree found in step 8.
- **Findings**: most severe first, numbered `P1`, `P2`, and so on. A finding with no single line gives the files and says `design-level`. A deleted line gives the base line and says `deleted`. Write `Rule:` when the finding rests on a rule, and `Trigger and consequence:` when it rests on behaviour. Write both when both apply. With no findings, write `No findings.` and keep the coverage section, so the result is read as clean only within that coverage.
- **Verdict**: the last section. `REQUEST_CHANGES` when any finding is critical or major, otherwise `APPROVE`. An `APPROVE` summary names the limits and areas not reviewed.

## Handing on

The findings are already in the shape the other review skills take: file and line, claim, trigger, severity in `critical`, `major`, or `minor`, and source. Just above the verdict, in one line, name the next steps that apply, so the verdict stays last:

- `review-cross-check` checks the findings against a pull request's existing review comments.
- `review-post` posts them to the pull request as a comment review, against the reviewed head commit.
- `review-fix` fixes them.

Do not run any of these unless the user asks.
