# Repository guidance

Skills have one canonical source: `plugins/company-skills/skills/`.

When adding or changing a skill, follow [CONTRIBUTING.md](CONTRIBUTING.md). Complete every authoring rule and behavior case, then run `python3 scripts/validate.py` successfully.

Keep the portable, Codex, and Claude plugin versions aligned for releases. Follow CONTRIBUTING.md's Codex compatibility and packaging rules, and keep README installation and invocation instructions current for both hosts. Do not duplicate a skill into product-specific directories.

## Agent skills

### Issue tracker

Issues are tracked in GitHub Issues on `cipherstash/skills`, using the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

The five default triage labels: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: one `GLOSSARY.md` and `docs/adr/` at the repo root. See `docs/agents/domain.md`.
