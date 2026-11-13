---
name: review-typescript
description: Reviews TypeScript and JavaScript changes for runtime/type mismatches, API compatibility, asynchronous behavior, and invalid tests. Use for a focused TypeScript or JavaScript diff review or an assignment from code-review. Does not implement fixes, post feedback, or assess general coverage gaps (review-test-gaps).
---

# review-typescript

Review the TypeScript and JavaScript portion of an identified change. Return findings to `code-review` or the user; preserve the reviewed source tree and leave publishing to `review-post`.

## Inputs and scope

Require a diff, its exact base and head commits (or an identified working-tree snapshot), the matching tree, and available requirements and repository guidance. When invoked directly, resolve the installed `code-review` skill and read its `references/findings.md` contract. A delegated assignment supplies that contract. If the target is missing or ambiguous, ask for it before reviewing; use `code-review` to prepare a PR target that has not yet been resolved.

Review TypeScript and JavaScript source, including TSX/JSX, declarations, and compiler/package configuration that changes their behavior. Apply runtime, input-boundary, async, and consumer checks to JavaScript-only projects; apply type-system checks only where TypeScript or checked JavaScript is configured. If there are no applicable changes, return `not applicable` with the reviewed scope.

## Review

1. **Establish compiler and runtime assumptions.** Read the effective `tsconfig` chain, package exports, compiler/runtime versions, and local guidance. Determine null/index checking, module resolution, declaration generation, and the build path used by affected consumers.
2. **Follow data across type boundaries.** Trace assertions, `any`, non-null assertions, suppression comments, and untyped inputs to the validation or invariant that makes them safe. Check that predicates establish all properties they promise. Types disappear at runtime: demonstrate the input that passes through a claimed guarantee and breaks its consumer, rather than treating every assertion as a defect.
3. **Exercise changed states.** Follow newly possible union variants, missing keys, null/undefined values, empty arrays, and mutation across asynchronous work. Check promise rejection handling, detached work, and ordering where the change depends on completion. Prove a reachable bad state before recommending an exhaustiveness check or a different state model.
4. **Check public contracts and build output.** Follow changed generics, overloads, inference, readonly promises, and declaration files into real consumers. Examine runtime import side effects, module cycles, and exports with the configured emit and bundler. A compiler-option change, enum, value import, or widened annotation alone is not a finding: identify the broken consumer guarantee or explicit repository rule.
5. **Inspect type-test validity.** Check whether assertions or `any` in a test bypass the type relation it claims to test, and whether negative type tests actually compile under the test command. Identify a test that can pass despite the demonstrated bad implementation. Send missing type/runtime scenarios to `review-test-gaps` with their contracts and relevant files.
6. **Check evidence.** Use the project's installed type-check, lint, and focused test commands when safe and available. Avoid package runners that download missing tools. Inspect scripts before execution; do not change code, loosen compiler options, install dependencies, or auto-fix diagnostics. Separate baseline errors and setup limitations from regressions introduced by the diff.

## Return

Use the supplied findings contract. Each finding needs a reviewed-tree location, changed cause, concrete trigger and impact (or a cited objective rule), evidence, severity `critical`/`major`/`minor`, feasible correction, and source skill/agent/model. Use `unknown` for unavailable provenance. Record the reviewed commit or snapshot, applicable configurations, checks actually run, failures, and skipped checks even when no findings survive. Stop when every assigned change is examined or explicitly marked unreviewed with a reason.
