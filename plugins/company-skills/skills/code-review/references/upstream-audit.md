# Capability audit and port decisions

Audited [auxesis/junk pr-review at ddc19fafd4e952dfc6aa2ff2c05042c0773b8015](https://github.com/auxesis/junk/tree/ddc19fafd4e952dfc6aa2ff2c05042c0773b8015/pr-review). The source's runtime review instructions are Python rubrics, not installed skills. This package independently expresses the useful capabilities as host-native skills; it does not copy the source runner or its rubric text.

| Source within pr-review | Destination |
| --- | --- |
| src/pr_review/review_types/test_gap.py | review-test-gaps |
| src/pr_review/review_types/infracode.py | review-infracode |
| src/pr_review/review_types/golang.py | review-golang |
| src/pr_review/review_types/typescript.py | review-typescript |
| src/pr_review/review_types/rust.py | review-rust |
| src/pr_review/review_types/python.py | review-python |
| synthesis.py, attribution.py, context/ | code-review scope, evidence checks, deduplication, context and provenance |
| output.py, payload.py, diff_guard.py | Existing review-post owns publication and exact line placement |
| context/filter.py | Existing review-cross-check owns duplicate matching; review-audit and review-fix receive the resulting feedback |

Excluded: headless backend launchers, model matrices, cooperative processes, terminal UI, CLI/install configuration, Python packaging and lockfiles, custom posting payloads, and the source's test runner. No external agent setup is needed. No language checker is imported; review findings use the existing posting workflow’s plain wording rules.

Corrections made during adaptation:

- Python exception chaining, asyncio task failure, and Go loop captures require actual language/runtime semantics. The source's blanket claims about gather cancelling siblings, lost implicit exception context, and deprecated os.path were not retained.
- Infrastructure divergence and fixed regions require evidence of intended equivalence or a concrete failure. Resource replacement and IAM scope depend on resource/provider behavior.
- Missing fuzz/property/doctests or preferred code patterns are not automatic defects. Test gaps require a plausible missed regression and inspection of existing protection.
- Unavailable checks and failed reviewers remain visible as coverage limits. Finding counts are not quotas or caps.
- A fix in a later open stacked PR does not remove the current PR's risk. Existing discussion is handled through the established cross-check workflow.
- Off-diff findings remain valid evidence; review-post decides whether they belong inline or in the summary.

The audit found no root license covering the source project's original rubrics. Its vendor directory separately contains MIT-licensed Jeffallan/claude-skills material pinned at efebc44c90ae6eb3b36ff1c53802a765418481b9. No vendored source or rubric text is redistributed here. If future maintenance copies that material, carry its applicable license and notices with the copy.

Upstream tests mainly exercise prompt construction and orchestration mechanics. This port supplies behavior cases and requires observed host testing to establish runtime behavior; structural validation alone is not such evidence.
