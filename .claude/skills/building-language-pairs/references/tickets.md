# Ticket breakdown

Split a pair into five tickets. Each first slice is a tracer bullet: it runs the whole path for one skill on a narrow scope, so later tickets only widen it. Copy the acceptance criteria from the Go ticket named in each row, and change what is specific to the language. Add each item [gotchas.md](gotchas.md) marks as a criterion for that ticket.

| # | Ticket | Go ticket | Blocked by |
| --- | --- | --- | --- |
| 1 | `<lang>-practices`: first slice | #57 | none |
| 2 | `<lang>-practices`: remaining references | #58 | 1 |
| 3 | `<lang>-review`: first slice, from target to verdict | #59 | 1 |
| 4 | `<lang>-review`: remaining checklist areas | #60 | 2, 3 |
| 5 | Release the pair and remove any upstream plugin | #62 | 4 |

Merge order into the integration branch: 1, 2, 3, 4, 5. Tickets 2 and 3 can be built in parallel. Ticket 4 branches from 3 and merges 2 in.

When the grill, design step 4, decided that `<lang>-review` reads existing convention skills instead of a new practices skill, drop tickets 1 and 2. Ticket 3 is then blocked by nothing, and ticket 4 by 3 only. The examples module and its checker are not built. Ticket 3 takes over the CI toolchain install. Its fixture test needs it.

Go had a sixth ticket, #61, for the convention in CONTRIBUTING.md. A later language changes CONTRIBUTING.md only when it settles something new, such as the grill's answer on existing convention skills. A language's PRs never change CONTRIBUTING.md, because it is shared text. Put a change that design settles in the shared-text ticket from design step 4, which blocks the first ticket of the layout. A gap found during build gets a shared-text ticket of its own, filed by the ticket that finds it.

## What each ticket proves

1. **Practices first slice.** Two references: one ported from upstream with its audited defects fixed, and one written new for an area upstream lacks. With no upstream skill, both are written new. The examples module and its script test. The test runs the language's checks and matches every quoted block to its source. Only the examples the spec lists for those two references. The CI toolchain install. When the skill copies upstream material, add the upstream `LICENSE` and `NOTICE`.
2. **Remaining references.** Every other area in the checklist gets a reference, each quoting the examples module. Build only the examples the spec lists.
3. **Review first slice.** Target resolution, the temporary worktree, the safe-checks reference, the finding contract, and the verdict, applied to two areas. A seeded-defect fixture with one planted defect for each of those two areas, its `expected-findings.md`, and its script test.
4. **Remaining areas.** One step reference per remaining area, and one planted fixture defect per area.
5. **Release ticket.** When an upstream plugin exists, remove it from every catalog that lists it and from the bundled-plugin lists in `scripts/validate.py`. Update the README. When an upstream plugin was removed, add uninstall steps for it modelled on the `golang-pro` note. Bump the version in all three manifests. Run strict plugin validation, the behavior cases on both hosts, and the fixture review by hand. Leave out #62's last criterion, the merge to `main`. The main PR, opened after this ticket merges, does that.

## Writing each ticket

Each ticket has a `## Parent` line and a `## What to build` section saying what a user can do once it merges. Its `## Acceptance criteria` checklist is one a reviewer can check against the PR. The last criterion is that the checks in build step 8 pass. Every ticket says its work merges into `feat/<lang>-skills`.
