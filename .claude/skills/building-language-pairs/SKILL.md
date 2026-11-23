---
name: building-language-pairs
description: Builds a language's skill pair in this repository, `<lang>-practices` and `<lang>-review`, from its parent ticket through an audit, a ticket breakdown, a stack of draft PRs, and the release PR. Use when starting or continuing the Python, TypeScript, Rust, or another language pair, or when breaking a language ticket into buildable tickets. Not for changing one skill of an existing pair, which CONTRIBUTING.md covers.
---

# Building a language pair

This skill is the process. The rules a pair must meet live in the **Language skills** section of [CONTRIBUTING.md](../../../CONTRIBUTING.md#language-skills). Read that section before step 1, and check every change against it. The Go pair is the worked example to copy: spec #56, tickets #57 to #62, PRs #70 to #75, and the skills `golang-practices` and `golang-review`.

The work has two phases with a person between them. **Design** turns a high-level language ticket, such as #64 for Python, into an audit and buildable tickets, then stops. **Build** turns approved tickets into a stack of draft PRs and a release.

## Inputs

- **The language** and its parent ticket. Without a ticket, ask which language and whether a ticket exists.
- **The upstream skill** the pair replaces, if any: the bundled plugin named in the README's **Bundled language practice skills** table.

## Design

1. **Settle existing skills.** If the language already has convention skills in `plugins/company-skills/skills/`, ask the person whether they must meet the practices-skill rules, the way Rust was exempted. Record the answer in CONTRIBUTING.md. Done when CONTRIBUTING.md says how the review skill treats them, or the language has none.

2. **Write the checklist.** Draft the review skill's areas table, modelled on the ten areas in `golang-review`'s SKILL.md. Give each area its priority and the tool that gives evidence for it. Go used `go vet`, `gofmt`, race-enabled tests with coverage, `govulncheck`, `go mod tidy -diff`, and an exported-API comparison. Name the language version the references will target. Name the toolchain CI must install. Done when every area names its evidence or says it has none.

3. **Audit the upstream skill** against that checklist. Read every reference, and build and run every example. Done when you have read each upstream file and run each example, or recorded it as unbuildable. Record each defect with its file, line, and checklist area. Record which areas upstream covers fully, partly, or not at all.

4. **Write the spec and tickets.** Write a spec issue shaped like #56 and split it into tickets using [references/tickets.md](references/tickets.md). File them as sub-issues of the parent with the `needs-triage` label, following `docs/agents/issue-tracker.md`.

5. **Stop for the person.** Post the audit, the checklist, and the ticket list, and ask them to approve or change the tickets. Build starts only on tickets the person has labelled `ready-for-agent`.

## Build

Before step 6, read [references/gotchas.md](references/gotchas.md). That file lists problems the Go run hit that no other file in the repository states.

6. **Open the integration branch.** Create `feat/<lang>-skills` from the latest `origin/main`. Every ticket PR stacks on it; only the release PR targets `main`.

7. **Build each ticket** in dependency order, with one branch and one draft PR per ticket. Base each branch on the branch of the ticket that blocks it. Start each with the `tdd` skill: a failing test first, then the code. Use the `authoring-pull-requests` skill for commits and the PR body, and list in the body which acceptance criteria are met. Run tickets with no dependency between them in parallel when the host has subagents. A ticket is done when the PR body marks every acceptance criterion met or open. Its checks must pass: `python3 scripts/validate.py`, `python3 -m unittest discover -s scripts/tests`, and both skills' `tests/` suites.

8. **Review each PR independently.** The author of a PR does not review it. A separate agent or session reviews it against its ticket with the `code-review` skill. Then work the findings with `review-fix`, red first. When a person or bot review lands later, run `review-audit`, then `review-fix`. Done when no finding is open, or each open one is reported to the person with the reason.

9. **Merge fixes through the stack.** After any push to a lower branch, merge it into every branch above, in stack order, and rerun the checks on each. Done when every branch in the stack contains the fix and its checks pass.

10. **Test on both hosts.** Run both skills' behaviour cases in Claude Code and in Codex, and run the review skill against its seeded-defect fixture. Compare the fixture review with `expected-findings.md`. Record the host, version, and observed result for each case in the release PR body. A trigger miss or a wrong finding becomes a behaviour case and a fix, red first. A host you cannot run is reported to the person by name. Done when every case has a recorded result on both hosts, or the missing host is reported.

11. **Release.** After the person merges the stack into the integration branch, merge `origin/main` into it and open the PR from `feat/<lang>-skills` to `main`.

## Report

When pausing or finishing, tell the person:

- each PR, its place in the stack, its CI state, and its open findings;
- the merge order for the stack;
- what is waiting on them: approvals, reviews, merges, and host runs.

For an unattended run, keep the log with the `run-report` skill.
