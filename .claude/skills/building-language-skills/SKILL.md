---
name: building-language-skills
description: Builds a language's skills in this repository, `<lang>-practices`, `<lang>-review`, and the language's check suite, from its parent ticket through research, an audit, a grill, a ticket breakdown, a chain of draft PRs, and the PR to main. Use when starting or continuing the Python, TypeScript, Rust, or another language's skills, including requests worded as the "Python pair" or a "language pair", when replacing a bundled upstream language plugin (`python-pro`, `typescript-pro`, `rust-engineer`), or when breaking a language ticket into buildable tickets. Not for changing one skill of an existing language, which CONTRIBUTING.md covers.
---

# Building a language's skills

This skill is the process. The rules a language's skills must meet live in the **Language skills** section of [CONTRIBUTING.md](../../../CONTRIBUTING.md#language-skills). Read that section before step 1, and check every change against it.

The Go skills are the worked example to copy: spec #56, tickets #57 to #62, PRs #70 to #75, and the skills `golang-practices` and `golang-review`. Go based each PR on the branch of the one before. Its main PR is #102, opened from a working branch that held `feat/golang-skills` plus the merge of `origin/main`, because the agent could not push to the integration branch. Go's references and spec predate the examples-list and reference-length rules in CONTRIBUTING.md, so follow those rules, not Go's sizes.

The work has two phases with a person between them. **Design** turns a high-level language ticket, such as #64 for Python, into buildable tickets, then stops. On the way it researches the language, audits the upstream skill, and grills the person on the language's own decisions. Design may start on a parent ticket labelled `ready-for-human`, because it ends in a proposal for the person. **Build** turns approved tickets into a chain of draft PRs and a PR to `main`.

Two PRs carry the release. The **release ticket PR** is the last PR in the chain and merges into the integration branch. The **main PR** merges the integration branch into `main`.

## Inputs

- **The language** and its parent ticket. Without a ticket, ask which language and whether a ticket exists.
- **The upstream skill** the language's skills replace, if any: the bundled plugin named in the README's **Bundled language practice skills** table.

## Resuming

Before step 1, look for work already done. Read the parent ticket's comments: they hold the research report, the checklist, the audit, and the grill outcome from steps 1 to 4. They also list the shared tickets that steps 1 to 3 filed or linked. Build on them, and do not redo them.

Then look for a spec sub-issue under the parent, its tickets, a `feat/<lang>-skills` branch, and a chain of PRs. Resume at the first step whose done condition is unmet.

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

Every design step posts its result as a comment on the parent ticket, and this repository is public. Leave out the names of private repositories, and any security gap in CI that is not fixed yet. Do this before you post any comment or file any issue. When a result cannot be posted without them, stop and ask the person what to post.

1. **Research the language.** Read the parent ticket, the upstream skill, and the language's own documentation and tools. Write a report that lists the language's open decisions. Mark each one shared, when every language must answer it, or language-only. Sort each shared one as ADR 0003 says:
   - Check it against CONTRIBUTING.md **Language skills** and the ADRs in `docs/adr/`. If they settle it, mark it settled and cite the rule or ADR.
   - Otherwise, search the open issues for a ticket on it, as `filing-github-issues` does, and link the match. With no match, file the question as its own ticket. It never goes to this language's grill.

   If the language already has convention skills in `plugins/company-skills/skills/`, list one more language-only decision. Either add a `<lang>-practices` skill beside them, or build no practices skill and have `<lang>-review` read them as they are. For Rust this is #63's open question. Answer no open decision yourself: step 4 takes the language-only ones to the person. Done when:
   - the report is posted as a comment on the parent ticket;
   - each shared question that the rules and ADRs do not settle has its own ticket;
   - the comment lists the shared tickets this step filed or linked.

2. **Write the checklist and draft the check suite.** Draft the review skill's areas table, modelled on the ten areas in `golang-review`'s SKILL.md. Give each area its priority and the tool that gives evidence for it. Go used `go vet`, `gofmt`, race-enabled tests with coverage, `govulncheck`, `go mod tidy -diff`, and an exported-API comparison. You may add a review area beyond Go's ten under the rule in CONTRIBUTING.md's [Shared rules for every language](../../../CONTRIBUTING.md#shared-rules-for-every-language): a suite tool gives evidence for the area, and the review fixture can plant a defect in it. For each one you add, the spec records why. List the examples each area's reference needs: one per rule that prose cannot state, marked as upstream as is, upstream with a fix, or new. Name the minimum language and runtime versions the references will target.

   Name the toolchain CI must install for the language, under either option: ticket 1's CI job uses it, or ticket 3's fixture test under option two.

   Then draft the language's check suite, which ticket 1 builds. When the language already has convention skills, the grill in step 4 may pick option two. Then the spec skips the check suite draft, because the language has no check suite, as [references/tickets.md](references/tickets.md) says. Otherwise, follow the shared rules in that CONTRIBUTING.md section, and decide only what is the language's own. Go's draft is spec #87, and its result is `golang-practices`' `references/checks.md`. The draft names:
   - **Tools**: each check the suite runs, and the areas it gives evidence for.
   - **Pinned versions**: an exact pinned version for each tool, or the committed lockfile that CI installs frozen or locked.
   - **What floats**: the language runtime, which CI takes at its latest stable or LTS release, and anything else that floats by choice, such as the semgrep ruleset.
   - **Untrusted input**: the tool that tests a function that parses or decodes untrusted input, a fuzz target or a property test, and how pull request CI keeps its inputs fixed. If neither fits the language, say why neither fits.

   List the language's [execution surface](../../../GLOSSARY.md#language-skills): the files and flags through which a change runs its own code when the suite's tools build, lint, or test it. Examples are Python's `conftest.py`, Rust's `build.rs`, and Go's `-toolexec`. The review runs nothing when a change touches one, until the user says yes, so ticket 3's criteria name each entry, as [references/tickets.md](references/tickets.md) says.

   The spec records the areas table, the check suite draft, and the execution surface, as #87 did for Go's check suite. Do not answer open questions yourself. Add each one this step raises to step 1's list, and sort it as step 1 says. Done when:
   - every area names its evidence, or says it has none;
   - every area lists its examples, or says it needs none;
   - the check suite draft names each tool, its pinned version, what floats, and the untrusted-input test tool and how pull request CI keeps its inputs fixed, or why neither fits;
   - the spec names the CI toolchain;
   - the execution surface is listed;
   - each shared question this step raised is settled or has its own ticket;
   - the checklist, the check suite draft, and the execution surface are posted as a comment on the parent ticket, with the shared tickets this step filed or linked.

3. **Audit the upstream skill** against that checklist, at the `sha` pinned for it in `.claude-plugin/marketplace.json`. Read every reference, and build and run every example. Record each defect with its file, line, and checklist area. Record which areas upstream covers fully, partly, or not at all. Then update step 2's examples list. An upstream example with no defect stays as it is. One with a defect gets the smallest fix. Add each open question the audit raises to step 1's list, and sort it as step 1 says. With no upstream skill, post a comment on the parent ticket saying so, and go to step 4. Done when a comment on the parent ticket says there is no upstream skill, or when:
   - you have read each upstream file;
   - you have run each example, or recorded it as unbuildable;
   - each shared question the audit raised is settled or has its own ticket;
   - the audit is posted as a comment on the parent ticket, with the shared tickets this step filed or linked.

4. **Grill the person.** Start only once every shared ticket that steps 1 to 3 name is settled, whoever filed it, as ADR 0003 orders. Their comments on the parent ticket list those tickets. If any is still open, stop and report those tickets to the person. Use `grilling` to take the language-only decisions from steps 1 to 3 to the person. Ask one question at a time, each with your recommended answer. Ask nothing that CONTRIBUTING.md or an ADR already settles. The grill drafts only GLOSSARY entries and ADRs, and writes no code. GLOSSARY.md and the ADRs are shared text. A language's PRs never change shared text, as CONTRIBUTING.md **Pull requests** says. So write each draft in the body of one shared-text ticket, with any CONTRIBUTING.md change that design settles. The files are written when that ticket is built. The shared-text ticket blocks the first ticket of the language's layout. The grill ends when the person confirms shared understanding. A "yes" there is not a go-ahead to build. Building waits for tickets labelled `ready-for-agent`, as step 6 says. Done when:
   - the person has confirmed shared understanding;
   - the shared-text ticket is filed, if the grill drafted any ADR or GLOSSARY entry;
   - the grill outcome is posted as a comment on the parent ticket: each question, its answer, and the draft that records it.

5. **Write the spec and tickets.** Read [references/gotchas.md](references/gotchas.md) first: some of its items become ticket criteria. Write a spec issue shaped like #56, with the checklist and the full audit in it or in a comment on it. For each decision the grill settled, cite its draft in the shared-text ticket. Split the spec into tickets using [references/tickets.md](references/tickets.md). File the spec as a sub-issue of the parent, and each ticket as a sub-issue of the spec, following `docs/agents/issue-tracker.md`. Set each ticket's blocked-by links from the tickets table, as that file's **Blocking** entry says. If step 4 filed a shared-text ticket, block the layout's first ticket on it. Label each `needs-triage`. Done when the spec and every ticket are filed, linked, and labelled.

6. **Stop for the person.** Post a comment on the parent ticket. Link the spec, the grill outcome, and the shared tickets, and list the tickets. Ask the person to approve or change the tickets. Answer no new open question yourself. A new question goes back to step 1's list and is sorted as step 1 says. A language-only one goes to the grill, and a shared one to its own ticket. Done when the person has labelled the tickets `ready-for-agent`. Build only those.

## Build

7. **Open the integration branch.** Create `feat/<lang>-skills` from the latest `origin/main` and push it. Every chain of ticket PRs starts from it. Done when the branch is on `origin`.

8. **Build each ticket** in dependency order, with one branch and one draft PR per ticket. Base each branch on the branch of the ticket that blocks it. A ticket with two blockers branches from one and merges the other in. Start each ticket with `tdd`. Use the `authoring-pull-requests` skill for commits and the PR body, with two changes for a chain of pull requests. This is a chain, not a GitHub stack, so never run `gh stack` or follow stacking-pull-requests. The two changes:
   - its `<base>` is the blocking ticket's branch, for both the signature range and the PR;
   - a branch in the chain is never re-signed by rebase. If a commit needs a new signature, stop and report it.

   A ticket's PR changes only its own skill directories, its own CI job, and its own drift test, as the pull request rules in [CONTRIBUTING.md](../../../CONTRIBUTING.md#shared-rules-for-every-language) say, so other languages can build at the same time. It leaves shared files alone: CONTRIBUTING.md, GLOSSARY.md, this skill, the README, the catalogs, and the plugin manifests. A gap found in shared text gets its own ticket. It has two exceptions: the release ticket PR updates the README, the catalogs, and the company-skills dependencies, as [references/tickets.md](references/tickets.md) says. The main PR bumps the version, as step 12 says.

   Run tickets with no dependency between them in parallel when the host has subagents. A ticket is done when the PR body marks each acceptance criterion met. An open criterion needs its reason in the body and a report to the person. Its checks must pass:
   - `python3 scripts/validate.py` and `python3 -m unittest discover -s scripts/tests`;
   - the `tests/` suite of each skill on the branch;
   - with Claude Code installed, `claude plugin validate . --strict`, and `claude plugin validate plugins/company-skills --strict`.

9. **Review each PR independently.** The author of a PR does not review it. A separate agent or session reviews it against its ticket with `code-review`. Without subagents, start a fresh session for the review. Then work the findings with `review-fix`, red first. When a person or bot review lands later, run `review-audit`, then `review-fix`. Fix each finding as **Fix a PR's findings where the line was added, never on a later branch** in [references/gotchas.md](references/gotchas.md) says. Before a PR merges, each finding deferred from it is filed as an issue and linked from the PR body, so none is lost when the PR closes. Before the release ticket PR opens, also run a security review on the tip of the chain, as **The chain** in [references/gotchas.md](references/gotchas.md) explains. Done when no finding is open, or each open one is filed as an issue, linked from the PR body, and reported to the person with the reason.

10. **Merge fixes through the chain.** After any push to a branch, merge it into every branch based on it, in chain order. Rerun the checks on each. Fix each finding as **Fix a PR's findings where the line was added, never on a later branch** says. Check each PR's base branch right before it merges, as **The chain** in [references/gotchas.md](references/gotchas.md) says. Done when every branch based on the fixed one has the fix and passes its checks.

11. **Test on both hosts.** Run both skills' behavior cases in Claude Code and in Codex, and run the review skill against its seeded-defect fixture. Build the fixture repository from the fixture's `base/` and `head/` outside the plugin, as `expected-findings.md` says. Load the review skill from a scratch copy of the plugin with every skill's `tests/` folder removed, so the reviewer cannot read the expected findings. **Host testing** in [references/gotchas.md](references/gotchas.md) covers making that copy and other host problems. Compare the fixture review with `expected-findings.md`. Check that each run lists the references and step files it read. Record the host, version, and observed result for each case in the release ticket PR body. Fix a trigger miss in the skill's `description`, and add a behavior case only when none covers the request. Fix a wrong finding red first. A host you cannot run is reported to the person by name. Done when every case has a recorded result on both hosts, or the missing host is reported.

12. **Open the main PR.** After the person merges the chain into the integration branch, merge `origin/main` into it. If you cannot push to the integration branch, make a working branch from it and merge there, as Go did for #102. Then, after that merge, bump the version in all three manifests, as the pull request rules in [CONTRIBUTING.md](../../../CONTRIBUTING.md#shared-rules-for-every-language) say. Only the main PR bumps the version, as [Releases](../../../CONTRIBUTING.md#releases) says. Pick the next version after the one `main` has, so languages building at the same time do not collide. A gap in shared text gets its own ticket, as step 8 says. Run step 8's checks again. Open the main PR to `main` from `feat/<lang>-skills` or the working branch, and link the host results from the release ticket PR. Done when the main PR is open with its checks passing. Its diff bumps the version in all three manifests past the one `main` has.

13. **File what the run learned.** After the main PR opens, file one issue against the `building-language-skills` process skill. List the run's deviations from this skill, such as a skipped step, a retry, or a workaround, and its process findings: anything this skill, its gotchas, or CONTRIBUTING.md got wrong or left out. The issue is linked from the main PR body. That issue starts the next pass, as ADR 0003 says: a shared ticket fixes the shared text, and no language's PR does. Done when the issue is filed and the main PR body links it.

## Report

When pausing or finishing, tell the person:

- each PR, its place in the chain, its CI state, and its open findings;
- the merge order for the chain;
- each finding deferred from a PR, and the issue that records it;
- the issue from step 13 that lists the run's deviations and process findings, once the main PR is open;
- what is waiting on them: approvals, reviews, merges, and host runs.
