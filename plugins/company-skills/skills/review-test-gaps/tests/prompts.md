# Behavior cases

## Should activate

- Review this PR for missing tests of changed behavior.
- Will the assertions catch a regression in the new retry and cancellation paths?
- Check test coverage for my changes; ask for the comparison if the target is unclear.

## Should not activate

- Write the missing regression tests and fix the defect; use review-fix.
- Audit production cloud permissions without a test-coverage question; use review-infracode.

## Expected behavior

- Identify changed behavior, inspect the real harness and closest tests, then search shared integration/property tests before asserting a gap.
- A parser accepts invalid input while tests assert only valid input: describe the missing rejection assertion, concrete malformed case, and relevant locations. Distinguish a proven production bug from a plausible untested regression.
- A roundtrip test whose encoder and decoder share the same wrong mapping needs an independent expected value; do not claim roundtrip coverage proves correctness.
- A removed assertion or undiscovered async test is evaluated for lost protection. Changed executable CI code is not excluded as documentation.
- Existing parameterized coverage refutes a candidate gap. Trivial getters and absence of fuzzing/doctests alone produce no finding.
- Sketches match actual helpers/frameworks and are labeled unexecuted unless run. Missing tooling and unavailable generated tests become limits, not invented results.
- Output includes scope, evidence, severity, sources, inspected behaviors, checks and limits, including explicit no findings for a prose-only diff. No code changes or comments are published.
