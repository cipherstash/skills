---
name: audit-pr-feedback
description: Deprecated alias for review-audit, kept so existing explicit invocations keep working until a later release removes it. Runs review-audit unchanged.
argument-hint: "<PR number or URL>"
disable-model-invocation: true
---

# audit-pr-feedback

This skill was renamed to `review-audit`. Read `../review-audit/SKILL.md`, resolved from this skill's installed directory, and follow it exactly as if `review-audit` had been invoked: its skill directory is `../review-audit/`, not this one, so its `<skill dir>`, `scripts/`, and `references/` paths resolve there — passing along every argument and pasted input given here. Tell the user once that `audit-pr-feedback` is deprecated and to invoke `review-audit` from now on.
