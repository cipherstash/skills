---
name: building-language-pairs
description: Builds a language's skill pair in this repository, `<lang>-practices` and `<lang>-review`, from its parent ticket through an audit, a ticket breakdown, a stack of draft PRs, and the PR to main. Use when starting or continuing the Python, TypeScript, Rust, or another language pair, when replacing a bundled upstream language plugin (`python-pro`, `typescript-pro`, `rust-engineer`), or when breaking a language ticket into buildable tickets. Not for changing one skill of an existing pair, which CONTRIBUTING.md covers.
---

# Building a language pair

This skill is the process. The rules a pair must meet live in the **Language skills** section of [CONTRIBUTING.md](../../../CONTRIBUTING.md#language-skills). Read that section before step 1, and check every change against it.

The Go pair is the worked example to copy: spec #56, tickets #57 to #62, PRs #70 to #75, and the skills `golang-practices` and `golang-review`. Go stacked each PR on the one before, and its PR to `main` was not open when this skill was written. Steps 6 and 11 are the intended flow, not yet a tested one.

The work has two phases with a person between them. **Design** turns a high-level language ticket, such as #64 for Python, into an audit and buildable tickets, then stops. Design may start on a parent ticket labelled `ready-for-human`, because it ends in a proposal for the person. **Build** turns approved tickets into a stack of draft PRs and a PR to `main`.

Two PRs carry the release. The **release ticket PR** is the last PR in the stack and merges into the integration branch. The **main PR** merges the integration branch into `main`.

## Inputs

- **The language** and its parent ticket. Without a ticket, ask which language and whether a ticket exists.
- **The upstream skill** the pair replaces, if any: the bundled plugin named in the README's **Bundled language practice skills** table.

## Resuming

Before step 1, look for work already done: a spec sub-issue under the parent, its tickets, a `feat/<lang>-skills` branch, and stacked PRs. Resume at the first step whose done condition is unmet.

## Tools by host

Where this skill names another skill, use it when the host has it. Otherwise do the step by hand as written:

- **`tdd`**: write a failing test, watch it fail, then write the code that passes it.
- **`code-review`**: check the diff against the ticket's acceptance criteria and CONTRIBUTING.md. Report each defect with its file, line, and severity.
- **`authoring-pull-requests`**, **`review-fix`**, **`review-audit`**, and **`run-report`** are company-skills skills. When company-skills is not installed, read `plugins/company-skills/skills/<name>/SKILL.md` in this repository and follow it.

## Unattended runs

When the person starts an unattended run of this skill, that approves commits and pushes to ticket branches and the integration branch. Tell `review-fix` so, since it otherwise asks first. It never approves a merge, a push to `main`, or marking a PR ready. Keep the log with the `run-report` skill. When a step needs a person, stop and report.

## Design

1. **Settle existing skills.** If the language already has convention skills in `plugins/company-skills/skills/`, ask the person to choose. Option one adds a `<lang>-practices` skill beside them. Option two builds no practices skill, and `<lang>-review` reads them as they are. For Rust this is #63's open question. Record the answer in the spec. Any CONTRIBUTING.md change it needs goes in the first ticket of the chosen layout. Done when the spec records the answer, or the language has no convention skills.

2. **Write the checklist.** Draft the review skill's areas table, modelled on the ten areas in `golang-review`'s SKILL.md. Give each area its priority and the tool that gives evidence for it. Go used `go vet`, `gofmt`, race-enabled tests with coverage, `govulncheck`, `go mod tidy -diff`, and an exported-API comparison. Name the language and runtime versions the references will target. Name the toolchain CI must install. Answer each open question in the parent ticket, or list it for the person. Done when every area names its evidence or says it has none. Every open question must have an answer or be on the list.

3. **Audit the upstream skill** against that checklist, at the `sha` pinned for it in `.claude-plugin/marketplace.json`. Read every reference, and build and run every example. Record each defect with its file, line, and checklist area. Record which areas upstream covers fully, partly, or not at all. With no upstream skill, record that and go to step 4. Done when you have read each upstream file and run each example, or recorded it as unbuildable.

4. **Write the spec and tickets.** Read [references/gotchas.md](references/gotchas.md) first: some of its items become ticket criteria. Write a spec issue shaped like #56, with the checklist and the full audit in it or in a comment on it. Split it into tickets using [references/tickets.md](references/tickets.md). File the spec as a sub-issue of the parent, and each ticket as a sub-issue of the spec, following `docs/agents/issue-tracker.md`. Set each ticket's blocked-by links from the tickets table, as that file's **Blocking** entry says. Label each `needs-triage`. Done when the spec and every ticket are filed, linked, and labelled.

5. **Stop for the person.** Post a comment on the parent ticket that links the spec and lists the tickets and the open questions. Ask the person to approve or change the tickets. Done when the person has labelled the tickets `ready-for-agent`. Build only those.

## Build

6. **Open the integration branch.** Create `feat/<lang>-skills` from the latest `origin/main` and push it. Every ticket PR stacks on it. Done when the branch is on `origin`.

7. **Build each ticket** in dependency order, with one branch and one draft PR per ticket. Base each branch on the branch of the ticket that blocks it. A ticket with two blockers branches from one and merges the other in. Start each ticket with `tdd`. Use the `authoring-pull-requests` skill for commits and the PR body, with two changes for a stack:
   - its `<base>` is the blocking ticket's branch, for both the signature range and the PR;
   - a stacked branch is never re-signed by rebase. If a commit needs a new signature, stop and report it.

   Run tickets with no dependency between them in parallel when the host has subagents. A ticket is done when the PR body marks each acceptance criterion met. An open criterion needs its reason in the body and a report to the person. Its checks must pass:
   - `python3 scripts/validate.py` and `python3 -m unittest discover -s scripts/tests`;
   - the `tests/` suite of each skill on the branch;
   - with Claude Code installed, `claude plugin validate . --strict`, and `claude plugin validate plugins/company-skills --strict`.

8. **Review each PR independently.** The author of a PR does not review it. A separate agent or session reviews it against its ticket with `code-review`. Without subagents, start a fresh session for the review. Then work the findings with `review-fix`, red first. When a person or bot review lands later, run `review-audit`, then `review-fix`. Done when no finding is open, or each open one is reported to the person with the reason.

9. **Merge fixes through the stack.** After any push to a branch, merge it into every branch that contains it, in stack order. Rerun the checks on each. Done when every branch that contains the fixed one has the fix and passes its checks.

10. **Test on both hosts.** Run both skills' behaviour cases in Claude Code and in Codex, and run the review skill against its seeded-defect fixture. Give the reviewing agent a copy of the change without the skill's `tests/` folder, so it cannot read the expected findings. Compare the fixture review with `expected-findings.md`. Check that each run lists the references and step files it read. Record the host, version, and observed result for each case in the release ticket PR body. Fix a trigger miss in the skill's `description`, and add a behaviour case only when none covers the request. Fix a wrong finding red first. A host you cannot run is reported to the person by name. Done when every case has a recorded result on both hosts, or the missing host is reported.

11. **Open the main PR.** After the person merges the stack into the integration branch, merge `origin/main` into it. Open the main PR from `feat/<lang>-skills` to `main`, and link the host results from the release ticket PR. Done when the main PR is open with its checks passing.

## Report

When pausing or finishing, tell the person:

- each PR, its place in the stack, its CI state, and its open findings;
- the merge order for the stack;
- what is waiting on them: approvals, reviews, merges, and host runs.
