---
name: review-test-gaps
description: Reviews changed behavior and tests for missing regression protection, ineffective assertions, and boundary or negative-case gaps. Use for a focused test-coverage review or when delegated by code-review. Does not implement tests, equate coverage percentages with correctness, or replace language and infrastructure defect review.
---

# review-test-gaps

Accept the comparison, reviewed tree or working snapshot, changed files, and requirements from `code-review`. For a standalone request, resolve these from the user's context and ask for the missing target or comparison if ambiguous. Read the installed `code-review` skill's `references/findings.md` for the output contract unless supplied in the assignment. Review only this scope, reading surrounding tests and callers as needed.

## Map behavior to protection

1. Read repository test guidance, the closest representative tests, and the harness configuration. Identify unit, integration, property, contract, generated, and end-to-end coverage relevant to each changed behavior. Follow test discovery and CI selection; a file that is never collected does not protect the behavior.
2. For each meaningful behavior changed or removed, identify the expected outcome, inputs/state, and existing assertions that would detect a regression. Include modified tests: weakening an assertion, an overbroad exception match, or mocking away the changed path can remove protection while leaving the suite green.
3. Examine error exits, permissions, malformed inputs, empty/null values, exact limits, retries, cleanup, cancellation, and concurrent state transitions where the change makes them relevant. For codecs, check both round trips and independent expected values: two symmetric mistakes can pass a round trip. For encryption, distinguish wrong-key, wrong-context, and tampered-data failures; verify fresh randomness only where the API promises it.
4. Trace shared helpers and fixtures before declaring a gap. A parameterized or integration test may already exercise the path. Missing fuzzing, property tests, doctests, or a test per branch is not automatically a finding; explain a material regression the existing protection would miss.

Completion: every assigned behavior is protected by identified assertions, has a substantiated gap, or is marked unknown with the search/coverage limit.

## Make gaps actionable

For each gap, cite the changed behavior and the relevant existing tests, describe a plausible mutation or regression that would pass them, and propose inputs/actions/assertions that distinguish correct behavior. Match the repository's actual framework, fixtures, naming, and async conventions. Include a short test sketch when the harness is known; otherwise give a precise test scenario and name the missing setup information. Do not invent helpers or claim a sketch ran.

Use existing focused test commands when useful and permitted. Record exact results and setup failures. Keep this review read-only; implementation belongs to `review-fix`. If a production defect is found while tracing tests, report it as such with evidence and identify the related gap without duplicating one claim as two findings.

Pure prose changes or inert metadata can return not applicable with a reason. Executable CI/task changes may need tests of their behavior; do not exclude them merely because they are YAML or shell.

Return findings using the shared contract, behaviors/tests inspected, checks run, limitations, and provenance. Return explicit no findings when appropriate. Do not post comments or resolve threads.
