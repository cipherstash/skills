---
name: review-infracode
description: Reviews infrastructure, deployment, CI permissions, task definitions, and observability changes for lifecycle, access, availability, and operational defects. Use for a focused infrastructure review or when delegated by code-review. Does not provision resources, apply plans, or set up review agents.
---

# review-infracode

Accept the comparison, reviewed tree or working snapshot, assigned files, and intended deployment behavior from `code-review`. For a standalone request, resolve these from context and ask for an ambiguous target or base. Read the installed `code-review` skill's `references/findings.md` unless the contract was supplied in the assignment.

## Trace operational effects

Read repository deployment guidance, resource definitions, module callers, environment overrides, and relevant CI/task configuration. Determine tool/provider versions from the project. Inspect equivalent sibling stacks only where they share an intended invariant; an intentional regional or service difference is not a defect.

Review each assigned change for:

- Resource identity and replacement: renamed addresses, changed keys/counts, immutable attributes, persistence, migration declarations, and deletion protection. Establish the state transition from configuration and available plan evidence; do not assert every rename destroys a resource. Cite the version-specific provider behavior when replacement depends on it.
- Availability and recovery: rollout ordering, health checks, dependencies, retention, backup/restore assumptions, failure recovery, and backward compatibility during mixed-version deployments.
- Access boundaries: who can perform the new action against which resource, trust conditions, role passing, cross-account access, and CI token permissions. Evaluate the effective policy and required operation; some actions require wildcard resources, so a wildcard alone is not proof of excessive access.
- Configuration flow: defaults, region/account/subnet references, secrets handling, variable interpolation, shell quoting, and which environments consume the value. Report fixed values when they violate an actual portability contract or misroute a concrete deployment.
- Observability: whether changed labels, selectors, thresholds, scrape/discovery rules, and alert routing still observe the intended service and failure condition.
- Execution wiring: CI event/permission combinations, untrusted inputs entering commands, task dependencies, working directories, exit handling, and whether the documented operation reaches the intended command.

A finding must name the affected resource or operation, triggering condition, consequence, and supporting code/plan/rule. Treat scope changes or duplication as findings only when they violate a stated constraint or cause a demonstrated operational problem. Keep refactoring preferences separate.

## Verify and report

Use existing supplied plans and safe static checks when available. Inspect unfamiliar scripts first. Do not apply/destroy resources, mutate remote state, fetch credentials, or initialize providers/backends merely to complete the review. If a claim needs a plan, provider documentation, or environment state that is unavailable, label it unresolved rather than inventing the result.

Propose a focused correction, including migration ordering when relevant. Return the shared findings contract plus resources/environments examined, checks and observed outcomes, missing evidence, and provenance. No applicable infrastructure changes yields an explicit not-applicable result. Keep the review read-only and leave publication to `review-post`.
