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

When design step 1 decided that `<lang>-review` reads existing convention skills instead of a new practices skill, drop tickets 1 and 2. Ticket 3 is then blocked by nothing, and ticket 4 by 3 only. The examples module and its checker are not built. The language then has no check suite, since only a practices reference defines one. That is the Rust exemption in CONTRIBUTING.md's **Language skills** section, and design step 1's CONTRIBUTING.md change states the same for any other language. Ticket 3 takes over the CI toolchain install. Its fixture test needs it. Ticket 3 fetches no tools, because there is no pin to fetch at: it runs only tools already installed, and reports each check it cannot run as a limit of the review. Ticket 4 has no Repository standards step, because there is no suite to compare the repository's CI with.

Go had a sixth ticket, #61, for the convention in CONTRIBUTING.md. A later language changes CONTRIBUTING.md only when it settles something new, such as the answer to design step 1. Put a change that design settles in the first ticket of the layout. Put a change found during build in the ticket that finds it.

## What each ticket proves

1. **Practices first slice.** Two references: one ported from upstream with its audited defects fixed, and one written new for an area upstream lacks. With no upstream skill, both are written new. The examples module and its script test. The script test runs none of the suite's checks: it only matches every quoted block to its source, as CONTRIBUTING.md's **Language skills** section says. Only the examples the spec lists for those two references. The check suite, as design step 2 drafted it in the spec: the `references/checks.md` reference with its pinned-versions table, a CI job in the validate workflow that installs the toolchain and runs the suite over the examples, and the drift test under `scripts/tests/` that checks each suite check is in place in that job and pinned at the table's version. Go's are `golang-practices`' `references/checks.md`, the `go-check-suite` job, and `test_go_check_suite_workflow.py`. When the skill copies upstream material, add the upstream `LICENSE` and `NOTICE`.
2. **Remaining references.** Every other area in the checklist gets a reference, each quoting the examples module. Build only the examples the spec lists.
3. **Review first slice.** Target resolution, the temporary worktree, the safe-checks reference, the finding contract, and the verdict, applied to two areas. A seeded-defect fixture with one planted defect for each of those two areas, its `expected-findings.md`, and its script test. CI is the gate, so the review quotes CI's result for each suite check that CI ran on the reviewed head commit. For a check it runs itself, it fetches only a suite tool, at the version the practices skill pins, into `.<lang>-review-tools/` with install scripts off, as **The review skill** in [gotchas.md](gotchas.md) says. Its criteria name each file and flag of the execution surface that the spec lists, and say that the review runs nothing when the change touches one, until the user says yes.
4. **Remaining areas.** One step reference per remaining area, and one planted fixture defect per area. A Repository standards step compares the repository's CI with the check suite, as **The check suite in CI** in `golang-review`'s `references/checks.md` does for Go. A missing check is a line in the report, not a finding. A weakened check is a `major` finding. A missing untrusted-input test is a `minor` finding, for a function the change adds that parses or decodes untrusted input.
5. **Release ticket.** When an upstream plugin exists, remove it from every catalog that lists it and from the dependencies. Update the README. When an upstream plugin was removed, add uninstall steps for it modelled on the `golang-pro` note. Bump the version in all three manifests. Run strict plugin validation, the behavior cases on both hosts, and the fixture review by hand. Leave out #62's last criterion, the merge to `main`. The main PR, opened after this ticket merges, does that.

## Writing each ticket

Each ticket has a `## Parent` line and a `## What to build` section saying what a user can do once it merges. Its `## Acceptance criteria` checklist is one a reviewer can check against the PR. The last criterion is that the checks in build step 7 pass. Every ticket says its work merges into `feat/<lang>-skills`.
