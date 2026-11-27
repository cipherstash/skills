# Step: testing and coverage

Area 4, high priority. Read this, and typescript-practices' `references/testing.md`, before judging the change's tests. The practices reference holds the rules for writing tests, type tests, and property tests. This file says what to look for in a change, what evidence shows it, and what is not a finding.

## Contents

- [New code without tests](#new-code-without-tests)
- [Parsers of untrusted input without a property test](#parsers-of-untrusted-input-without-a-property-test)
- [A check of the suite removed or weakened](#a-check-of-the-suite-removed-or-weakened)
- [Coverage figure](#coverage-figure)
- [Tests that cannot fail](#tests-that-cannot-fail)
- [Evidence](#evidence)
- [Not a finding](#not-a-finding)

## New code without tests

Report each function, method, or branch the change adds or alters that no test runs, when a plausible regression there would go unnoticed: a calculation, a parser, an error path, a boundary. Name the function and the regression a test would catch, for example "a `retryDelay` that stopped capping the delay would pass every test".

Report a test the change deletes or weakens, such as a removed case, a loosened assertion, or a new `test.skip`, `test.only`, or `test.todo`, when the behaviour it covered still exists. If the deleted test caught a defect the change introduces, fold this into that defect's finding as part of its cause.

## Parsers of untrusted input without a property test

A function the change adds that parses or decodes untrusted input, with no fast-check property test, is a `minor` finding. Untrusted input is bytes from outside the process: a request or webhook body, an uploaded file, a message from a queue, or a response from another service. The documentation comment, the parameter's source, or a caller usually says where the input comes from: name it in the finding.

A property test counts when it is written with `@fast-check/vitest`'s `test.prop` and calls the function, as typescript-practices' `references/testing.md` shows. Tests with fixed inputs only, however many, do not count. A function that existed before the change, and that the change does not alter, is not a finding. A crash or wrong result that a property run finds is reported at its own severity, not as `minor`.

Report a property test the change adds that sets `seed` or `numRuns` itself, or imports `fc` from `fast-check` instead of the repository's configured module, as `minor`: pull request CI then runs it with random inputs.

CI cannot tell that a property test is missing, so this rule is the review's to enforce. It is not a missing line in the check suite section.

## A check of the suite removed or weakened

When the change removes or weakens a check of the TypeScript check suite in CI, report it as `major`. `checks.md` describes this under "The check suite in CI". A check missing at the base and still missing at the head is a line in the report's check suite section, not a finding.

## Coverage figure

`checks.md` runs the tests with `--coverage --coverage.provider=v8` into a temporary directory outside the repository. From the text report, quote:

- the total line coverage, with the packages it covers;
- each changed file's line, and the uncovered line numbers for a changed function, when that matters to a finding.

A report is still written when tests fail, so the figure stands with the failure noted beside it. If the tests were not run, the coverage figure is a limit: write `not run` and the reason, and quote CI's coverage for the head commit when there is one. Coverage is a figure, not a verdict: a percentage below some target is not a finding.

## Tests that cannot fail

Report a test the change adds that cannot fail for the defect it names:

- it calls the code but checks nothing, or checks only that no exception was thrown;
- its expected value is computed the same way as the code under test;
- it does not `await` the promise it tests, so the test ends before the assertion runs, or it checks a rejection without `await expect(...).rejects`;
- it mocks the module under test, so it tests the mock;
- it waits with a real timer for a condition, where `vi.useFakeTimers()` would do, which makes it slow and flaky;
- an integration test that skips itself when a service or credential is missing, so it passes without running.

## Evidence

- The coverage report: quote the lines for the files and functions you name.
- The diff of the test files: quote a deleted case or a weakened assertion.
- To show that a test cannot fail, you may break the code in the temporary worktree and run the test, then put the code back. That runs the change's code, so it runs only where `checks.md` allows tests to run. Say that you did.
- For a missing property test: the function's documentation comment or caller that shows the input is untrusted, and the test files that call it, none with `test.prop`.

## Not a finding

- A coverage percentage, high or low, by itself.
- No test for code with no logic to get wrong: a constant, a type declaration, a re-export, or generated code.
- No type test for a type the change does not export or that callers do not narrow.
- A missing property test for a function that reads only input the program built itself, or one that existed before the change and that the change does not alter.
- A test style the practices reference prefers, such as one behaviour per test, when the existing tests check the behaviour.
