---
name: building-language-pairs
description: Builds a language's skill pair in this repository, `<lang>-practices` and `<lang>-review`, from its parent ticket through an audit, a ticket breakdown, a stack of draft PRs, and the PR to main. Use when starting or continuing the Python, TypeScript, Rust, or another language pair, or when breaking a language ticket into buildable tickets. Not for changing one skill of an existing pair, which CONTRIBUTING.md covers.
---

# Building a language pair

This skill is the process. The rules a pair must meet live in the **Language skills** section of [CONTRIBUTING.md](../../../CONTRIBUTING.md#language-skills). Read that section before step 1, and check every change against it.

The Go pair is the worked example to copy: spec #56, tickets #57 to #62, PRs #70 to #75, and the skills `golang-practices` and `golang-review`. Go stacked each PR on the one before, and its PR to `main` was not open when this skill was written. Steps 6 and 11 are the intended flow, not yet a tested one.

The work has two phases with a person between them. **Design** turns a high-level language ticket, such as #64 for Python, into an audit and buildable tickets, then stops. **Build** turns approved tickets into a stack of draft PRs and a PR to `main`.

Two PRs carry the release. The **release ticket PR** is the last PR in the stack and merges into the integration branch. The **main PR** merges the integration branch into `main`.

## Inputs

- **The language** and its parent ticket. Without a ticket, ask which language and whether a ticket exists.
- **The upstream skill** the pair replaces, if any: the bundled plugin named in the README's **Bundled language practice skills** table.

## Tools by host

Where this skill names another skill, use it when the host has it. Otherwise do the step by hand as written:

- **`tdd`**: write a failing test, watch it fail, then write the code that passes it.
- **`code-review`**: check the diff against the ticket's acceptance criteria and CONTRIBUTING.md. Report each defect with its file, line, and severity.
- **`review-fix`** and **`review-audit`** ship in company-skills, so every host has them.

## Design

1. **Settle existing skills.** If the language already has convention skills in `plugins/company-skills/skills/`, ask the person to choose. Option one adds a `<lang>-practices` skill beside them. Option two builds no practices skill, and `<lang>-review` reads them as they are. For Rust this is #63's open question. The current exemption in CONTRIBUTING.md ends when `rust-practices` exists. Record the answer in the spec. The CONTRIBUTING.md change it needs goes in a ticket. Done when the spec records the answer, or the language has no convention skills.

2. **Write the checklist.** Draft the review skill's areas table, modelled on the ten areas in `golang-review`'s SKILL.md. Give each area its priority and the tool that gives evidence for it. Go used `go vet`, `gofmt`, race-enabled tests with coverage, `govulncheck`, `go mod tidy -diff`, and an exported-API comparison. Name the language version the references will target. Name the toolchain CI must install. Done when every area names its evidence or says it has none.

3. **Audit the upstream skill** against that checklist. Read every reference, and build and run every example. Done when you have read each upstream file and run each example, or recorded it as unbuildable. Record each defect with its file, line, and checklist area. Record which areas upstream covers fully, partly, or not at all.

4. **Write the spec and tickets.** Write a spec issue shaped like #56 and split it into tickets using [references/tickets.md](references/tickets.md). File the spec as a sub-issue of the parent, and each ticket as a sub-issue of the spec, following `docs/agents/issue-tracker.md`. Label each `needs-triage`. Done when the spec and every ticket are filed, linked, and labelled.

5. **Stop for the person.** Post the audit, the checklist, and the ticket list, and ask them to approve or change the tickets. Done when the person has labelled the tickets `ready-for-agent`. Build only those.

## Build

Before step 6, read [references/gotchas.md](references/gotchas.md). That file lists problems the Go run hit.

6. **Open the integration branch.** Create `feat/<lang>-skills` from the latest `origin/main` and push it. Every ticket PR stacks on it. Done when the branch is on `origin`.

7. **Build each ticket** in dependency order, with one branch and one draft PR per ticket. Base each branch on the branch of the ticket that blocks it. A ticket with two blockers branches from one and merges the other in. Start each ticket with `tdd`. Use the `authoring-pull-requests` skill for commits and the PR body. List in the body which acceptance criteria are met. Run tickets with no dependency between them in parallel when the host has subagents. A ticket is done when the PR body marks every acceptance criterion met or open. Its checks must pass: `python3 scripts/validate.py`, `python3 -m unittest discover -s scripts/tests`, and the `tests/` suite of each skill on the branch.

8. **Review each PR independently.** The author of a PR does not review it. A separate agent or session reviews it against its ticket with `code-review`. Without subagents, start a fresh session for the review. Then work the findings with `review-fix`, red first. When a person or bot review lands later, run `review-audit`, then `review-fix`. Done when no finding is open, or each open one is reported to the person with the reason.

9. **Merge fixes through the stack.** After any push to a branch, merge it into every branch that contains it, in stack order. Rerun the checks on each. Done when every branch that contains the fixed one has the fix and passes its checks.

10. **Test on both hosts.** Run both skills' behaviour cases in Claude Code and in Codex, and run the review skill against its seeded-defect fixture. Compare the fixture review with `expected-findings.md`. Record the host, version, and observed result for each case in the release ticket PR body. A trigger miss or a wrong finding becomes a behaviour case and a fix, red first. A host you cannot run is reported to the person by name. Done when every case has a recorded result on both hosts, or the missing host is reported.

11. **Open the main PR.** After the person merges the stack into the integration branch, merge `origin/main` into it. Open the main PR from `feat/<lang>-skills` to `main`, and link the host results from the release ticket PR. Done when the main PR is open with its checks passing.

## Report

When pausing or finishing, tell the person:

- each PR, its place in the stack, its CI state, and its open findings;
- the merge order for the stack;
- what is waiting on them: approvals, reviews, merges, and host runs.

For an unattended run, keep the log with the `run-report` skill.
