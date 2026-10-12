# Repository guidance

Skills have one canonical source: `plugins/company-skills/skills/`.

When adding or changing a skill, follow [CONTRIBUTING.md](CONTRIBUTING.md). Complete every authoring rule and behavior case, then run `python3 scripts/validate.py` successfully.

Keep the portable, Codex, and Claude plugin versions aligned for releases. Follow CONTRIBUTING.md's Codex compatibility and packaging rules, and keep README installation and invocation instructions current for both hosts. Do not duplicate a skill into product-specific directories.
