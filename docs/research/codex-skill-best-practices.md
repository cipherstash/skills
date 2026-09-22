# Codex skill best-practices audit

Date: 2026-09-22

## Verdict

**Aligned as a distribution and authoring scaffold after the follow-up changes.** The repository now has a portable Agent Plugins `plugin.json`, retains the supported Codex compatibility manifest, uses a single-source skill layout, validates changes in CI, and documents the required authoring and behavior-test contract. The repository still has no real skills, so instruction quality, triggering, progressive disclosure, and runtime behavior cannot yet be validated.

## What aligns

- `plugins/company-skills/skills/<skill-name>/SKILL.md` matches the standard skill shape and keeps optional `scripts/`, `references/`, and `assets/` with the skill. OpenAI describes a skill as a folder containing `SKILL.md` plus those optional resources. [OpenAI: Build skills](https://developers.openai.com/codex/skills/) [Agent Skills specification](https://agentskills.io/specification)
- The repository packages reusable skills as a plugin instead of relying on `.agents/skills`, which OpenAI recommends for reusable distribution beyond one repository. [OpenAI: Build skills](https://developers.openai.com/codex/skills/)
- `.agents/plugins/marketplace.json` is in the documented repository marketplace location. Its local source begins with `./` and points to the plugin directory, matching OpenAI's marketplace guidance. [OpenAI: Package your plugin](https://developers.openai.com/plugins/build/plugins)
- The current `.codex-plugin/plugin.json` declares `skills: "./skills/"`; this is the supported compatibility structure produced by OpenAI's plugin creator. [OpenAI: Package your plugin](https://developers.openai.com/plugins/build/plugins)
- `AGENTS.md` correctly requires lowercase hyphenated names, concrete trigger conditions, colocated resources, and validation. The README also advises keeping each skill focused on one job. These align with OpenAI's advice to keep a skill focused, make descriptions drive reliable triggering, and test the trigger behavior. [OpenAI: Build skills](https://developers.openai.com/codex/skills/)
- The repository has an MIT `LICENSE`, and both product manifests identify the license as MIT.

## Gaps and risks

### Resolved: portable plugin packaging

`plugins/company-skills/plugin.json` now declares the Agent Plugins 1.0 schema. The `.codex-plugin/plugin.json` file remains as a supported compatibility fallback. [OpenAI: Package your plugin](https://developers.openai.com/plugins/build/plugins)

### High: no actual skill can be audited or behavior-tested

`skills/` contains only `.gitkeep`. A valid directory structure does not demonstrate that future descriptions trigger correctly, instructions have explicit inputs and outputs, scripts are safe, or realistic prompts produce the desired result. OpenAI explicitly recommends testing prompts against each description. [OpenAI: Build skills](https://developers.openai.com/codex/skills/)

### Resolved: complete authoring constraints

`CONTRIBUTING.md` now records the exact name and description constraints, and `scripts/validate.py` enforces their structural parts. [Agent Skills specification](https://agentskills.io/specification)

### Resolved: progressive disclosure and instruction quality

`CONTRIBUTING.md` now defines concise entrypoints, focused references, imperative inputs and outputs, scripts only for deterministic mechanics, and behavior cases covering activation boundaries and edge cases. The validator enforces the line limit and safe, existing relative links. [Agent Skills specification](https://agentskills.io/specification) [OpenAI: Build skills](https://developers.openai.com/codex/skills/)

### Resolved: reproducible validation and CI

`python3 scripts/validate.py` now validates manifests, skill metadata, links, entrypoint size, and behavior fixtures without third-party dependencies. `.github/workflows/validate.yml` runs the same command for pushes to `main` and pull requests.

### Low: Codex-specific per-skill metadata is not discussed

OpenAI supports optional `agents/openai.yaml` inside a skill for UI metadata, invocation policy, and tool dependencies. It is not needed for an instruction-only skill, so this is not a current defect; the authoring guide should mention it when a skill needs icons, explicit-only invocation, or MCP dependencies. [OpenAI: Build skills](https://developers.openai.com/codex/skills/#optional-metadata)

## Concrete recommendations

1. Completed: add the portable Agent Plugins 1.0 manifest while retaining compatibility manifests.
2. Completed: document and validate the expanded authoring contract.
3. Completed: add a repository-level validator and CI workflow.
4. Completed: require positive, negative, incomplete-input, and expected-behavior cases for every skill.
5. Remaining: re-run this audit after the first real skill is added; only then can triggering, instruction quality, progressive disclosure, script safety, and output quality be assessed.

## Sources

- [OpenAI — Build skills](https://developers.openai.com/codex/skills/)
- [OpenAI — Plugin architecture](https://developers.openai.com/plugins/concepts/plugins)
- [OpenAI — Package your plugin](https://developers.openai.com/plugins/build/plugins)
- [Agent Skills — Specification](https://agentskills.io/specification)
- [Agent Skills — Reference implementation](https://github.com/agentskills/agentskills/tree/main/skills-ref)
