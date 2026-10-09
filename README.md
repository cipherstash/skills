# Company agent skills

Reusable company workflows published as [open Agent Skills](https://agentskills.io) for Codex and Claude Code. One plugin, `company-skills`, ships every skill from the `company` marketplace in this repository.

## Install

Both products install at user scope by default, so the skills are available in every project.

### Claude Code

```sh
claude plugin marketplace add cipherstash/skills
claude plugin install company-skills@company
```

Inside a session, `/plugin marketplace add cipherstash/skills` and `/plugin install company-skills@company` do the same. Start a new session, then invoke a skill by its namespaced name, for example `/company-skills:address-code-review`.

To update to the latest published skills:

```sh
claude plugin marketplace update company
```

### Codex

```sh
codex plugin marketplace add cipherstash/skills
codex plugin add company-skills@company
```

To update, run `codex plugin marketplace upgrade company`.

## Develop locally

Install from a clone by passing its path instead of `cipherstash/skills`:

```sh
claude plugin marketplace add /path/to/skills
claude plugin install company-skills@company

codex plugin marketplace add /path/to/skills
codex plugin add company-skills@company
```

Both products install a cached copy, so edits in the clone are not live:

- **Claude Code:** run `claude plugin marketplace update company` and start a new session. If a change still does not appear, bump `version` in `plugins/company-skills/.claude-plugin/plugin.json`. To test edits without reinstalling, start a session with `claude --plugin-dir /path/to/skills/plugins/company-skills`.
- **Codex:** `marketplace upgrade` refreshes Git marketplaces only. For a local clone, run `codex plugin remove company-skills@company`, then `codex plugin add company-skills@company`.

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

## Contribute

Follow [CONTRIBUTING.md](CONTRIBUTING.md) to add or change a skill: naming, progressive disclosure, required behavior cases, and the validation commands to run. Pull requests run the same validator in GitHub Actions.

See the official [Codex skills documentation](https://developers.openai.com/codex/skills/) and [Claude Code plugin marketplace documentation](https://code.claude.com/docs/en/plugin-marketplaces) for current publishing and installation options.

## License

MIT
