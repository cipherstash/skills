# Behavior cases

## Should activate

- "Use review-rust on this base/head diff and matching worktree."
- "Check the soundness and cancellation behavior of this Rust API change."
- "Check my Rust change for panics on bad input." If there is no identifiable diff or target, ask for it.

## Should not activate

- "Review my Rust code." Use review-code, which selects review-rust alongside review-test-gaps and hands findings to review-cross-check.
- "Implement a Rust builder following our conventions."
- "Audit the existing PR comments." Use review-audit.

## Expected behavior

- Trace an unsafe slice construction to the caller-controlled length and violated bounds; distinguish that defect from a documentation-only safety-rule violation.
- Read repository guidance and apply rust-sdk-dx, rust-security, and rust-testing only where their scopes match. Preserve their identities in review provenance.
- Show the cancellation sequence that leaves a changed operation inconsistent, or accept the implementation when cleanup preserves its invariant.
- Avoid blanket findings for test unwraps, detached tasks, missing Clone derives on secret types, or harmless cold-path allocations.
- Check feature constraints before choosing test commands; do not run mutually exclusive features together merely because a generic checklist says all-features.
- Route missing test scenarios to review-test-gaps; report an existing panic test that accepts the wrong failure as an assertion defect with evidence.
- Do not turn unavailable Clippy, a missing cross target, or baseline failures into introduced defects. Return check limitations and accurate source/snapshot provenance.
- With the bundled `rust-engineer` skill installed, invoke it by name and read `references/async.md` before judging a changed task shutdown path, and list it among the references read. Do not follow that skill's authoring workflow, and do not report a departure from its examples without a trigger and consequence.
- Without the `rust-engineer` skill installed, review from this skill alone and report the missing references as a coverage limit.
