# Contributing skills

Add skills under `plugins/company-skills/skills/<skill-name>/`. The directory is the single source published to Codex and Claude Code.

A skill for working on this repository itself, such as `building-language-pairs`, goes in `.claude/skills/` instead. It is not published, the validator does not check it, and it needs no behavior cases. AGENTS.md points to it, so Codex can follow it too.

A multi-agent workflow script for working on this repository goes in `.claude/workflows/`. A workflow runs in Claude Code only, through the Workflow tool, and is not published. `implement-tickets` builds a spec's `ready-for-agent` tickets into stacked draft PRs, then reviews and fixes each PR and writes a run report.

Start `implement-tickets` with `/implement-tickets <spec number>`, or `/implement-tickets <spec number> plan` to see the plan first. The project skill `.claude/skills/implement-tickets` turns those arguments into the workflow's `args`, and only a person can start it. You can also ask for the workflow by name with `{spec: <issue number>}`. The comment at the top of the script lists its other arguments.

## Skill skeleton

Start each skill from this `plugins/company-skills/skills/<skill-name>/SKILL.md`:

```markdown
---
name: skill-name
description: Describes what the skill does and the requests that should activate it.
---

Write the instructions the agent should follow.
```

## Authoring contract

- Give each skill one recognizable user goal. Split workflows with different triggers, inputs, or success criteria.
- Name the directory and frontmatter `name` identically. Use 1–64 lowercase ASCII letters, digits, and single hyphens, with no leading or trailing hyphen. Do not use the reserved words `anthropic` or `claude`. Prefer a specific gerund or noun phrase (`processing-pdfs`, `pdf-processing`) over vague names such as `helper` or `utils`.
- Group related skills under a shared domain prefix followed by a verb or topic: `rust-testing`, `vanta-triage`, `review-fix`. Group by what the skills are about, not where they run — the `review-` skills are about a code review's findings, and one of them works without a pull request, so they are not `pr-`. A review skill for one language is about that language, so it takes the language prefix, such as `golang-review` (see [Language skills](#language-skills)). Choose verbs for what the skill actually does: `review-fix` fixes findings, and does not reply to or resolve threads, so it is not "address".
- Write a non-empty `description` of at most 1,024 characters, in the third person and without XML tags, that says what the skill does and when it should activate. Include a boundary when a nearby request should not activate it.
- Write imperative steps with explicit inputs, outputs, decision points, and stopping conditions. Preserve explicit user instructions and authorization boundaries.
- Keep `SKILL.md` concise—preferably below 500 lines—and move branch-specific detail into focused files under `references/`. Link each reference directly from `SKILL.md`, keep references one level deep, and state when to read each one. Start any reference longer than 100 lines with a table of contents. Use forward-slash relative paths.
- Add `scripts/` only for deterministic or repeated mechanics. Document inputs, outputs, dependencies, and failure behavior, then execute tests for every changed script.
- Put generated-output templates and other copied resources in `assets/`.
- Add `agents/openai.yaml` only when the skill needs Codex UI metadata, explicit-only invocation, or declared tool dependencies.

## Convention skills

Most skills here are workflows: a user asks for a result and the skill runs a procedure. A **convention skill** instead carries coding rules the agent applies while it writes code (for example `rust-sdk-dx`). Author one like this:

- Write the `description` as what the conventions cover, then `Use when …` naming the files or changes they apply to, then the nearest work they do not apply to (other languages, binaries, a sibling convention skill). The boundary is load-bearing: the plugin installs at user scope, so a loose description fires in every project.
- Set `user-invocable: false` in the frontmatter so Claude Code applies the skill automatically and keeps it out of the `/` menu. Codex has no equivalent setting and invokes skills implicitly by default, so no `agents/openai.yaml` is needed.
- Keep rules company-wide. Name a repository's own helpers, paths, task runner commands, or ticket numbers only as clearly labelled examples, and leave repository-specific rules in that repository as a small local skill that points here.
- When two convention skills touch the same topic, one owns it and the other links to it by name instead of restating it.
- Name the library versions an API example targets, so a reader on another version knows the advice may not compile.
- Behavior cases still apply. "Should activate" lists change requests the rules govern rather than requests that name the skill, and the incomplete case covers a vague request in a matching codebase.

## Language skills

A programming language gets a pair of skills with the language as the shared prefix: `<lang>-practices` and `<lang>-review`. `<lang>` is the language's lowercase name, never an abbreviation: `golang` for Go, then `python`, `typescript`, or `rust`. Copy the layout of the Go pair, `golang-practices` with `golang-review`, for the next language. The Go pair is the worked example.

To build a new pair, follow the [`building-language-pairs`](.claude/skills/building-language-pairs/SKILL.md) project skill. It takes a language ticket through an audit and tickets to the main PR.

Rust already has convention skills: `rust-sdk-dx`, `rust-security`, and `rust-testing`. Rust is exempt from the practices-skill rules below for now. A `rust-review` skill may read those three as they are, with no check suite, `examples/` module, script test, or short `SKILL.md`. The exemption ends when a `rust-practices` skill is added.

Any other language that already has convention skills needs a decision like this before you build its pair.

- Name the review skill `<lang>-review`, not `review-<lang>`. This guide groups skills by what they are about. A language review is about the language. The `review-` prefix stays reserved for skills that work on a review's findings, such as `review-fix` and `review-post`.
- Put all knowledge about the language in the practices skill. The practices skill is a convention skill, so the rules above apply to it.
- Put only the review procedure in the review skill: its steps, the tools it runs, what counts as a finding, and the report format. Where both skills cover a topic, the practices skill states the rule. The review skill names the practices reference to read. The review skill may restate a rule that decides what is a finding, such as a minimum language version. Keep that copy the same as the practices reference.
- In the review skill, invoke the practices skill by name to read its references. Loading it gives its directory, and its reference paths resolve from there. No file the review skill reads during a review may link to or read `../<lang>-practices/`. Its tests may read the practices skill, to check that the two skills agree. The validator rejects a Markdown link in `SKILL.md` that leaves the skill directory. The validator does not check other files or plain-text paths, so check those by hand.
- If the practices skill cannot be loaded, the review carries on with its own steps. The report lists each reference it could not read as a limit of the review.
- Keep the practices skill's `SKILL.md` safe to load during a review. Give it a short rule list and a table saying when to read each reference. Leave out any authoring workflow, output template, or persona.
- Every language pair defines a check suite (see [GLOSSARY.md](GLOSSARY.md)): the checks that gate every pull request, run in CI. Define it in one practices reference, with every tool version pinned. Other references and both skills link to it instead of repeating its commands. The Go pair's is `golang-practices`' [checks.md](plugins/company-skills/skills/golang-practices/references/checks.md).
- Keep reference examples as real source that CI builds and tests. Put them in a small module under the practices skill's `examples/`, with tests. Quote each code block in a reference word for word from that source, with a link to the file on the line before it.
- Keep each example to the smallest code that shows one rule the reference states. Where prose can state the rule, write no code. Add no features, error paths, or tests beyond what shows the example works. The pair's spec is the issue filed under the language's ticket, such as #56 for Go. It lists the examples each reference needs, and a reviewer flags any example not on that list.
- Aim to keep each reference under 100 lines. The spec names any reference planned to run longer, and why.
- The examples-list and reference-length rules start with the next pair. Go's references and spec #56 predate them, so do not copy Go's sizes.
- Run the language's check suite over the examples in CI, in the validate workflow. Add a workflow test under `scripts/tests/` that checks each suite check is in place there and that its pinned version matches the reference.
- Add a script test to the practices skill that checks every quoted block matches its source. It runs none of the suite's checks. golang-practices' test also runs each benchmark once, because benchmarks are not a suite check. CI runs it with the other skill script tests.
- State in each reference the language version its examples target.
- Include a seeded-defect fixture in the review skill, under `tests/fixtures/`. The fixture is a small change, as `base/` and `head/` trees, with at least one planted defect for each area the skill covers. The fixture's `expected-findings.md` lists the findings a correct review must report.
- Add a script test to the review skill that checks the fixture. The test checks that the base is clean, that each defect comes from the change, and that the tools catch what they should. Where no tool shows a defect, add a probe test to a temporary copy of the module. The fixture stays unchanged. The test also checks that each expected location quotes its line. Run the review against the fixture by hand, as [Behavior cases](#behavior-cases) says.
- Report each finding with a severity of `critical`, `major`, or `minor`. Those are the values `review-cross-check`, `review-post`, and `review-fix` take unchanged. Copy their meanings from the [Finding contract](plugins/company-skills/skills/golang-review/SKILL.md#finding-contract) in `golang-review`. Change only the Go-specific examples. Do not paraphrase them.
- End the review report with a verdict of `APPROVE` or `REQUEST_CHANGES`. The verdict stays in the report: the review skill never submits an approving or blocking review on GitHub.
- Keep the review skill read-only. `review-fix` fixes findings and `review-post` posts them, so the review skill does neither. Write the review steps to run in sequence, so the skill works on hosts without subagents.
- Run the checks in a temporary worktree. The checkout must run none of the change. The review must remove the worktree on every exit. The review must never remove the records of the user's other worktrees. Copy the steps from `golang-review`'s [target.md](plugins/company-skills/skills/golang-review/references/target.md#the-temporary-worktree).
- Read all the changed code the tests will run before you run them. If that code does more than the change needs, record the tests as not run and say why. Copy the steps from `golang-review`'s [checks.md](plugins/company-skills/skills/golang-review/references/checks.md#before-running-tests).

### Taking in upstream material

A language pair often starts from an upstream skill. Take its material in like this:

- Audit it first: read it against the language's review checklist, and build and run its examples where you can. Record each defect you find. The checklist is the areas table in the review skill. For a new language, write that table first. Model it on the ten areas in `golang-review`.
- Copy it under its licence. Put the licence text in the skill's `LICENSE`. Put a `NOTICE` beside it that names the source repository, path, and commit, and lists every change. `plain-language` follows the same pattern.
- Fix every defect the audit found before the copy merges, each with the smallest change that fixes it. Keep upstream material that has no defect as it is. Rewrite or drop confused or dated rules.
- Drop the upstream frontmatter metadata, persona line, and links to skills that do not exist here.
- If company-skills installs the upstream skill as a dependency, the new `<lang>-practices` replaces it. The README lists these under **Bundled language practice skills**. The release ticket PR is the last of the stacked PRs that build the pair. It drops the upstream plugin from every catalog that lists it and from the company-skills dependencies. That PR also tells users how to uninstall the old plugin. The validator rejects any entry in either catalog, other than company-skills, that is not a dependency. The only exceptions are the Claude catalog's opt-in plugins, listed in `CLAUDE_OPT_IN_PLUGINS` in `scripts/validate.py`.

## Behavior cases

Every skill must include `tests/prompts.md` with these sections:

```markdown
# Behavior cases

## Should activate

- A direct request that should select the skill.
- An indirect request expressing the same goal.
- An incomplete request that should trigger a clarifying question.

## Should not activate

- A nearby but out-of-scope request.

## Expected behavior

- An observable end-to-end result, including important edge cases and facts the agent must not invent.
```

Use the cases for forward testing; they are evaluation inputs, not exact-output snapshots. Nothing in CI runs an agent, so run an agent against the cases by hand.

## Codex compatibility

Keep the shared workflow usable with the host's available tools. If a workflow delegates, describe a sequential fallback for hosts without subagents. Resolve bundled scripts and references from the installed skill directory, since the working directory is usually the user's project.

Skills activate automatically by default: write a description precise enough to trigger implicitly rather than making a skill explicit-only. Explicit-only is reserved for deprecated aliases (see [Renaming a skill](#renaming-a-skill)), which would otherwise compete with the skill they point to. For those, set `policy.allow_implicit_invocation: false` in the skill's `agents/openai.yaml`, and keep Claude Code's `disable-model-invocation: true` in `SKILL.md` as well; it is not the Codex policy setting. Other skills may omit `agents/openai.yaml`. See [Codex optional metadata](https://learn.chatgpt.com/docs/build-skills#optional-metadata).

Install and refresh the plugin using the [README's Codex instructions](README.md#codex). In a fresh session, confirm each added skill appears in `/skills` or the `$` picker, then exercise its behavior cases. For explicit-only skills, check both selection and non-activation on an unselected matching request. Record the host/version and observed results; structural validation does not establish runtime behavior.

## Releases

Installed copies are cached by plugin version, so users receive a change only when the version changes. For every change meant to reach installed users, bump `version` in all three manifests together: `plugins/company-skills/plugin.json`, `plugins/company-skills/.codex-plugin/plugin.json`, and `plugins/company-skills/.claude-plugin/plugin.json`. The validator fails when they differ.

Keep all three manifests aligned on identity as well. The Codex compatibility manifest must publish `./skills/`. Both marketplace catalogs must point to `./plugins/company-skills` relative to the repository root. Keep Codex marketplace policies and its display name populated. Update the README's skill list when adding or removing a workflow.

## Renaming a skill

A released skill name is part of the public interface: users invoke it by name, and other skills name it as a boundary. To rename one:

1. Move the directory with `git mv` and update the frontmatter `name`, the heading, and every reference to it in other skills, behavior cases, the README, and this file.
2. Leave a deprecated alias at the old name: a `SKILL.md` with `disable-model-invocation: true`, a description starting `Deprecated alias for <new-name>`, and a body that reads `../<new-name>/SKILL.md` and follows it with the same inputs, stating that the target's `<skill dir>`, `scripts/`, and `references/` paths resolve from `../<new-name>/` (the alias directory holds none of them); an `agents/openai.yaml` with `policy.allow_implicit_invocation: false`; and a `tests/prompts.md`. Do not symlink the old directory — the validator rejects a name that differs from its directory, and both copies would trigger.
3. Bump the version in all three manifests and add the rename to the README's **Renamed skills** table, noting any behaviour that changed with it and the release that will remove the alias.
4. In that later release, delete the alias directories only. Keep the table rows: they are the permanent record that points an old name to its replacement.

A name that never shipped in a release needs no alias.

## Validation

Run the repository validator before opening a pull request:

```sh
python3 scripts/validate.py
python3 -m unittest discover -s scripts/tests
```

With Claude Code installed, also run `claude plugin validate . --strict` and `claude plugin validate plugins/company-skills --strict`.

The validator checks this repository's packaging contract, skill metadata, reference paths, size limits, and the behavior-case structure. Its regression tests cover broken packaging configurations. It is not a complete upstream JSON/YAML schema validator and does not validate every optional `agents/openai.yaml` field. Run each skill's script tests separately when changing those scripts. Exercise representative prompts in both Codex and Claude Code for changes that affect both hosts, and report any host you could not test.
