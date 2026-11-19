# Behavior cases

## Should activate

- "Use review-typescript for this PR's TypeScript diff at the supplied commits."
- "Check whether this new type predicate and its consumers handle malformed JSON safely."
- "Check the TypeScript branch's new type guards." If no branch or base can be identified, ask for the target.

## Should not activate

- "Review the TypeScript branch." Use review-code, which selects review-typescript alongside review-test-gaps and hands findings to review-cross-check.
- "Refactor these TypeScript types."
- "Post these verified findings to GitHub." Use review-post.

## Expected behavior

- A JavaScript-only diff receives runtime, input-boundary, async, and consumer review without requiring a tsconfig or reporting missing TypeScript as a defect.

- Follow an unsound predicate from external input to a concrete failing consumer and return the head location, trigger, evidence, severity, correction, and source.
- Accept an assertion justified by an earlier runtime schema check; do not report it merely because it uses `as`.
- Read inherited compiler options before evaluating unchecked indexing and nullability. Check published declarations and consuming imports for a packaging regression.
- Reject blanket claims that enabling skipLibCheck, using an enum, or omitting a never default is itself a defect without an applicable rule or demonstrated failure.
- Identify a changed type test whose `any` cast hides the exact contract under test; route absent type-test scenarios to review-test-gaps.
- Report missing node_modules or unavailable local tools as limitations; do not use a downloading runner or claim checks passed.
- Return not applicable for a non-TypeScript diff, and retain snapshot identity for uncommitted changes.
- With the bundled `typescript-pro` skill installed, read `references/type-guards.md` before judging a changed type predicate, and list it among the references read. Do not follow that skill's authoring workflow, and do not report a departure from its examples without a trigger and consequence.
- Without the `typescript-pro` skill installed, review from this skill alone and report the missing references as a coverage limit.
