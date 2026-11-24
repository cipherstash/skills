# Step: testing and coverage

Area 3, high priority. Read this, and golang-practices' `references/testing.md`, before judging the change's tests. The practices reference holds the rules for writing tests. This file says what to look for in a change, what evidence shows it, and what is not a finding.

## Contents

- [New code without tests](#new-code-without-tests)
- [The race detector](#the-race-detector)
- [Coverage figure and untested functions](#coverage-figure-and-untested-functions)
- [Tests that cannot fail](#tests-that-cannot-fail)
- [Evidence](#evidence)
- [Not a finding](#not-a-finding)

## New code without tests

Report each function, method, or branch the change adds or alters that no test runs, when a plausible regression there would go unnoticed: a calculation, a parser, an error path, a boundary. Name the function and the regression a test would catch, for example "a `Backoff` that stopped capping the delay would pass every test".

Report a test the change deletes or weakens, such as a removed case or a loosened assertion, when the behaviour it covered still exists. If the deleted test caught a defect the change introduces, fold this into that defect's finding as part of its cause.

## The race detector

CI runs the tests with `-race`, and the review reads that result, as `checks.md` sets out. The result is shared with the concurrency step. A race-enabled pass covers only the paths the tests ran. When the change adds concurrent code that no test runs concurrently, say so here: the race detector cannot see it.

## Coverage figure and untested functions

CI's coverage report is `go tool cover -func` output for the profile its race-enabled tests wrote. From that output, report:

- the total, from its `total:` line, as the coverage figure, with the packages it covers;
- every function in a changed file at `0.0%`, by name and `file:line`, which is the first line of the function;
- for a changed function that is partly covered, whether the changed lines are among those run, when that matters to a finding and CI publishes the profile.

Without a CI coverage report for the head, the coverage figure is a limit: write `not run` and the reason, and find untested code by reading: search the tests for calls to each changed function. Coverage is a figure, not a verdict: a percentage below some target is not a finding.

## Tests that cannot fail

Report a test the change adds that cannot fail for the defect it names:

- it calls the code but checks nothing, or checks only that no error came back;
- its expected value is computed the same way as the code under test;
- it uses `t.Errorf` before a step that panics, such as indexing a result that may be empty, where `t.Fatalf` would stop it;
- it waits with `time.Sleep` for a condition, which makes it slow and flaky;
- a parallel subtest captures the loop variable without a copy, only in a module below Go 1.22.

## Evidence

- CI's coverage report: quote the lines for the functions you name, or the search that found no test calling a function.
- The diff of the test files: quote a deleted case or a weakened assertion.
- To show that a test cannot fail, name the change to the code that it would still pass, such as a `Backoff` that stopped capping the delay. The review does not make that change or run the test.

## Not a finding

- A coverage percentage, high or low, by itself.
- No test for code with no logic to get wrong: a constant, a type declaration, a one-line getter, or generated code.
- A missing fuzz test, benchmark, or testable example, unless it would catch a plausible regression.
- A test style the practices reference prefers, such as table-driven tests, when the existing tests check the behaviour.
