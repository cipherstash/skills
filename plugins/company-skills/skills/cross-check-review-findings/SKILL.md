---
name: cross-check-review-findings
description: Deprecated alias for review-cross-check, kept so existing explicit invocations keep working until a later release removes it. Runs review-cross-check, which now ends at a report and offers review-post to publish findings, instead of drafting a review response itself.
argument-hint: "<PR number or URL> [pasted findings]"
disable-model-invocation: true
---

# cross-check-review-findings

This skill was renamed to `review-cross-check`. Read `../review-cross-check/SKILL.md`, resolved from this skill's installed directory, and follow it exactly as if `review-cross-check` had been invoked: its skill directory is `../review-cross-check/`, not this one, so its `<skill dir>`, `scripts/`, and `references/` paths resolve there — passing along every argument and pasted input given here. Tell the user once that `cross-check-review-findings` is deprecated and to invoke `review-cross-check` from now on, and that it no longer drafts a review response: it ends at a report, and review-post publishes the findings.
