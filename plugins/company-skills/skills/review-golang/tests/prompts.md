# Behavior cases

## Should activate

- "Use review-golang on the supplied base/head diff and tree."
- "Check whether these Go worker changes leak goroutines when a request is cancelled."
- "Review my Go changes." With no identifiable target, ask for the diff or PR rather than guessing a branch.

## Should not activate

- "Implement a Go worker pool."
- "Find missing test scenarios across this repository." Use review-test-gaps.

## Expected behavior

- Trace a new blocked channel send through the receiver's cancellation path and return its trigger, consequence, head location, fix, and provenance.
- Examine Go version and variable declaration before claiming a parallel subtest captures the wrong loop variable; do not report the historical loop-variable bug solely from its syntax.
- Keep an intentional process-lifetime goroutine when its shutdown mechanism and contract are satisfied.
- Find an error-wrapping regression only after inspecting the caller's matching behavior; avoid generic style objections about interface placement.
- Report a missing race toolchain as a skipped check, never a successful test or a code defect. Do not install dependencies, fix source, or post a review.
- Preserve the exact dirty snapshot identity for a working-tree review; do not label it a clean HEAD review.
- Return not applicable for a diff containing no Go or relevant Go configuration changes.
