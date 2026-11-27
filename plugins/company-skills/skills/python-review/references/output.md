# Output format

Read this in step 9. The review's output goes to the user in the conversation. It is not written to the repository or posted anywhere.

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
| `ruff check --no-cache --no-fix --output-format=concise --config pyproject.toml` | changed files | failed: `mailer/send.py:41:13: B904 Within an except clause, raise exceptions with raise ... from err` |
| `mypy --strict --cache-dir=<tmp>/mypy --config-file pyproject.toml` | `src tests` | failed: `mailer/templates.py:18: error: Returning Any from function declared to return "dict[str, str]"  [no-any-return]`; 2 `import-not-found` errors for `jinja2`, a limit |
| `pytest --cov --cov-branch` | `tests` | not run: the change touches the execution surface (`tests/conftest.py`), and the user did not say yes. Command: `COVERAGE_FILE=<tmp>/.coverage pytest -p no:cacheprovider --cov --cov-branch --cov-report=term-missing tests` |
| `pip-audit` | `uv.lock` | not run: needs the vulnerability service over the network |
| `semgrep` | changed files | not run: not installed |
| `uv lock --check --offline --directory .` | `.` | passed |
| `mypy --strict` in CI | `src tests` | failed: job `python-checks` on the head commit, `<run URL>` |
| `ruff check` in CI | `.` | passed: job `python-checks` on the head commit, `<run URL>` |

## Check suite in CI

- `pip-audit`: no workflow step runs it.
- `semgrep`: not in place: its step has `continue-on-error: true` (`.github/workflows/ci.yml:41`).
- `scripts/rotate_keys.py` has neither a `pyproject.toml` nor a PEP 723 header, so no check covers it.

## Advisory checks

- `griffe check`: no workflow step runs it.

## API changes

Compared the public names and `__all__` of `mailer` at the base and the head; CI runs no griffe check.

- Changed: `send(message: Message, *, retries: int = 3) -> None` is now `send(message: Message, *, retries: int) -> None` (`mailer/send.py:22`). `retries` lost its default, so every call that leaves it out fails with `TypeError`.
- Added: `TemplateError`, `load_templates`.
- Version: 2.3.0 (`[project] version`). The change needs a new major version, or the default for `retries` restored.

## Coverage and limits

- Areas reviewed: all eleven, in priority order, with the files read for each:
  1. Error handling: read `references/step-error-handling.md`, python-practices `references/errors.md`
  2. Correctness and edge cases: read `references/step-correctness.md`, python-practices `references/data-modelling.md`, python-practices `references/errors.md`
  3. Testing and coverage: read `references/step-testing.md`, python-practices `references/testing.md`
  4. Typing: read `references/step-typing.md`, python-practices `references/typing.md`
  5. Concurrency and async: read `references/step-concurrency.md`, python-practices `references/async.md`
  6. Naming and style: read `references/step-naming.md`, python-practices `references/project-structure.md`
  7. Security: read `references/step-security.md`, python-practices `references/security.md`
  8. Performance: read `references/step-performance.md`, python-practices `references/performance.md`
  9. Dependency management: read `references/step-dependencies.md`, python-practices `references/dependencies.md`
  10. Documentation: read `references/step-documentation.md`, python-practices `references/project-structure.md`
  11. Breaking changes: read `references/step-breaking-changes.md`, python-practices `references/project-structure.md`, python-practices `references/dependencies.md`
- Areas not reviewed: none.
- Execution surface: `tests/conftest.py` changed; `pytest` not run without a yes.
- Limits: mypy ran without the change's dependencies, so calls into `jinja2` were read as `Any`; `pytest` not run; `pip-audit` and `semgrep` not run.

## Findings

### P1 · major · `mailer/send.py:22` · optional parameter made required breaks every caller

- Area: breaking changes
- Cause: the change removes the default `3` from `send`'s keyword-only parameter `retries`.
- Trigger and consequence: every caller of `send` written for 2.3.0 that leaves `retries` out, such as `send(message)`, raises `TypeError: send() missing 1 required keyword-only argument: 'retries'` after an upgrade to the next minor release.
- Rule: python-practices project structure, "making an optional parameter required ... breaks users".
- Evidence: the signatures at the base and the head, compared (observed); `[project] version = "2.3.0"` and no major bump (observed).
- Fix: restore the default, `retries: int = 3`.
- Source: python-review · <model ID>

### P2 · major · `mailer/templates.py:18` · decoded template map returned as `Any`

- Area: typing
- Cause: the change adds `load_templates`, annotated `-> dict[str, str]`, which returns `json.loads(path.read_text())` with no check of its shape.
- Trigger and consequence: a templates file holding a JSON list, or a map whose values are objects, passes through as a `dict[str, str]`. `render` then calls `.format` on a `dict` and raises `AttributeError` while sending, after the message was taken off the queue.
- Rule: python-practices typing, "Do not use `Any` where a type is known. Take `object` for a value of unknown type, and narrow it before use."
- Evidence: mypy `no-any-return` at `mailer/templates.py:18` (observed); the path to `render` read at `mailer/send.py:30` (inferred from reading).
- Fix: decode into `object`, check it is a `dict` whose keys and values are all `str`, and raise the module's `TemplateError` otherwise.
- Source: python-review · <model ID>

### P3 · minor · `mailer/send.py:41` · new error raised without its cause

- Area: error handling
- Cause: the change wraps `smtplib.SMTPException` in `SendError` inside `except`, with no `from`.
- Rule: python-practices errors, "Inside `except`, raise a new error with `raise NewError(...) from error`, so the cause stays in the traceback."
- Evidence: ruff `B904` at `mailer/send.py:41` (observed). No code in the repository reads `__cause__`, so the severity is minor.
- Fix: `except smtplib.SMTPException as error: raise SendError(message.id) from error`.
- Source: python-review · <model ID>

Next: `review-cross-check`, `review-post`, `review-fix`, if you ask.

## Verdict

REQUEST_CHANGES: <one to three sentences: what blocks the change, and any limit the reader must know.>
````

## Fields

- **Reviewed**: full SHAs for base and head. For uncommitted changes, write `HEAD <SHA> plus uncommitted changes`. A snapshot has no commit for `review-post` to post against, so say the user must commit before posting.
- **Python floor**: one line per module when the change touches several, with where the floor came from. Write `3.12 (no requires-python)` where the module has none.
- **Checks**: one row per check, with the exact command and scope. The outcome is `passed`, `failed: <evidence>`, or `not run: <reason>`, as `checks.md` defines them. A check run with replacement flags, because the change edits the tool's config, says so. A check CI ran on the head commit is its own row, with the job, CI's outcome, and the run's URL. A local run of a suite tool is evidence for a finding, not the gate's result. Write `CI's results: not read: <reason>` under the table when they could not be read.
- **Check suite in CI**: one line for each suite check that is not in place in CI at the head, and one for each Python script with neither a `pyproject.toml` nor a PEP 723 header, as `checks.md` describes under Repository standards. Each line says what is missing. Write `All in place.` when none is missing. Write `not compared: <reason>` when the review could not compare CI with the suite. That is also a limit. A missing check is a line here, not a finding. A check the change removes or weakens is also a finding.
- **Advisory checks**: one line for each advisory check that does not run on `pull_request` at its pinned version, such as `griffe check`. Write `All in place.` when none is missing. A missing advisory check is one line here, never a finding, and it never changes the verdict.
- **API changes**: every removed, renamed, or changed public name, the additions in one line, the version note, and the method used: griffe's result from CI, or the comparison of public names and `__all__`, as `step-breaking-changes.md` describes. Write `None.` when the public API is unchanged, and `not compared: <reason>` when the review could not compare it, which is also a limit. Leave the section out only when breaking changes are not in scope at the user's request.
- **Coverage and limits**: every area of the eleven is listed once, as reviewed or not reviewed with the reason: left out at the user's request, cut for scope, or `step reference not read`. A reviewed area lists the files read for it in step 7: its step reference and each python-practices reference, by path. An area is reviewed only if its step reference was read; otherwise it is listed as not reviewed, `step reference not read`, with no findings under it. A python-practices reference the table names for a reviewed area but not read is a limit of that area. If the skill could not be loaded, write `python-practices not loaded:` and the references not read under limits. List each changed file on the execution surface, or `Execution surface: not touched.` Every check not run is a limit, as is mypy without the change's dependencies, and any change to the user's tree found in step 9.
- **Findings**: most severe first, numbered `P1`, `P2`, and so on. A finding with no single line gives the files and says `design-level`. A deleted line gives the base line and says `deleted`. Write `Rule:` when the finding rests on a rule, and `Trigger and consequence:` when it rests on behaviour. Write both when both apply. With no findings, write `No findings.` and keep the coverage section, so the result is read as clean only within that coverage.
- **Verdict**: the last section. `REQUEST_CHANGES` when any finding is critical or major, otherwise `APPROVE`. An `APPROVE` summary names the limits and areas not reviewed.

## Handing on

The findings are already in the shape the other review skills take: file and line, claim, trigger, severity in `critical`, `major`, or `minor`, and source. Just above the verdict, in one line, name the next steps that apply, so the verdict stays last:

- `review-cross-check` checks the findings against a pull request's existing review comments.
- `review-post` posts them to the pull request as a comment review, against the reviewed head commit.
- `review-fix` fixes them.

Do not run any of these unless the user asks.
