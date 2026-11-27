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


if __name__ == "__main__":
    unittest.main()
