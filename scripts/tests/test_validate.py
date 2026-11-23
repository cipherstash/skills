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
PIN = "149d7b21f4067765b82e67029730b42d228ef4b4"


def git_subdir(name="example-plugin", **changes):
    source = {
        "source": "git-subdir",
        "url": "https://github.com/example/skills.git",
        "path": f"./plugins/{name}",
        "sha": PIN,
    }
    source.update(changes)
    return {"name": name, "source": {key: value for key, value in source.items() if value is not None}}
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

    def add_to_both_catalogs(self, claude_entry, codex_entry, declare=True):
        policy = {"policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"}, "category": "Productivity"}
        if claude_entry and declare:
            self.change_json(
                "plugins/company-skills/.claude-plugin/plugin.json",
                lambda data: data["dependencies"].append(claude_entry["name"]),
            )
        self.change_json(".claude-plugin/marketplace.json", lambda data: data["plugins"].extend([claude_entry] if claude_entry else []))
        self.change_json(
            ".agents/plugins/marketplace.json",
            lambda data: data["plugins"].extend([{**codex_entry, **policy}] if codex_entry else []),
        )

    def test_pinned_git_subdir_entry_passes(self):
        self.add_to_both_catalogs(git_subdir(), git_subdir())
        self.check_result(0, "Validation passed")

    def test_git_subdir_pins_match_across_catalogs(self):
        other = "0" * 40
        for claude_entry, codex_entry in (
            (git_subdir(), git_subdir(sha=other)),
            (git_subdir(), git_subdir(path="./plugins/other")),
            (None, git_subdir()),
        ):
            with self.subTest(claude=claude_entry, codex=codex_entry):
                self.add_to_both_catalogs(claude_entry, codex_entry)
                self.check_result(1, "example-plugin: git-subdir pin must match in both marketplace catalogs")

    def test_claude_only_git_subdir_entry_passes(self):
        self.add_to_both_catalogs(git_subdir(), None)
        self.check_result(0, "Validation passed")

    def test_claude_git_subdir_entries_are_pinned(self):
        for changes, diagnostic in (
            ({"sha": None}, "sha must be a full 40-character lowercase commit SHA"),
            ({"sha": PIN[:7]}, "sha must be a full 40-character lowercase commit SHA"),
            ({"sha": PIN.upper()}, "sha must be a full 40-character lowercase commit SHA"),
            ({"path": None}, "git-subdir source needs url and path"),
            ({"url": None}, "git-subdir source needs url and path"),
        ):
            with self.subTest(changes=changes):
                self.change_json(".claude-plugin/marketplace.json", lambda data: data["plugins"].append(git_subdir(**changes)))
                self.check_result(1, diagnostic)

    def test_codex_git_subdir_entries_are_pinned(self):
        policy = {"policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"}, "category": "Productivity"}
        for changes, diagnostic in (
            ({"sha": PIN[:7]}, "sha must be a full 40-character lowercase commit SHA"),
            ({"path": None}, "git-subdir source needs url and path"),
        ):
            with self.subTest(changes=changes):
                self.change_json(
                    ".agents/plugins/marketplace.json",
                    lambda data: data["plugins"].append({**git_subdir(**changes), **policy}),
                )
                self.check_result(1, diagnostic)

    def test_dependencies_name_listed_plugins(self):
        self.add_to_both_catalogs(git_subdir(), git_subdir())
        manifest = "plugins/company-skills/.claude-plugin/plugin.json"
        self.check_result(0, "Validation passed")
        for dependencies in (
            ["unlisted-plugin"],
            ["example-plugin@other"],
            [{"name": "example-plugin", "version": "^1.0.0"}],
            "example-plugin",
        ):
            with self.subTest(dependencies=dependencies):
                self.change_json(manifest, lambda data: data.update(dependencies=dependencies))
                self.check_result(1, "dependencies must name plugins in the company marketplace")

    def test_bundled_plugin_must_be_a_dependency(self):
        self.add_to_both_catalogs(git_subdir(), git_subdir(), declare=False)
        self.check_result(1, "example-plugin: a bundled plugin in the catalog must be a company-skills dependency")

    def test_bundled_plugin_of_any_source_type_must_be_a_dependency(self):
        for source in (
            {"source": "github", "repo": "example/skills"},
            {"source": "url", "url": "https://github.com/example/skills.git"},
            "./plugins/example-plugin",
        ):
            with self.subTest(source=source):
                shutil.copy(REPO / ".claude-plugin/marketplace.json", self.root / ".claude-plugin/marketplace.json")
                self.change_json(
                    ".claude-plugin/marketplace.json",
                    lambda data: data["plugins"].append({"name": "example-plugin", "source": source}),
                )
                self.check_result(1, "example-plugin: a bundled plugin in the catalog must be a company-skills dependency")

    def test_codex_bundled_plugin_must_be_a_dependency(self):
        codex_market = ".agents/plugins/marketplace.json"
        policy = {"policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"}, "category": "Productivity"}
        for entry in (
            git_subdir(),
            {"name": "example-plugin", "source": {"source": "local", "path": "./plugins/example-plugin"}},
        ):
            with self.subTest(entry=entry):
                shutil.copy(REPO / codex_market, self.root / codex_market)
                self.change_json(codex_market, lambda data: data["plugins"].append({**entry, **policy}))
                self.check_result(
                    1, f"{codex_market}: example-plugin: a bundled plugin in the catalog must be a company-skills dependency"
                )

    def test_malformed_dependencies_report_only_the_shape_error(self):
        manifest = "plugins/company-skills/.claude-plugin/plugin.json"
        for dependencies in ("differential-review", [{"name": "differential-review"}], None):
            with self.subTest(dependencies=dependencies):
                self.change_json(manifest, lambda data: data.update(dependencies=dependencies))
                output = io.StringIO()
                with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
                    result = validate.main()
                self.assertEqual(result, 1, output.getvalue())
                self.assertIn("dependencies must name plugins in the company marketplace", output.getvalue())
                self.assertNotIn("must be a company-skills dependency", output.getvalue())

    def test_removing_a_bundled_plugin_needs_both_catalogs_and_dependencies(self):
        manifest = "plugins/company-skills/.claude-plugin/plugin.json"
        claude_market = ".claude-plugin/marketplace.json"
        codex_market = ".agents/plugins/marketplace.json"
        # A plugin both catalogs list, so every removal path is exercised.
        bundled = "differential-review"
        for relative in (claude_market, codex_market):
            self.assertIn(bundled, [entry["name"] for entry in json.loads((REPO / relative).read_text())["plugins"]])
        self.assertIn(bundled, json.loads((REPO / manifest).read_text())["dependencies"])

        def drop_dependency(data):
            data["dependencies"].remove(bundled)

        def drop_entry(data):
            data["plugins"] = [entry for entry in data["plugins"] if entry["name"] != bundled]

        for removed, diagnostic in (
            ((claude_market, codex_market), "dependencies must name plugins in the company marketplace"),
            ((manifest,), f"{bundled}: a bundled plugin in the catalog must be a company-skills dependency"),
            ((manifest, claude_market), f"{bundled}: git-subdir pin must match in both marketplace catalogs"),
            ((manifest, claude_market, codex_market), "Validation passed"),
        ):
            with self.subTest(removed=removed):
                for relative in (manifest, claude_market, codex_market):
                    shutil.copy(REPO / relative, self.root / relative)
                for relative in removed:
                    self.change_json(relative, drop_dependency if relative == manifest else drop_entry)
                self.check_result(0 if diagnostic == "Validation passed" else 1, diagnostic)

    def test_publisher_required(self):
        for author in (None, {}, {"name": None}, {"name": ""}):
            with self.subTest(author=author):
                self.change_json("plugins/company-skills/plugin.json", lambda data: data.update(author=author))
                self.check_result(1, "author.name is required")


class LicenseDeclarationTests(unittest.TestCase):
    # plain-language ships Apache-2.0 code and OGL-UK-3.0 content
    # (skills/plain-language/LICENSE and NOTICE); the rest of the plugin is MIT.
    BUNDLED = ("MIT", "Apache-2.0", "OGL-UK-3.0")

    def test_manifests_declare_every_bundled_license(self):
        for relative in ("plugin.json", ".claude-plugin/plugin.json", ".codex-plugin/plugin.json"):
            license_value = json.loads((REPO / "plugins/company-skills" / relative).read_text())["license"]
            identifiers = set(license_value.replace("(", " ").replace(")", " ").split())
            for spdx in self.BUNDLED:
                with self.subTest(manifest=relative, spdx=spdx):
                    self.assertIn(spdx, identifiers, f"{relative} license is {license_value!r}")

    def test_readme_license_section_names_every_bundled_license(self):
        readme = (REPO / "README.md").read_text()
        section = readme.split("\n## License\n", 1)[1].split("\n## ", 1)[0]
        for name in ("MIT", "Apache", "Open Government Licence"):
            with self.subTest(name=name):
                self.assertIn(name, section)


if __name__ == "__main__":
    unittest.main()
