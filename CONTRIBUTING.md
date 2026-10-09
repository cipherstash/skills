# Contributing skills

Add skills under `plugins/company-skills/skills/<skill-name>/`. The directory is the single source published to Codex and Claude Code.

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
- Write a non-empty `description` of at most 1,024 characters, in the third person and without XML tags, that says what the skill does and when it should activate. Include a boundary when a nearby request should not activate it.
- Write imperative steps with explicit inputs, outputs, decision points, and stopping conditions. Preserve explicit user instructions and authorization boundaries.
- Keep `SKILL.md` concise—preferably below 500 lines—and move branch-specific detail into focused files under `references/`. Link each reference directly from `SKILL.md`, keep references one level deep, and state when to read each one. Start any reference longer than 100 lines with a table of contents. Use forward-slash relative paths.
- Add `scripts/` only for deterministic or repeated mechanics. Document inputs, outputs, dependencies, and failure behavior, then execute tests for every changed script.
- Put generated-output templates and other copied resources in `assets/`.
- Add `agents/openai.yaml` only when the skill needs Codex UI metadata, explicit-only invocation, or declared tool dependencies.

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

Use the cases for forward testing; they are evaluation inputs, not exact-output snapshots.

## Codex compatibility

Keep the shared workflow usable with the host's available tools. If a workflow delegates, describe a sequential fallback for hosts without subagents. Resolve bundled scripts and references from the installed skill directory, since the working directory is usually the user's project.

For explicit-only skills, set `policy.allow_implicit_invocation: false` in the skill's `agents/openai.yaml`, as `address-code-review` does. Keep Claude Code's `disable-model-invocation: true` in `SKILL.md` as well; it is not the Codex policy setting. Other skills may omit `agents/openai.yaml`. See [Codex optional metadata](https://learn.chatgpt.com/docs/build-skills#optional-metadata).

Install and refresh the plugin using the [README's Codex instructions](README.md#codex). In a fresh session, confirm each added skill appears in `/skills` or the `$` picker, then exercise its behavior cases. For explicit-only skills, check both selection and non-activation on an unselected matching request. Record the host/version and observed results; structural validation does not establish runtime behavior.

## Releases

Installed copies are cached by plugin version, so users receive a change only when the version changes. For every change meant to reach installed users, bump `version` in all three manifests together: `plugins/company-skills/plugin.json`, `plugins/company-skills/.codex-plugin/plugin.json`, and `plugins/company-skills/.claude-plugin/plugin.json`. The validator fails when they differ.

Keep all three manifests aligned on identity as well. The Codex compatibility manifest must publish `./skills/`. Both marketplace catalogs must point to `./plugins/company-skills` relative to the repository root. Keep Codex marketplace policies and its display name populated. Update the README's skill list when adding or removing a workflow.

## Validation

Run the repository validator before opening a pull request:

```sh
python3 scripts/validate.py
python3 -m unittest discover -s scripts/tests
```

With Claude Code installed, also run `claude plugin validate . --strict` and `claude plugin validate plugins/company-skills --strict`.

The validator checks this repository's packaging contract, skill metadata, reference paths, size limits, and the behavior-case structure. Its regression tests cover broken packaging configurations. It is not a complete upstream JSON/YAML schema validator and does not validate every optional `agents/openai.yaml` field. Run each skill's script tests separately when changing those scripts. Exercise representative prompts in both Codex and Claude Code for changes that affect both hosts, and report any host you could not test.
