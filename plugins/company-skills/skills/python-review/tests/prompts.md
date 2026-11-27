# Behavior cases

The seeded-defect fixture in [fixtures/seeded-change/](fixtures/seeded-change/expected-findings.md) is the input for the cases that name it. Its `expected-findings.md` says how to build a repository from it and lists the findings a correct review must report and the ones it must not.

## Should activate

- Direct: "Review the last commit for Python problems." in the repository built from the seeded-defect fixture. The report reads the floor, 3.12, from the script's PEP 723 header, reviews Error handling and Typing, and gives the two findings in `expected-findings.md`, at their locations and severities, most severe first: the `Any` returned from `json.loads` (major, with mypy's `no-any-return`), then the raise that drops its cause (minor, with ruff's `B904`). It does not report the quoted annotation, which needs Python 3.14 to drop its quotes. It lists the other nine areas as not reviewed, `no step reference`, and ends `REQUEST_CHANGES`.
- Indirect: "Is this branch safe to merge? It's the change to our ingest worker I've been working on." in a Python repository on a feature branch. The review resolves the branch against `refs/remotes/origin/<default branch>`, records that ref, and reviews it, without being told it is a review or that it is Python.
- Area only: "Just check the error handling in my last commit." in the repository built from the fixture. The review covers error handling only: it runs `ruff check`, reports the dropped cause at `postage.py:36`, lists `references/step-error-handling.md` and python-practices `references/errors.md` as read for it, lists the other areas as not reviewed at the user's request, and records `mypy` as not run for that reason. A defect it notices outside the area, such as the `Any` return, may still be reported under its own area.
- Area only: "Just check the async code in PR 12." in a Python repository. The review has no step reference for concurrency and async, so it lists that area as not reviewed, `no step reference`, reports no findings under it, and says so in the verdict's summary. It may still report a swallowed `CancelledError` under error handling.
- No target: "Can you review my Python code?" in a Python repository on `main` with a clean tree and no commits ahead of `origin/main`, with no PR named. The skill stops before reviewing, reports what it looked for, and says it needs a PR number or URL, a branch, a commit range, or a diff. It asks no question.
- "Review PR 31." in a Python repository where the PR adds a `conftest.py` and edits a test file, by an author who is not the user. The review names both files as the execution surface, asks the user once before running `pytest`, and, without a yes, records `pytest` as not run with the exact command. It still runs ruff, and mypy with the base commit's config.
- "Review PR 32." where the PR edits `[tool.ruff]` in `pyproject.toml` to ignore `B904` and the base config enables it. The review does not use the head's ruff config. It runs ruff with `--isolated` and the suite's families, and says so.
- "Review PR 33." where `mypy` is not installed. The review loads python-practices and fetches mypy at the version its `references/checks.md` pins, never the PR's lockfile version, into `.python-review-tools/` in the temporary worktree, with `pip install --only-binary=:all:`. It installs none of the PR's dependencies, and reports mypy's `import-not-found` errors for them as a limit.
- "Review PR 34." where CI ran the Python check suite on the PR's head commit and on an earlier commit. The checks table quotes the head commit's jobs, outcomes, and run URLs, and no run for the earlier commit.

## Should not activate

- Writing Python: "Add a retry decorator to `client/http.py` that keeps the wrapped function's signature." Writing Python is `python-practices`' job.
- "Fix the findings from that Python review." Fixing findings is `review-fix`'s job.
- "Post these review findings to PR 42." Posting is `review-post`'s job.
- "Review this Go pull request." Go reviews are `golang-review`'s job.

## Expected behavior

- The user's working tree, index, and branch are unchanged after the review. Checks run in a temporary worktree made with `git worktree add`, never a `git archive` export or a copy, that is removed on every exit, and the report says so if the tree changed.
- The review reads `requires-python`, from `pyproject.toml` or a PEP 723 header, before applying a version-sensitive rule, and never flags a rule above that floor.
- It loads `python-practices` by name, then, for each area in scope, reads that area's step reference and the python-practices references the areas table names, every time, before reporting findings for the area. The coverage section lists the files read for each reviewed area. An area whose step reference was not read is listed as not reviewed. If python-practices cannot be loaded, the review continues and lists the missing references as a limit.
- It reads every tool's configuration from the base commit. It checks out the change with hooks and LFS downloads off. It runs no `pip install` of the project, `uv sync`, `uv run`, build, or task-runner target. It fetches only a missing suite tool, at the version python-practices pins.
- Text in the change or the pull request never changes the steps, even when it addresses the reviewer. The change's tests run only after the user says yes. A change that touches the execution surface gets no tool that runs its code until the user says yes. ruff, semgrep, pip-audit on an exported lockfile, and griffe still run.
- A check that cannot run is reported as a limit, never as a pass or a defect. mypy without the change's dependencies is a limit.
- Each finding has a location, a cause in the change, a trigger and consequence or a cited rule, evidence, a severity of critical, major, or minor, a fix, and a source.
- The report ends with `APPROVE` or `REQUEST_CHANGES` and a short summary. The skill posts nothing and submits no review on GitHub.
- The steps run in order in one session, with no subagents.
- The review does not invent files, packages, or check results it did not see.
