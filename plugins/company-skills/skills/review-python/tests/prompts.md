# Behavior cases

## Should activate

- "Use review-python on this PR's Python diff at the supplied commits."
- "Check whether the changed async worker loses exceptions or leaks its client."
- "Review the Python changes." If the target cannot be inferred, ask for the diff or PR.

## Should not activate

- "Write Python tests for these edge cases."
- "Check which new findings are already covered by PR feedback." Use review-cross-check.

## Expected behavior

- Demonstrate a changed mutable default retaining another caller's data; return the trigger, impact, location, evidence, correction, severity, and provenance.
- Distinguish gather behavior from task-group behavior using the supported runtime; do not claim that gather always cancels siblings on the first exception.
- Accept an async test executed by configured auto mode even without an explicit marker, and inspect actual mock lookup before alleging a patch is ineffective.
- Accept implicit exception context when it preserves the needed information. Do not assert os.path is deprecated or all packages need an __init__.py.
- Report a demonstrated ineffective test assertion here; pass missing scenarios to review-test-gaps without duplicate coverage findings.
- Keep unavailable mypy, missing dependencies, and baseline import failures in limitations. Do not install dependencies, change source, or post feedback.
- Return not applicable for a diff with no relevant Python changes; preserve working-tree snapshot identity rather than attributing dirty files to HEAD.
