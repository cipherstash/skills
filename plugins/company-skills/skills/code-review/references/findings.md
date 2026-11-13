# Review findings contract

Use this contract for coordinator and specialist output. It is a handoff format, not a GitHub API payload. Markdown is sufficient; keep every field explicit enough for another agent to verify without the original conversation.

## Review run

- Target: canonical PR URL or local repository and requested comparison.
- Reviewed state: full head and comparison-base SHAs, comparison semantics, or a dirty snapshot identity and its base. A dirty snapshot is not a reviewed commit for posting.
- Provenance: host, coordinator and delegate identifiers, actual model IDs and effort when exposed, and skills used. Use `unknown` for unavailable values.
- Coverage: selected skills and assigned areas, completed/failed/skipped assignments and reasons, context unavailable, commands run and observed results. Separate static inspection from executed checks.
- Result: findings, unresolved questions, or an explicit no-findings result qualified by coverage. Retain provenance even with zero findings.

## Each finding

- Stable local ID and short title.
- Location: repository-relative path and head line or range; state old-side/deleted or design-level evidence accurately. Do not invent a new-side anchor merely to make a comment inline. Posting placement belongs to review-post.
- Claim and kind: behavioral defect, test gap, or objective contract/convention violation.
- Trigger and impact: concrete input, state, or deployment condition and the wrong result. For a test gap, name the plausible regression and why current assertions miss it; do not claim the production bug exists. For a convention violation, cite the applicable rule and mark runtime failure as not applicable if none is claimed.
- Evidence: head code and relevant caller/test/rule locations, plus any commands actually run and their results. Distinguish observed facts from assumptions. Unverified provider/version behavior is an open question until checked.
- Severity: `critical` for demonstrated catastrophic impact such as broad compromise or irreversible data loss; `major` for material incorrect behavior, security exposure, or loss of service under a concrete trigger; `minor` for bounded defects or worthwhile test/contract gaps. Preserve any original scale and explicit blocking designation; do not label every hypothetical gap blocking.
- Suggested fix: a focused correction or concrete test case, with the expected outcome. A sketch is illustrative unless verified against the actual harness; state dependencies and avoid invented helpers.
- Sources: all producing skills/agents and their known model IDs, or `unknown`. Keep this attribution through verification and merging.

Keep subjective preferences and unsupported suspicions outside the findings ledger. A lack of tests is not itself proof of a production defect. A passing suite is not proof that omitted cases are covered. Search relevant integration, generated, property, and shared contract tests before asserting absence.

## Downstream preservation

`review-cross-check` may mint its own IDs: retain enough content to trace the original entries. It adds verdicts and existing-comment URLs; only its New and Adds to existing sections proceed to posting. An addition carries only new material and the selected existing comment URL. `review-post` handles severity normalization, current-head checks, line placement, and publication authorization.

For `review-audit` and `review-fix`, the published or supplied claim must stand alone: include the trigger, observed evidence, consequence, and correction. Never rely on a delegate name as proof. Re-check the receiving head; a finding about an older commit may already be fixed.
