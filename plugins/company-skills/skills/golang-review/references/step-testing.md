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

When the change removes or weakens a check of the Go check suite in CI, report it as `major`. `checks.md` describes this under "The check suite in CI".

## The race detector

Tests run with `-race`, as `checks.md` sets out. The run is shared with the concurrency step. A race-enabled pass covers only the paths the tests ran. When the change adds concurrent code that no test runs concurrently, say so here: the race detector cannot see it.

## Coverage figure and untested functions

`checks.md` runs the tests with `-coverprofile` into a file in a temporary directory outside the repository, then `go tool cover -func=<file>`. From that output, report:

- the total, from its `total:` line, as the coverage figure, with the packages it covers;
- every function in a changed file at `0.0%`, by name and `file:line`, which is the first line of the function;
- for a changed function that is partly covered, whether the changed lines are among those run, when that matters to a finding. `go tool cover -html` shows this, but it opens a browser: read the profile's lines for that file instead, where each block ends with a count of `0` when it never ran.

A profile is still written when tests fail, so the figure stands with the failure noted beside it. If the tests were not run, the coverage figure is a limit: write `not run` and the reason. Coverage is a figure, not a verdict: a percentage below some target is not a finding.

## Tests that cannot fail

Report a test the change adds that cannot fail for the defect it names:

- it calls the code but checks nothing, or checks only that no error came back;
- its expected value is computed the same way as the code under test;
- it uses `t.Errorf` before a step that panics, such as indexing a result that may be empty, where `t.Fatalf` would stop it;
- it waits with `time.Sleep` for a condition, which makes it slow and flaky;
- a parallel subtest captures the loop variable without a copy, only in a module below Go 1.22.

## Evidence

- The coverage profile and `go tool cover -func` output: quote the lines for the functions you name.
- The diff of the test files: quote a deleted case or a weakened assertion.
- To show that a test cannot fail, you may break the code in the temporary worktree and run the test, then put the code back, as `checks.md` describes. Say that you did.

## Not a finding

- A coverage percentage, high or low, by itself.
- No test for code with no logic to get wrong: a constant, a type declaration, a one-line getter, or generated code.
- A missing fuzz test, benchmark, or testable example, unless it would catch a plausible regression. The exception: a function the change adds that parses or decodes untrusted input, with no Fuzz target, is a `minor` finding. A function that existed before the change is not a finding. A crash that a fuzz run finds is reported at its own severity, not as `minor`.
- A test style the practices reference prefers, such as table-driven tests, when the existing tests check the behaviour.
