# Tests that typescript-practices and typescript-review have replaced the bundled upstream typescript-pro plugin
# (cipherstash/skills#151).
# Run: python3 -m unittest discover -s tests (from the skill directory).
#
# typescript-practices adapts typescript-pro (see NOTICE). Once it ships, the company marketplace must not also offer
# typescript-pro, because the two would compete to activate on TypeScript work.
import ast
import json
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
REPO = SKILL.parents[3]
UPSTREAM = "typescript-pro"
CATALOGS = (".claude-plugin/marketplace.json", ".agents/plugins/marketplace.json")
BUNDLED_LISTS = ("CLAUDE_BUNDLED_PLUGINS", "CODEX_BUNDLED_PLUGINS")


def bundled_names(name: str) -> set[str]:
    """Read the plugin names written in the assignment to `name` in scripts/validate.py, without importing it."""
    tree = ast.parse((REPO / "scripts" / "validate.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(getattr(target, "id", None) == name for target in node.targets):
            return {
                leaf.value
                for leaf in ast.walk(node.value)
                if isinstance(leaf, ast.Constant) and isinstance(leaf.value, str)
            }
    raise AssertionError(f"scripts/validate.py does not assign {name}")


class UpstreamPluginRemovedTests(unittest.TestCase):
    def test_notice_names_the_upstream_plugin(self):
        self.assertIn(f"skills/{UPSTREAM}", (SKILL / "NOTICE").read_text(encoding="utf-8"))

    def test_no_catalog_lists_the_upstream_plugin(self):
        for relative in CATALOGS:
            with self.subTest(catalog=relative):
                plugins = json.loads((REPO / relative).read_text(encoding="utf-8"))["plugins"]
                self.assertNotIn(UPSTREAM, [entry.get("name") for entry in plugins])

    def test_validate_py_does_not_list_the_upstream_plugin_as_bundled(self):
        for name in BUNDLED_LISTS:
            with self.subTest(list=name):
                names = bundled_names(name)
                self.assertTrue(names, f"{name} names no plugin, so this test would pass by accident")
                self.assertNotIn(UPSTREAM, names)


def readme_section(heading: str) -> str:
    readme = (REPO / "README.md").read_text(encoding="utf-8")
    marker = f"\n## {heading}\n"
    if marker not in readme:
        raise AssertionError(f"README.md has no '## {heading}' section")
    return readme.split(marker, 1)[1].split("\n## ", 1)[0]


class ReadmeTests(unittest.TestCase):
    def test_available_skills_lists_both_typescript_skills(self):
        rows = [line for line in readme_section("Available skills").splitlines() if line.startswith("| `")]
        for skill in ("typescript-practices", "typescript-review"):
            with self.subTest(skill=skill):
                self.assertTrue(any(row.startswith(f"| `{skill}` |") for row in rows), f"no table row for {skill}")

    def test_readme_no_longer_installs_or_updates_the_upstream_plugin(self):
        readme = (REPO / "README.md").read_text(encoding="utf-8")
        for command in (f"plugin install {UPSTREAM}@company", f"plugin update {UPSTREAM}@company"):
            with self.subTest(command=command):
                self.assertNotIn(command, readme)
        table = readme_section("Bundled language practice skills")
        self.assertNotIn(f"| `{UPSTREAM}` |", table)

    def test_readme_gives_uninstall_steps_for_the_upstream_plugin(self):
        section = readme_section("Bundled language practice skills")
        self.assertIn(f"claude plugin uninstall {UPSTREAM}@company", section)
        self.assertIn("typescript-practices", section)

    def test_uninstall_note_covers_typescript_pro_installed_as_a_dependency(self):
        # 0.12.0 to 0.18.0 installed typescript-pro as a company-skills dependency. On Claude Code 2.1.332, once the
        # catalog drops it, `claude plugin prune` refuses to run ("cannot determine orphans") until it is uninstalled.
        section = readme_section("Bundled language practice skills")
        note = section.split("removes the bundled `typescript-pro` plugin", 1)[1]
        note = note.split("removes the bundled `golang-pro`", 1)[0]
        self.assertIn("0.12.0 to 0.18.0", note)
        self.assertIn("cannot determine orphans", note)

    def test_prune_advice_says_to_uninstall_typescript_pro_first(self):
        # The update section tells 0.12.0 to 0.18.0 users to run prune, which fails while typescript-pro is installed.
        readme = (REPO / "README.md").read_text(encoding="utf-8")
        advice = readme.split("\nUpdating from 0.12.0 to 0.18.0", 1)[1].split("\nUpdating company-skills does not", 1)[0]
        self.assertIn(f"claude plugin uninstall {UPSTREAM}@company", advice)


if __name__ == "__main__":
    unittest.main()
