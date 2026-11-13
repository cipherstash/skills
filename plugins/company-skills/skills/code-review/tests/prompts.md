# Behavior cases

## Should activate

- Review https://github.example/team/service/pull/42 before we merge it.
- Assess this branch since its merge-base with main, including the tests it needs.
- Review my changes. If the repository and comparison cannot be inferred, ask for the missing scope.

## Should not activate

- Audit which existing PR review threads are still unresolved; use review-audit.
- Fix these review findings; use review-fix.
- Publish the finished review; use review-post.

## Expected behavior

- A mixed Rust/Terraform diff selects review-rust, review-infracode, and review-test-gaps; no Go/Python/TypeScript reviewer is launched without a relevant consumer. The coordinator checks requirements and interactions.
- A TypeScript input-validation change with a happy-path-only test returns a supported defect or gap with the concrete trigger, expected assertion, actual code/test evidence, and preserved attribution.
- A documentation-only diff receives accuracy/requirements review without all six specialists. An unsupported language gets general review with a disclosed specialist limit.
- PR scope uses its canonical repository and recorded head, including forks and Enterprise hosts. Dirty user work is preserved. A moved PR head is reported or re-verified, never silently adopted.
- Explicit two-endpoint ranges are not silently changed to merge-base comparisons. Staged-only requests omit unstaged edits. All-working-change requests include relevant untracked files and identify the actual dirty snapshot, not HEAD alone.
- Missing target/base prompts clarification; invalid refs or unreadable diffs stop review. An empty verified diff is reported as empty rather than generating findings. Missing specs or optional linked issues are disclosed without inventing requirements.
- Delegates receive actual assignments, tree/snapshot paths, and the complete findings contract. A host with no subagents executes sequentially and reports that mode.
- Duplicate root causes retain all producing sources; distinct defects on the same line survive. Failed delegates get one bounded retry and remain visible as incomplete coverage. All failed assignments cannot produce a clean review.
- A later open stacked PR fixing a defect does not erase the current-head risk. Existing reviewer dismissal is context, not automatic suppression.
- For a PR with findings, cross-check receives complete evidence and provenance unless raw review alone was requested. Only New and Adds to existing are passed onward, with reply URLs and verified head retained.
- A zero-findings result retains run provenance and reviewed commit without calling cross-check on missing findings. An authorized post still states incomplete coverage. An ordinary review does not post, fix, resolve threads, commit, or push.
- Objective convention and test-oracle findings cite their rule or missed regression; unsupported preferences remain outside the ledger. Unknown model or effort fields remain unknown.
