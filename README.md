# Company agent skills

Reusable company workflows published as [open Agent Skills](https://agentskills.io) for Codex and Claude Code.

## Structure

```text
.
├── .agents/plugins/marketplace.json       # Codex marketplace
├── .claude-plugin/marketplace.json        # Claude Code marketplace
└── plugins/company-skills/
    ├── plugin.json                         # Portable Agent Plugins manifest
    ├── .codex-plugin/plugin.json           # Codex compatibility metadata
    ├── .claude-plugin/plugin.json          # Claude Code plugin metadata
    └── skills/<skill-name>/SKILL.md        # Shared skill source
```

Each skill is authored once under `plugins/company-skills/skills/`. Both plugin manifests publish that same directory, so product-specific copies cannot drift.

## Add a skill

Create `plugins/company-skills/skills/<skill-name>/SKILL.md`:

```markdown
---
name: skill-name
description: State what the skill does and the requests that should trigger it.
---

Write the instructions the agent should follow.
```

Follow [CONTRIBUTING.md](CONTRIBUTING.md) for naming, progressive disclosure, supporting resources, and required behavior cases.

## Validate locally

```sh
python3 scripts/validate.py
```

Pull requests run the same validator in GitHub Actions.

## Install during development

For Codex, add this repository as a plugin marketplace, then install `company-skills` from the `company` marketplace. For Claude Code:

```text
/plugin marketplace add /path/to/this/repository
/plugin install company-skills@company
```

See the official [Codex skills documentation](https://developers.openai.com/codex/skills/) and [Claude Code plugin marketplace documentation](https://code.claude.com/docs/en/plugin-marketplaces) for current publishing and installation options.

## License

MIT
