# Repository guidance

Every published skill lives once, in `plugins/company-skills/skills/`; Codex and Claude Code both publish from that directory. Skills for working on this repository live in `.claude/skills/` and are not published.

When adding, changing, renaming, or releasing a skill, follow [CONTRIBUTING.md](CONTRIBUTING.md). The change is done when it meets every authoring rule and behavior case, the README's installation and invocation instructions are current for both hosts, and `python3 scripts/validate.py` passes.

To build a language's skill pair (`<lang>-practices` and `<lang>-review`), read and follow `.claude/skills/building-language-pairs/SKILL.md`.

## Agent skills

### Issue tracker

Issues are tracked in GitHub Issues on `cipherstash/skills`. See `docs/agents/issue-tracker.md`.

### Triage labels

The five default triage labels: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: one `GLOSSARY.md` and `docs/adr/` at the repo root. See `docs/agents/domain.md`.
