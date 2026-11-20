---
name: review-rust
description: Reviews Rust changes for soundness, panic and error paths, async lifecycles, public API compatibility, and invalid test assertions. Use for a Rust-specific concern named directly, or a Rust assignment from review-code; a general request to review Rust changes goes to review-code. Does not implement fixes, post feedback, or assess general coverage gaps (review-test-gaps).
---

# review-rust

Review the Rust portion of an identified change. Return findings to `review-code` or the user; preserve the reviewed source tree and leave publishing to `review-post`.

## Inputs and scope

Require a diff, its exact base and head commits (or an identified working-tree snapshot), the matching tree, and available requirements and repository guidance. When invoked directly, resolve the installed `review-code` skill and read its `references/findings.md` contract. A delegated assignment supplies that contract. If the target is missing or ambiguous, ask for it before reviewing; use `review-code` to prepare a PR target that has not yet been resolved.

Review Rust code and Cargo, feature, target, or test configuration affecting it. If there are no applicable changes, return `not applicable` with the reviewed scope.

## Review

1. **Establish contracts.** Read manifests, toolchain/MSRV settings, selected features, and repository guidance first. Apply available `rust-sdk-dx` to changed public library APIs, `rust-security` to secrets/cryptography/authentication, and `rust-testing` to Rust tests, respecting their scopes and explicit project rules. Record which skills and rules apply; report a missing convention skill as a limitation rather than inventing its requirements.
2. **Prove safety invariants.** For changed unsafe code, FFI, raw pointers, pinning, or `Send`/`Sync` implementations, read the enclosing ownership and drop paths. Check validity, alignment, bounds, aliasing, initialization, lifetimes, and thread access against the stated safety contract. Distinguish a missing required safety explanation from demonstrated unsoundness; give a violating caller or state for the latter.
3. **Trace failures.** Follow user-controlled input into indexing, arithmetic, conversions, panics, and fallible operations. Verify recovery and error conversion preserve the contract and required context without leaking secrets. An `unwrap` in a test or a proven invariant is not automatically a production failure. Check public error changes against downstream matching and compatibility expectations.
4. **Trace async and shared-state lifecycles.** Examine lock duration, blocking operations, task results, cancellation, channel capacity, and cleanup. Explain how a particular scheduling or cancellation sequence loses state, progress, or an error. A dropped task handle is a defect only when the required supervision or shutdown behavior is lost.
5. **Check API and build compatibility.** Follow ownership, lifetime, trait, generic, derive, visibility, and feature changes into consumers. Verify supported target/feature combinations and serialization contracts. Require concrete caller costs or an applicable convention for API-shape findings; avoid speculative allocation tuning and blanket all-features assumptions when features are mutually exclusive.
6. **Inspect test assertions.** Check panic expectations, async completion, isolation, and assertions against the failure they claim to detect. Read relevant doctests as consumer examples. Send missing unsafe/concurrency/parser/API scenarios to `review-test-gaps` with the affected invariant; do not demand fuzzing or a new test style without a specific risk or rule.
7. **Check evidence.** Use existing project checks when safe and available, with the supported features and targets. Prefer the project's test runner and commands; focused tests, doctests, and Clippy can supply evidence. Inspect build/test scripts before execution. Do not install toolchains, change source, or apply formatter/linter fixes. List unavailable tools, baseline failures, and skipped checks separately from findings.

## Language practice references

The `rust-engineer` skill, bundled with company-skills as its own plugin, carries Rust practice references. Where it is installed, invoke it by name and read the reference for each area the diff touches before judging that area. Invoking it loads the skill and gives its directory, which the `references/` paths below resolve from.

| Changed area | Reference |
| --- | --- |
| Futures, tasks, `select`, streams, channels, shared state, shutdown | `references/async.md` |
| `Result` and `Option`, custom error types, conversion, context | `references/error-handling.md` |
| Borrowing, lifetimes, smart pointers, interior mutability, `Pin`, `Drop` | `references/ownership.md` |
| Unit, integration, async and doc tests, mocking, property tests, fuzzing | `references/testing.md` |
| Trait definitions, bounds, trait objects, derives, conversion traits | `references/traits.md` |

Use them under these rules:

- Use the skill for its references. Its `SKILL.md` is a workflow for writing Rust; its steps, MUST lists, and output templates are not review criteria.
- A reference shows preferred practice. A departure from it is a finding only with the trigger and consequence, or the cited rule, that **Return** requires.
- The company convention skills named in step 1 and the steps in **Review** win where a reference disagrees. `references/error-handling.md` and `references/testing.md` prefer particular crates and test styles; steps 3 and 6 hold, so an `unwrap` behind a proven invariant or an absent fuzz test is not a defect by itself.
- Record the references read alongside the checks run. If the skill is not installed, record that as a coverage limit and continue from this skill alone.

## Return

Use the supplied findings contract. Each finding needs a reviewed-tree location, changed cause, concrete trigger and consequence (or a cited objective rule), evidence, severity `critical`/`major`/`minor`, feasible correction, and source skill/agent/model. Use `unknown` for unavailable provenance. Include the reviewed commit or snapshot, relevant feature/target coverage, conventions consulted, checks actually run, and limitations even with no findings. Stop when every assigned change has been examined or explicitly marked unreviewed with a reason.
