---
name: building-language-pairs
description: Builds a language's skill pair in this repository, `<lang>-practices` and `<lang>-review`, from its parent ticket through research, an audit, a grill, a ticket breakdown, a stack of draft PRs, and the PR to main. Use when starting or continuing the Python, TypeScript, Rust, or another language pair, when replacing a bundled upstream language plugin (`python-pro`, `typescript-pro`, `rust-engineer`), or when breaking a language ticket into buildable tickets. Not for changing one skill of an existing pair, which CONTRIBUTING.md covers.
---

# Building a language pair

This skill is the process. The rules a pair must meet live in the **Language skills** section of [CONTRIBUTING.md](../../../CONTRIBUTING.md#language-skills). Read that section before step 1, and check every change against it.

The Go pair is the worked example to copy: spec #56, tickets #57 to #62, PRs #70 to #75, and the skills `golang-practices` and `golang-review`. Go stacked each PR on the one before. Its main PR is #102, opened from a working branch that held `feat/golang-skills` plus the merge of `origin/main`, because the agent could not push to the integration branch. Go's references and spec predate the examples-list and reference-length rules in CONTRIBUTING.md, so follow those rules, not Go's sizes.

The work has two phases with a person between them. **Design** turns a high-level language ticket, such as #64 for Python, into research, an audit, a grill with the person on the language's own decisions, and buildable tickets, then stops. Design may start on a parent ticket labelled `ready-for-human`, because it ends in a proposal for the person. **Build** turns approved tickets into a stack of draft PRs and a PR to `main`.

Two PRs carry the release. The **release ticket PR** is the last PR in the stack and merges into the integration branch. The **main PR** merges the integration branch into `main`.

## Inputs

- **The language** and its parent ticket. Without a ticket, ask which language and whether a ticket exists.
- **The upstream skill** the pair replaces, if any: the bundled plugin named in the README's **Bundled language practice skills** table.

## Resuming

Before step 1, look for work already done. Read the parent ticket's comments: they hold the research report, the checklist, the audit, and the grill outcome from steps 1 to 4. Build on them, and do not redo them. Then look for a spec sub-issue under the parent, its tickets, a `feat/<lang>-skills` branch, and stacked PRs. Resume at the first step whose done condition is unmet.

## Tools by host

Where this skill names another skill, use it when the host has it. Otherwise do the step by hand as written:

- **`tdd`**: write a failing test, watch it fail, then write the code that passes it.
- **`grilling`**: ask the person one question at a time, each with your recommended answer, until they confirm shared understanding.
- **`code-review`**: check the diff against the ticket's acceptance criteria and CONTRIBUTING.md. Report each defect with its file, line, and severity.
- **`authoring-pull-requests`**, **`review-fix`**, **`review-audit`**, and **`run-report`** ship in company-skills. When company-skills is not installed, read `plugins/company-skills/skills/<name>/SKILL.md` in this repository and follow it.

## Unattended runs

When the person starts an unattended run of this skill, that approves commits and pushes to ticket branches and the integration branch. Tell `review-fix` so, since it otherwise asks first. Local `git merge`s into ticket branches and the integration branch are approved too. It never approves merging a PR on GitHub, a push to `main`, or marking a PR ready.

Keep the log with the `run-report` skill. When a step needs a person, stop and report.

## Design

1. **Research the language.** Read the parent ticket, the upstream skill, and the language's own documentation and tools. Write a report that lists the language's open decisions. Mark each one shared, when every language must answer it, or language-only. Check each shared one against CONTRIBUTING.md **Language skills** and the ADRs in `docs/adr/` first: if they settle it, mark it settled and cite the rule or ADR. A shared question they do not settle goes to its own ticket, not to this language's grill, as ADR 0003 says. If the language already has convention skills in `plugins/company-skills/skills/`, list as a language-only decision whether to add a `<lang>-practices` skill beside them, or to build no practices skill and have `<lang>-review` read them as they are. For Rust this is #63's open question. Answer no open decision yourself: step 4 takes them to the person. Done when the report is posted as a comment on the parent ticket, and each shared question it does not settle has its own ticket.

2. **Write the checklist.** Draft the review skill's areas table, modelled on the ten areas in `golang-review`'s SKILL.md. Give each area its priority and the tool that gives evidence for it. Go used `go vet`, `gofmt`, race-enabled tests with coverage, `govulncheck`, `go mod tidy -diff`, and an exported-API comparison. List the examples each area's reference needs: one per rule that prose cannot state, marked as upstream as is, upstream with a fix, or new. Name the language and runtime versions the references will target. Name the toolchain CI must install. Do not answer open questions yourself. Add each one this step raises to step 1's list, marked shared or language-only. Check each new shared one against CONTRIBUTING.md **Language skills** and the ADRs as step 1 does, and file one they do not settle as its own ticket. Only language-only questions go to the grill. Done when every area names its evidence or says it has none, and lists its examples or says it needs none, each shared question this step raised is settled or has its own ticket, and the checklist is posted as a comment on the parent ticket.

3. **Audit the upstream skill** against that checklist, at the `sha` pinned for it in `.claude-plugin/marketplace.json`. Read every reference, and build and run every example. Record each defect with its file, line, and checklist area. Record which areas upstream covers fully, partly, or not at all. Then update step 2's examples list: an upstream example with no defect stays as it is, and one with a defect gets the smallest fix. Add each open question the audit raises to step 1's list as step 2 does: a shared one that CONTRIBUTING.md and the ADRs do not settle gets its own ticket. Only language-only questions go to the grill. With no upstream skill, record that and go to step 4. Done when you have read each upstream file and run each example, or recorded it as unbuildable, each shared question the audit raised is settled or has its own ticket, and the audit is posted as a comment on the parent ticket.

4. **Grill the person.** Start only once every shared ticket filed in steps 1 to 3 is settled, as ADR 0003 orders. If any is still open, stop and report those tickets to the person. Use `grilling` to take the language-only decisions from steps 1 to 3 to the person, one question at a time, each with your recommended answer. Ask nothing that CONTRIBUTING.md or an ADR already settles. The grill writes only GLOSSARY entries and ADRs, and writes no code. Each decision becomes an ADR in `docs/adr/` or a GLOSSARY entry. These are shared text, which a language's PRs never change, as CONTRIBUTING.md **Pull requests** says. So file them, with any CONTRIBUTING.md change design settles, as one shared-text ticket of their own, which blocks the first ticket of the language's layout. The spec cites them. The grill ends when the person confirms shared understanding. A "yes" there is not a go-ahead to build: building waits for tickets labelled `ready-for-agent`, as step 6 says. Done when the person has confirmed shared understanding, the shared-text ticket is filed if the grill wrote any ADR or GLOSSARY entry, and the grill outcome is posted as a comment on the parent ticket: each question, its answer, and the ADR or GLOSSARY entry that records it.

5. **Write the spec and tickets.** Read [references/gotchas.md](references/gotchas.md) first: some of its items become ticket criteria. Write a spec issue shaped like #56, with the checklist and the full audit in it or in a comment on it. Cite the grill's ADRs and GLOSSARY entries for each decision it settled. Split it into tickets using [references/tickets.md](references/tickets.md). File the spec as a sub-issue of the parent, and each ticket as a sub-issue of the spec, following `docs/agents/issue-tracker.md`. Set each ticket's blocked-by links from the tickets table, as that file's **Blocking** entry says, and block the layout's first ticket on step 4's shared-text ticket. Label each `needs-triage`. Done when the spec and every ticket are filed, linked, and labelled.

6. **Stop for the person.** Post a comment on the parent ticket that links the spec and lists the tickets and the open questions. Ask the person to approve or change the tickets. Done when the person has labelled the tickets `ready-for-agent`. Build only those.

## Build

7. **Open the integration branch.** Create `feat/<lang>-skills` from the latest `origin/main` and push it. Every ticket PR stacks on it. Done when the branch is on `origin`.

8. **Build each ticket** in dependency order, with one branch and one draft PR per ticket. Base each branch on the branch of the ticket that blocks it. A ticket with two blockers branches from one and merges the other in. Start each ticket with `tdd`. Use the `authoring-pull-requests` skill for commits and the PR body, with two changes for a stack:
   - its `<base>` is the blocking ticket's branch, for both the signature range and the PR;
   - a stacked branch is never re-signed by rebase. If a commit needs a new signature, stop and report it.

   Run tickets with no dependency between them in parallel when the host has subagents. A ticket is done when the PR body marks each acceptance criterion met. An open criterion needs its reason in the body and a report to the person. Its checks must pass:
   - `python3 scripts/validate.py` and `python3 -m unittest discover -s scripts/tests`;
   - the `tests/` suite of each skill on the branch;
   - with Claude Code installed, `claude plugin validate . --strict`, and `claude plugin validate plugins/company-skills --strict`.

9. **Review each PR independently.** The author of a PR does not review it. A separate agent or session reviews it against its ticket with `code-review`. Without subagents, start a fresh session for the review. Then work the findings with `review-fix`, red first. When a person or bot review lands later, run `review-audit`, then `review-fix`. Before the release ticket PR opens, also run a security review on the tip of the stack, as **The stack** in [references/gotchas.md](references/gotchas.md) explains. Done when no finding is open, or each open one is reported to the person with the reason.

10. **Merge fixes through the stack.** After any push to a branch, merge it into every branch stacked on it, in stack order. Rerun the checks on each. Fix each line on the branch that added it, and check each PR's base branch right before it merges, as **The stack** in [references/gotchas.md](references/gotchas.md) says. Done when every branch stacked on the fixed one has the fix and passes its checks.

11. **Test on both hosts.** Run both skills' behavior cases in Claude Code and in Codex, and run the review skill against its seeded-defect fixture. Build the fixture repository from the fixture's `base/` and `head/` outside the plugin, as `expected-findings.md` says. Load the review skill from a scratch copy of the plugin with every skill's `tests/` folder removed, so the reviewer cannot read the expected findings. **Host testing** in [references/gotchas.md](references/gotchas.md) covers making that copy and other host problems. Compare the fixture review with `expected-findings.md`. Check that each run lists the references and step files it read. Record the host, version, and observed result for each case in the release ticket PR body. Fix a trigger miss in the skill's `description`, and add a behavior case only when none covers the request. Fix a wrong finding red first. A host you cannot run is reported to the person by name. Done when every case has a recorded result on both hosts, or the missing host is reported.

12. **Open the main PR.** After the person merges the stack into the integration branch, merge `origin/main` into it. Open the main PR from `feat/<lang>-skills` to `main`, and link the host results from the release ticket PR. Done when the main PR is open with its checks passing.

## Report

When pausing or finishing, tell the person:

- each PR, its place in the stack, its CI state, and its open findings;
- the merge order for the stack;
- what is waiting on them: approvals, reviews, merges, and host runs.
