---
name: review-golang
description: Reviews Go changes for concurrency, error handling, API compatibility, and language-specific test defects. Use for a Go-specific concern named directly, or a Go assignment from review-code; a general request to review Go changes goes to review-code. Does not implement fixes, post feedback, or assess general coverage gaps (review-test-gaps).
---

# review-golang

Review the Go portion of an identified change. Return findings to `review-code` or the user; preserve the reviewed source tree and leave publishing to `review-post`.

## Inputs and scope

Require a diff, its exact base and head commits (or an identified working-tree snapshot), the matching tree, and available requirements and repository guidance. When invoked directly, resolve the installed `review-code` skill and read its `references/findings.md` contract. A delegated assignment supplies that contract. If the target is missing or ambiguous, ask for it before reviewing; use `review-code` to prepare a PR target that has not yet been resolved.

Review `.go` changes and Go module, build, and test configuration that affects them. Follow calls into unchanged code to prove consequences introduced by the diff. If there are no applicable changes, return `not applicable` with the reviewed scope.

## Review

1. **Establish the environment.** Read `go.mod`, relevant build tags, CI checks, and local guidance. Record the Go language version before applying version-sensitive rules, especially loop-variable capture. Identify affected packages and exported contracts.
2. **Trace ownership and termination.** For changed goroutines, channels, and synchronization, identify who starts, cancels, waits, sends, and closes. Trace error and early-return paths as well as success. Check shared-memory access, copied synchronization values, wait-group ordering, bounded work, and sends or receives that remain blocked after a peer exits. A background task may intentionally outlive a request; judge its actual lifecycle contract.
3. **Trace failures and resources.** Follow context deadlines through blocking calls, close resources on every exit, and verify errors reach the caller that must act. Check wrapping and matching together: changing error identity matters when callers depend on it. Examine typed-nil interface values and zero values at the boundaries changed by the diff.
4. **Check compatibility.** Trace changed interfaces, generic constraints, receivers, and exports into consumers. Confirm named types, pointer/value method sets, wire formats, and build variants still meet the documented API. Check module replacements and dependency placement against how consumers build. Treat alternative interface layouts or configuration styles as preferences unless a concrete contract or repository rule is violated.
5. **Inspect Go test mechanics.** Check parallel tests for shared mutable fixtures and version-relevant closure capture, test cleanup for leaked work, and benchmarks for measuring the intended operation. Report an invalid assertion or race in an existing test here. Hand missing scenarios to `review-test-gaps`, with the behavior and relevant files, instead of duplicating coverage findings.
6. **Check evidence.** Use existing project check commands when safe and available; targeted package tests, `go vet`, and race-enabled tests can establish a suspected failure. Inspect commands before execution and keep dependency installation, source changes, and external-service operations out of the review. Record failed, unavailable, and skipped checks separately. An environment failure is a limitation, not evidence that the diff is defective.

## Language practice references

The `golang-pro` skill, bundled with company-skills as its own plugin, carries Go practice references. Where it is installed, invoke it by name and read the reference for each area the diff touches before judging that area. Invoking it loads the skill and gives its directory, which the `references/` paths below resolve from.

| Changed area | Reference |
| --- | --- |
| Goroutines, channels, `select`, sync primitives, backpressure | `references/concurrency.md` |
| Interfaces, embedding, type assertions and switches | `references/interfaces.md` |
| Type parameters and constraints | `references/generics.md` |
| Modules, internal packages, build tags, `go generate` | `references/project-structure.md` |
| Tests, benchmarks, fuzzing, race detection | `references/testing.md` |

Use them under these rules:

- Use the skill for its references. Its `SKILL.md` is a workflow for writing Go; its steps, MUST lists, and output templates are not review criteria.
- A reference shows preferred practice. A departure from it is a finding only with the trigger and consequence, or the cited rule, that **Return** requires.
- The steps in **Review** win where a reference disagrees. `references/testing.md` copies the loop variable (`tt := tt`) for parallel subtests; that is needed only before Go 1.22, so apply step 1's version check.
- Record the references read alongside the checks run. If the skill is not installed, record that as a coverage limit and continue from this skill alone.

## Return

Use the supplied findings contract. Each finding needs a location in the reviewed tree, the changed cause, a concrete trigger and consequence (or a cited objective rule), supporting evidence, severity `critical`/`major`/`minor`, a feasible correction, and source skill/agent/model. State `unknown` for unavailable provenance. Distinguish observations from unexecuted hypotheses. Include the exact reviewed commit or snapshot, packages checked, check outcomes, and gaps even with no findings. Stop when every assigned change has been examined or explicitly marked unreviewed with a reason.
