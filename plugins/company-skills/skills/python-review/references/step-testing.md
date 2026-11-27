# Step: testing and coverage

Area 3, high priority. Read this, and python-practices' `references/testing.md`, before judging the change's tests. The practices reference holds the rules for writing tests. This file says what to look for in a change, what evidence shows it, and what is not a finding.

## Contents

- [New code without tests](#new-code-without-tests)
- [A parser of untrusted input without a property test](#a-parser-of-untrusted-input-without-a-property-test)
- [A removed or weakened check](#a-removed-or-weakened-check)
- [Coverage figure and untested functions](#coverage-figure-and-untested-functions)
- [Tests that cannot fail](#tests-that-cannot-fail)
- [Evidence](#evidence)
- [Version-sensitive rules](#version-sensitive-rules)
- [Not a finding](#not-a-finding)

## New code without tests

Report each function, method, or branch the change adds or alters that no test runs, when a regression there would go unnoticed. Examples are a calculation, a parser, an error path, and a boundary. Name the function and the regression a test would catch. An example: "a retry helper that stopped capping its delay would pass every test".

Report a test the change deletes or weakens when the behaviour it covered still exists. Examples are a removed `parametrize` case, a looser assertion, a new `@pytest.mark.skip`, and an `xfail` with no `strict=True`. If the deleted test caught a defect the change introduces, fold this into that defect's finding as part of its cause.

## A parser of untrusted input without a property test

Untrusted input is bytes from outside the process, such as a request body, a file, or a message, as python-practices' `references/checks.md` defines it. A function the change adds that parses or decodes untrusted input, with no Hypothesis `@given` test, is a `minor` finding. The function's other tests do not change that. Cite the practices rule: such a function gets a `@given` test with `@example` seeds. Name the function and the property its test should state, such as "it returns a valid value or raises the module's own error".

A function that existed before the change is not a finding under this rule. A `@given` test with no `@example` seed for an input the change is known to mishandle is part of the defect's own finding. A crash that a property test finds is reported at its own severity, not as `minor`. Code review enforces this rule, because CI cannot tell that the test is missing.

## A removed or weakened check

When the change removes or weakens a check of the Python check suite in CI, report it as `major`, under this area. `checks.md` describes the cases under [Repository standards](checks.md#repository-standards).

## Coverage figure and untested functions

When the tests run, `checks.md` runs them with `--cov --cov-branch --cov-report=term-missing`, writing the data file to a temporary directory. From that output, report:

- the `TOTAL` line, as the coverage figure, with the modules it covers;
- every changed file whose changed lines or branches appear under `Missing`, by name and line.

If the tests were not run, the coverage figure is a limit: write `not run` and the reason. Coverage is a figure, not a verdict. A percentage below some target is not a finding.

## Tests that cannot fail

Report a test the change adds that cannot fail for the defect it names:

- it calls the code but asserts nothing, or asserts only that no exception was raised;
- its expected value is computed the same way as the code under test;
- `pytest.raises` wraps more than the one call that should raise, so an earlier call can raise the error instead;
- it mocks the function under test, or patches a name where it is defined, not where the code looks it up. The real code never runs;
- an async test with no `@pytest.mark.asyncio`, or a coroutine never awaited, so its body never runs;
- it waits for a condition with `time.sleep`, so it is slow and flaky.

## Evidence

- The coverage report: quote the lines for the files you name.
- The diff of the test files: quote a deleted case or a weakened assertion.
- A search of the module's tests for `given` and `hypothesis`: quote what it finds, or say it finds nothing.
- To show that a test cannot fail, you may break the code in the temporary worktree and run the test, as `checks.md` describes. Put the code back, and say that you did.

## Version-sensitive rules

Read the module's floor from step 3 before you flag a rule or suggest a fix. `unittest.mock.AsyncMock` needs Python 3.8, and `asyncio.TaskGroup` in a test needs 3.11. Suggest no fix above the floor.

## Not a finding

- A coverage percentage by itself.
- No test for code with no logic to get wrong: a constant, a type declaration, a dataclass with no methods, or generated code.
- A missing property test or benchmark, other than for a new parser of untrusted input, unless it would catch a plausible regression.
- A test style the practices reference prefers, such as plain functions over `unittest.TestCase`, when the existing tests check the behaviour.
- A missing check of the suite in CI. That is a line in the report's check suite section, never a finding.
