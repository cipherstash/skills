---
name: review-python
description: Reviews Python changes for shared state, exception and resource behavior, async lifecycles, packaging compatibility, and ineffective tests. Use for a focused Python diff review or a Python assignment from code-review. Does not implement fixes, post feedback, or assess general coverage gaps (review-test-gaps).
---

# review-python

Review the Python portion of an identified change. Return findings to `code-review` or the user; preserve the reviewed source tree and leave publishing to `review-post`.

## Inputs and scope

Require a diff, its exact base and head commits (or an identified working-tree snapshot), the matching tree, and available requirements and repository guidance. When invoked directly, resolve the installed `code-review` skill and read its `references/findings.md` contract. A delegated assignment supplies that contract. If the target is missing or ambiguous, ask for it before reviewing; use `code-review` to prepare a PR target that has not yet been resolved.

Review Python changes and packaging, typing, or test configuration affecting them. If there are no applicable changes, return `not applicable` with the reviewed scope.

## Review

1. **Establish runtime assumptions.** Read supported Python versions, package/build configuration, installed test plugins, typing settings, and repository guidance. Evaluate annotations, namespace packages, async tests, and standard-library behavior against that environment.
2. **Follow state and inputs.** Check mutable defaults and class attributes, closure binding, iterator consumption, mutation during iteration, import side effects, and identity/value comparisons. Demonstrate cross-call contamination or a concrete wrong result rather than flagging syntax alone. Follow untrusted data through parsing, coercion, and validation into consumers.
3. **Trace exceptions and resources.** Follow cleanup through success, exception, early return, and cancellation. Check broad handlers for swallowed failures, exception translation for lost information, and `finally` for suppressed results or errors. Ordinary exception chaining can retain context without an explicit `from`; inspect actual semantics before alleging a lost cause.
4. **Trace async execution.** Determine whether coroutines run, who retains and awaits tasks, and how task failures and cancellation reach the owner. Inspect blocking operations inside event-loop work and the lifetime of async clients/generators. Distinguish `gather`, task groups, and caller-driven cancellation under the project's Python version; do not infer sibling cancellation from every exception.
5. **Check interfaces and packaging.** Follow changed return shapes, optional values, protocols, serialization, imports, entry points, dependency groups, and distribution contents into callers. An annotation cannot validate external data. Require a broken contract or cited rule for missing annotations or API-style findings; `os.path`, manual constructors, and namespace packages are not defects by themselves.
6. **Inspect test validity.** Verify mocks replace the name the code actually uses, assertions detect the intended wrong result, async tests execute under the configured runner, and fixtures restore mutable/global state. Send absent scenarios to `review-test-gaps` with the changed behavior and relevant files. Do not assume a missing async marker means a test is skipped without reading runner configuration.
7. **Check evidence.** Use the configured lint/type-check and focused test commands when safe and already available, honoring their configuration. Inspect scripts before execution; avoid dependency installation, source fixes, and auto-fix options. Record checks actually run and distinguish setup or baseline errors from new failures. Continue a source-based review when execution is unavailable and state the resulting limits.

## Return

Use the supplied findings contract. Each finding needs a reviewed-tree location, changed cause, concrete trigger and impact (or a cited objective rule), evidence, severity `critical`/`major`/`minor`, feasible correction, and source skill/agent/model. Use `unknown` for unavailable provenance. Include the reviewed commit or snapshot, interpreter/configuration assumptions, check outcomes, and skipped work even with no findings. Stop when every assigned change is examined or explicitly marked unreviewed with a reason.
