# Contributing skills

Add skills under `plugins/company-skills/skills/<skill-name>/`. The directory is the single source published to Codex and Claude Code.

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

## Validation

Run the repository validator before opening a pull request:

```sh
python3 scripts/validate.py
```

With Claude Code installed, also run `claude plugin validate . --strict` and `claude plugin validate plugins/company-skills --strict`.

The validator checks manifests, skill metadata, reference paths, size limits, and the behavior-case structure. It cannot prove instruction quality, so also exercise representative prompts in Codex or Claude Code.
