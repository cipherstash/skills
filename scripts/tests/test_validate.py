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

    def bundle(self, name, claude=True, codex=True):
        """List a plugin as bundled in validate.py for the catalogs given."""
        changes = {}
        if claude:
            changes["CLAUDE_BUNDLED_PLUGINS"] = validate.CLAUDE_BUNDLED_PLUGINS | {name}
        if codex:
            changes["CODEX_BUNDLED_PLUGINS"] = validate.CODEX_BUNDLED_PLUGINS | {name}
        bundled = patch.multiple(validate, **changes)
        bundled.start()
        self.addCleanup(bundled.stop)

    def add_to_both_catalogs(self, claude_entry, codex_entry, declare=True):
        policy = {"policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"}, "category": "Productivity"}
        if declare and (claude_entry or codex_entry):
            self.bundle((claude_entry or codex_entry)["name"], claude=bool(claude_entry), codex=bool(codex_entry))
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

    def test_manifests_declare_no_dependencies(self):
        for manifest in (
            "plugins/company-skills/plugin.json",
            "plugins/company-skills/.codex-plugin/plugin.json",
            "plugins/company-skills/.claude-plugin/plugin.json",
        ):
            self.assertNotIn("dependencies", json.loads((REPO / manifest).read_text()))
            for dependencies in (["differential-review"], [], "differential-review"):
                with self.subTest(manifest=manifest, dependencies=dependencies):
                    self.change_json(manifest, lambda data: data.update(dependencies=dependencies))
                    self.check_result(1, f"{manifest}: must not declare dependencies")
            shutil.copy(REPO / manifest, self.root / manifest)

    def test_bundled_plugin_must_be_listed(self):
        self.add_to_both_catalogs(git_subdir(), git_subdir(), declare=False)
        self.check_result(1, "example-plugin: a bundled plugin in the catalog must be listed in validate.py")

    def test_bundled_plugin_of_any_source_type_must_be_listed(self):
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
                self.check_result(1, "example-plugin: a bundled plugin in the catalog must be listed in validate.py")

    def test_claude_only_plugins_are_not_bundled_for_codex(self):
        self.check_result(0, "Validation passed")
        codex_market = ".agents/plugins/marketplace.json"
        policy = {"policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"}, "category": "Productivity"}
        self.change_json(
            codex_market,
            lambda data: data["plugins"].append({**git_subdir(name="plugin-dev"), **policy}),
        )
        self.check_result(1, f"{codex_market}: plugin-dev: a bundled plugin in the catalog must be listed in validate.py")

    def test_codex_bundled_plugin_must_be_listed(self):
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
                    1, f"{codex_market}: example-plugin: a bundled plugin in the catalog must be listed in validate.py"
                )

    def test_removing_a_bundled_plugin_needs_both_catalogs_and_the_list(self):
        claude_market = ".claude-plugin/marketplace.json"
        codex_market = ".agents/plugins/marketplace.json"
        # A plugin both catalogs list, so every removal path is exercised.
        bundled = "differential-review"
        for relative in (claude_market, codex_market):
            self.assertIn(bundled, [entry["name"] for entry in json.loads((REPO / relative).read_text())["plugins"]])

        def drop_entry(data):
            data["plugins"] = [entry for entry in data["plugins"] if entry["name"] != bundled]

        unlisted = {
            "CLAUDE_BUNDLED_PLUGINS": validate.CLAUDE_BUNDLED_PLUGINS - {bundled},
            "CODEX_BUNDLED_PLUGINS": validate.CODEX_BUNDLED_PLUGINS - {bundled},
        }
        for removed, drop_from_list, diagnostic in (
            ((), True, f"{bundled}: a bundled plugin in the catalog must be listed in validate.py"),
            ((claude_market,), False, f"{bundled}: listed in validate.py as bundled but missing from the catalog"),
            ((claude_market, codex_market), False, f"{bundled}: listed in validate.py as bundled but missing from the catalog"),
            ((claude_market, codex_market), True, "Validation passed"),
        ):
            with self.subTest(removed=removed, drop_from_list=drop_from_list):
                for relative in (claude_market, codex_market):
                    shutil.copy(REPO / relative, self.root / relative)
                for relative in removed:
                    self.change_json(relative, drop_entry)
                with patch.multiple(validate, **unlisted) if drop_from_list else contextlib.nullcontext():
                    self.check_result(0 if diagnostic == "Validation passed" else 1, diagnostic)

    def add_reference(self, text, relative="references/extra.md"):
        path = self.root / "plugins/company-skills/skills/plain-language" / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return path

    def test_reference_to_a_shipped_skill_passes(self):
        self.add_reference(
            "Follow the `rust-security` skill, the `rust-*` skills, `company-skills:golang-practices`, "
            "or `company-skills:rust-*`.\n"
        )
        self.check_result(0, "Validation passed")

    def test_reference_to_an_unshipped_company_skill_fails(self):
        for text, relative in (
            ("Use `company-skills:review-code` if it is installed.\n", "references/extra.md"),
            ("Use company-skills:review-code here.\n", "references/extra.md"),
            ("# see company-skills:review-code\n", "assets/extra.yml"),
            ("# see company-skills:review-code\n", "scripts/extra.py"),
        ):
            with self.subTest(text=text, relative=relative):
                path = self.add_reference(text, relative)
                self.check_result(1, "company-skills does not ship `review-code`")
                path.unlink()

    def test_bare_reference_to_another_plugins_skill_fails(self):
        for text in ("Invoke the `python-pro` skill.\n", "Load the `python-*` skills.\n"):
            with self.subTest(text=text):
                self.add_reference(text)
                self.check_result(1, "is not a company-skills skill")

    def test_other_plugins_skill_needs_a_fallback(self):
        for text in (
            "Invoke `mattpocock-skills:tdd` and follow it.\n\n\n\n\nIf mattpocock-skills cannot be loaded, too far.\n",
            "Invoke `superpowers:brainstorming` and follow it.\n",
            "Use `mattpocock-skills:tdd`. PGPORT is not available on Windows.\n",
            "Invoke `mattpocock-skills:tdd`.\nIf it cannot be loaded, work red-green yourself.\n",
        ):
            with self.subTest(text=text):
                self.add_reference(text)
                self.check_result(1, "is another plugin's skill")
        for text in (
            "Invoke `mattpocock-skills:tdd`.\nIf `mattpocock-skills:tdd` cannot be loaded, work red-green yourself.\n",
            "If the superpowers plugin is not installed, skip this.\nInvoke `superpowers:brainstorming`.\n",
            "Run `/differential-review:diff-review` if it is available; otherwise review by hand.\n",
            "Invoke \\`mattpocock-skills:tdd\\`. If the mattpocock-skills plugin is not installed, follow its steps.\n",
        ):
            with self.subTest(text=text):
                self.add_reference(text)
                self.check_result(0, "Validation passed")

    def test_behaviour_cases_and_non_skill_colons_are_ignored(self):
        self.add_reference("Report `path:line`, `file:12` and `localhost:6060`; set key:value.\n")
        self.check_result(0, "Validation passed")
        self.add_reference("Invoke `mattpocock-skills:tdd`.\n", relative="tests/extra.md")
        self.check_result(0, "Validation passed")

    def test_unparsed_catalog_reports_no_missing_bundled_plugins(self):
        for relative in (".claude-plugin/marketplace.json", ".agents/plugins/marketplace.json"):
            with self.subTest(catalog=relative):
                self.change_json(relative, lambda data: data.update(plugins="not a list"))
                output = io.StringIO()
                with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
                    result = validate.main()
                self.assertEqual(result, 1, output.getvalue())
                self.assertIn("plugins must be an array", output.getvalue())
                self.assertNotIn("missing from the catalog", output.getvalue())
                shutil.copy(REPO / relative, self.root / relative)

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
