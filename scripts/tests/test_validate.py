"""Regression tests for the repository's plugin packaging contract."""

import contextlib
import importlib.util
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch


REPO = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("validate", REPO / "scripts/validate.py")
validate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validate)


class PackagingTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        for directory in ("plugins", ".agents", ".claude-plugin"):
            shutil.copytree(REPO / directory, self.root / directory)
        plugin = self.root / "plugins/company-skills"
        paths = patch.multiple(validate, ROOT=self.root, PLUGIN=plugin, SKILLS=plugin / "skills")
        paths.start()
        self.addCleanup(paths.stop)

    def change_json(self, relative, change):
        path = self.root / relative
        value = json.loads((REPO / relative).read_text())
        change(value)
        path.write_text(json.dumps(value))

    def check_result(self, expected, diagnostic=""):
        output = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            result = validate.main()
        self.assertEqual(result, expected, output.getvalue())
        self.assertIn(diagnostic, output.getvalue())

    def test_repository_passes(self):
        self.check_result(0, "Validation passed")

    def test_codex_skill_path_is_required(self):
        for value in (None, "./.codex-plugin/skills/", "../skills/"):
            with self.subTest(value=value):
                self.change_json("plugins/company-skills/.codex-plugin/plugin.json", lambda data: data.update(skills=value))
                self.check_result(1, "skills must be ./skills/")

    def test_versions_stay_aligned(self):
        self.change_json("plugins/company-skills/.codex-plugin/plugin.json", lambda data: data.update(version="9.0.0"))
        self.check_result(1, "version must match plugin.json")

    def test_marketplace_identity_and_source(self):
        for change, diagnostic in (
            (lambda data: data.update(name="other"), "name must be company"),
            (lambda data: data["plugins"][0]["source"].update(source="git"), "must publish ./plugins/company-skills"),
            (lambda data: data["plugins"][0]["source"].update(path="./missing"), "must publish ./plugins/company-skills"),
        ):
            with self.subTest(diagnostic=diagnostic):
                self.change_json(".agents/plugins/marketplace.json", change)
                self.check_result(1, diagnostic)

    def test_marketplace_requires_policy(self):
        self.change_json(".agents/plugins/marketplace.json", lambda data: data["plugins"][0].pop("policy"))
        self.check_result(1, "plugin policy must use")

    def test_marketplace_requires_category_and_display_name(self):
        self.change_json(".agents/plugins/marketplace.json", lambda data: data["plugins"][0].pop("category"))
        self.check_result(1, "plugin category must be Productivity")
        self.change_json(".agents/plugins/marketplace.json", lambda data: data.pop("interface"))
        self.check_result(1, "interface.displayName is required")

    def test_malformed_entries_report_errors(self):
        for value in (None, {}, [None]):
            with self.subTest(value=value):
                self.change_json(".agents/plugins/marketplace.json", lambda data: data.update(plugins=value))
                self.check_result(1, "Validation failed")

    def test_openai_extension_cannot_shadow_fallback(self):
        self.change_json("plugins/company-skills/plugin.json", lambda data: data.update(extensions={"com.openai": {}}))
        self.check_result(1, "com.openai would override it")

    def test_missing_skill_directory_reports_error(self):
        shutil.rmtree(validate.SKILLS)
        self.check_result(1, "shared skills directory is required")

    def test_publisher_required(self):
        for author in (None, {}, {"name": None}, {"name": ""}):
            with self.subTest(author=author):
                self.change_json("plugins/company-skills/plugin.json", lambda data: data.update(author=author))
                self.check_result(1, "author.name is required")


if __name__ == "__main__":
    unittest.main()
