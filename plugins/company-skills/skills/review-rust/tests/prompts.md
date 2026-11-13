# Behavior cases

## Should activate

- "Use review-rust on this base/head diff and matching worktree."
- "Check the soundness and cancellation behavior of this Rust API change."
- "Review my Rust code." If there is no identifiable diff or target, ask for it.

## Should not activate

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
