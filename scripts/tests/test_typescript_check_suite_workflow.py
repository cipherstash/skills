"""Tests that the TypeScript check suite gates pull requests in .github/workflows/validate.yml.

The suite and its pinned versions are listed in typescript-practices' references/checks.md. These tests check that each
suite check is in place over the typescript-practices examples package, and that each pinned version matches that
list. The checks every language shares come from language_drift.DriftTests; the rest are TypeScript's own.
"""

import json
import os
import re
import unittest

import yaml

import language_drift
from test_go_check_suite_workflow import semgrep_ignored


REPO = language_drift.REPO
PRACTICES = REPO / "plugins/company-skills/skills/typescript-practices"
EXAMPLES = "plugins/company-skills/skills/typescript-practices/examples"
LOCKFILE = f"{EXAMPLES}/pnpm-lock.yaml"
REVIEW_FIXTURES = "plugins/company-skills/skills/typescript-review/tests/fixtures"
WORKFLOW = yaml.safe_load((REPO / ".github/workflows/validate.yml").read_text())
SUITE_JOB = "typescript-check-suite"
SUITE = WORKFLOW["jobs"].get(SUITE_JOB, {"steps": []})
STEPS = SUITE["steps"]
PINS = {tool: pin.version for tool, pin in language_drift.read_pins(PRACTICES / "references/checks.md").items()}
# The suite's tools that are exact devDependencies of the examples package, fixed by its committed lockfile.
LOCKED_TOOLS = (
    "typescript",
    "@biomejs/biome",
    "oxlint",
    "oxlint-tsgolint",
    "vitest",
    "@vitest/coverage-v8",
    "fast-check",
    "@fast-check/vitest",
    "publint",
)
# The suite's tools that the workflow pins, because they are not npm packages, or, for attw, because its own exact
# TypeScript dependency would put a second TypeScript version in the examples package's lockfile.
WORKFLOW_TOOLS = ("@arethetypeswrong/cli", "osv-scanner", "semgrep")
# The compiler settings typescript-practices requires, isolatedDeclarations because the examples package is published.
REQUIRED_COMPILER_SETTINGS = (
    "strict",
    "noUncheckedIndexedAccess",
    "exactOptionalPropertyTypes",
    "verbatimModuleSyntax",
    "isolatedDeclarations",
)
# The type-aware rules the oxlint template must turn on as errors.
TYPE_AWARE_RULES = (
    "typescript/no-floating-promises",
    "typescript/no-misused-promises",
    "typescript/no-unsafe-argument",
    "typescript/no-unsafe-assignment",
    "typescript/no-unsafe-call",
    "typescript/no-unsafe-member-access",
    "typescript/no-unsafe-return",
    "typescript/only-throw-error",
    "typescript/switch-exhaustiveness-check",
)


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def steps_using(action):
    return [step for step in STEPS if step.get("uses", "").startswith(action + "@")]


def step_using(action):
    matches = steps_using(action)
    if len(matches) != 1:
        raise AssertionError(f"want one step that uses {action}, found {len(matches)}")
    return matches[0]


def commands_in(directory):
    return [command for cwd, command in language_drift.run_lines(WORKFLOW, SUITE_JOB) if cwd == directory]


def package_directories():
    """Return each directory in the repository, relative to it, that holds a package.json outside node_modules."""
    found = set()
    for root, dirs, files in os.walk(REPO):
        dirs[:] = [d for d in dirs if d not in (".git", "node_modules")]
        if "package.json" in files:
            found.add(os.path.relpath(root, REPO).replace(os.sep, "/"))
    return found


class CheckSuiteWorkflowTests(language_drift.DriftTests, unittest.TestCase):
    CHECKS = PRACTICES / "references/checks.md"
    JOB = SUITE_JOB
    LOCKFILES = {tool: LOCKFILE for tool in LOCKED_TOOLS}

    def assertRuns(self, pattern, directory=EXAMPLES):
        commands = commands_in(directory)
        self.assertTrue(
            any(re.search(pattern, command) for command in commands),
            f"no step in {directory} runs {pattern!r}; steps there run: {commands}",
        )

    # DriftTests checks that the suite runs on every pull request with no filter or job condition, that no job, step
    # or default sets continue-on-error, a condition, or a shell, and that each tool is pinned at its version: through
    # the lockfile and a frozen install for LOCKFILES, and in a step for the rest.

    def test_the_job_exists(self):
        self.assertIn(SUITE_JOB, WORKFLOW["jobs"])

    def test_no_check_may_fail_without_failing_the_job(self):
        super().test_no_check_may_fail_without_failing_the_job()
        # TypeScript's suite also sets no defaults but the examples package's working directory.
        self.assertNotIn("defaults", WORKFLOW)
        self.assertEqual(SUITE["defaults"], {"run": {"working-directory": EXAMPLES}})

    def test_reference_pins_every_suite_tool(self):
        self.assertEqual(set(PINS), set(LOCKED_TOOLS) | set(WORKFLOW_TOOLS))

    def test_each_locked_tool_is_an_exact_dev_dependency(self):
        dev = read_json(PRACTICES / "examples/package.json")["devDependencies"]
        for tool in LOCKED_TOOLS:
            with self.subTest(tool=tool):
                self.assertEqual(dev.get(tool), PINS[tool])
        for tool in WORKFLOW_TOOLS:
            with self.subTest(tool=tool):
                self.assertNotIn(tool, dev)

    def test_every_dev_dependency_is_exact(self):
        for name, version in read_json(PRACTICES / "examples/package.json")["devDependencies"].items():
            with self.subTest(package=name):
                self.assertRegex(version, r"^\d+\.\d+\.\d+$")

    def test_pnpm_is_pinned_in_package_manager_and_nowhere_else(self):
        package = read_json(PRACTICES / "examples/package.json")
        self.assertRegex(package["packageManager"], r"^pnpm@\d+\.\d+\.\d+(\+sha\d+\.[0-9a-f]+)?$")
        setup = step_using("pnpm/action-setup")
        # With no version input, the action installs the version packageManager names.
        self.assertEqual(setup.get("with"), {"package_json_file": f"{EXAMPLES}/package.json"})

    def test_uses_the_latest_node_lts_release(self):
        self.assertEqual(step_using("actions/setup-node")["with"]["node-version"], "lts/*")

    def test_installs_the_lockfile_frozen(self):
        self.assertRuns(r"^pnpm install --frozen-lockfile$")

    def test_type_checks_every_tsconfig_with_a_fixed_checkers_count(self):
        configs = sorted(path.name for path in (REPO / EXAMPLES).glob("tsconfig*.json"))
        self.assertIn("tsconfig.json", configs)
        for config in configs:
            with self.subTest(config=config):
                self.assertRuns(rf"^pnpm exec tsc --noEmit -p {re.escape(config)} --checkers \d+$")

    def test_formats_and_lints_with_biome_from_the_template(self):
        self.assertRuns(r"^pnpm exec biome ci --error-on-warnings --config-path=\.\./assets/biome\.json$")

    def test_lints_types_with_oxlint_from_the_template(self):
        self.assertRuns(r"^pnpm exec oxlint --type-aware --deny-warnings -c \.\./assets/oxlintrc\.json$")

    def test_runs_the_tests_with_v8_coverage_and_no_threshold(self):
        self.assertRuns(r"^pnpm exec vitest run --coverage --coverage\.provider=v8$")
        # A Vitest config file could set a threshold, and it is code that runs.
        self.assertEqual(sorted((REPO / EXAMPLES).glob("vit*.config.*")), [])
        self.assertNotIn("threshold", yaml.safe_dump(SUITE))

    def test_checks_the_package_shape_with_publint_and_attw(self):
        package = read_json(PRACTICES / "examples/package.json")
        # publint and attw run over every package that does not set "private": true, so the examples package sets none.
        self.assertNotIn("private", package)
        self.assertRuns(r"^pnpm run build$")
        self.assertRuns(r"^pnpm exec publint --strict$")
        attw = re.escape(f"@arethetypeswrong/cli@{PINS['@arethetypeswrong/cli']}")
        self.assertRuns(rf"^pnpm dlx {attw} --pack \. --profile esm-only$")

    def test_has_no_publish_step(self):
        self.assertNotRegex(yaml.safe_dump(SUITE), r"\bpublish\b")

    def test_osv_scanner_scans_every_lockfile_at_the_pinned_version(self):
        self.assertIsNotNone(step_using("actions/setup-go"))
        osv = re.escape(f"github.com/google/osv-scanner/v2/cmd/osv-scanner@{PINS['osv-scanner']}")
        self.assertRuns(rf"^go run {osv} scan source -r \.$")

    def test_semgrep_runs_both_rulesets_and_the_local_rules_at_the_pinned_version(self):
        self.assertRuns(rf"pip install semgrep=={re.escape(PINS['semgrep'])}$", directory=".")
        # From the repository root, so the optional .semgrep/ directory is found there.
        self.assertRuns(r"if \[ -d \.semgrep \]; then .*--config \.semgrep", directory=".")
        self.assertRuns(
            r'^semgrep scan --config p/typescript --config p/javascript "\$\{local_rules\[@\]\}" --error '
            rf"--metrics=off {EXAMPLES}$",
            directory=".",
        )

    def test_semgrep_pin_is_the_one_every_language_shares(self):
        go = language_drift.read_pins(REPO / "plugins/company-skills/skills/golang-practices/references/checks.md")
        self.assertEqual(PINS["semgrep"], go["semgrep"].version)

    def test_semgrep_scans_the_test_files(self):
        ignore = REPO / ".semgrepignore"
        test_files = sorted(path.relative_to(REPO).as_posix() for path in (REPO / EXAMPLES).rglob("src/**/*.test.ts"))
        self.assertTrue(test_files)
        self.assertEqual(semgrep_ignored(ignore.read_text(encoding="utf-8"), test_files), [])

    def test_leaves_out_the_typescript_review_fixture(self):
        # The fixture holds planted defects, so the suite would fail on it.
        self.assertNotIn("typescript-review", yaml.safe_dump(SUITE))

    def test_covers_every_package_except_the_typescript_review_fixture(self):
        # Every check runs over the examples package only, so a package anywhere else would go unchecked. The
        # typescript-review fixture is the one exception: a check is in place when it covers every package except
        # fixtures with planted defects.
        fixtures = REVIEW_FIXTURES + "/"
        self.assertEqual({d for d in package_directories() if not d.startswith(fixtures)}, {EXAMPLES})
        self.assertTrue(any(d.startswith(fixtures) for d in package_directories()), "the fixture has no package.json")

    def test_tsconfig_template_sets_the_required_compiler_settings(self):
        options = read_json(PRACTICES / "assets/tsconfig.json")["compilerOptions"]
        for setting in REQUIRED_COMPILER_SETTINGS:
            with self.subTest(setting=setting):
                self.assertIs(options.get(setting), True)

    def test_examples_tsconfig_extends_the_template_and_weakens_nothing(self):
        config = read_json(REPO / EXAMPLES / "tsconfig.json")
        self.assertEqual(config["extends"], "../assets/tsconfig.json")
        overridden = set(config["compilerOptions"]) & set(read_json(PRACTICES / "assets/tsconfig.json")["compilerOptions"])
        self.assertEqual(overridden, set())
        for path in (REPO / EXAMPLES).glob("tsconfig*.json"):
            with self.subTest(config=path.name):
                options = read_json(path).get("compilerOptions", {})
                self.assertFalse(set(options) & set(REQUIRED_COMPILER_SETTINGS))
                self.assertNotIn("skipLibCheck", options)

    def test_biome_template_runs_the_recommended_rules(self):
        config = read_json(PRACTICES / "assets/biome.json")
        self.assertIs(config["linter"]["enabled"], True)
        self.assertIs(config["formatter"]["enabled"], True)
        self.assertEqual(config["linter"]["rules"]["preset"], "recommended")
        # Biome reads the template's own version from its schema URL.
        self.assertIn(f"/schemas/{PINS['@biomejs/biome']}/", config["$schema"])

    def test_oxlint_template_turns_on_the_type_aware_rules(self):
        config = read_json(PRACTICES / "assets/oxlintrc.json")
        for rule in TYPE_AWARE_RULES:
            with self.subTest(rule=rule):
                self.assertEqual(config["rules"].get(rule), "error")
        # A JavaScript plugin runs code when oxlint loads it, so the template names none.
        self.assertNotIn("jsPlugins", config)

    def test_oxlint_tsgolint_moves_with_typescript(self):
        # oxlint-tsgolint's version starts with the TypeScript version it is built on.
        self.assertTrue(
            PINS["oxlint-tsgolint"].startswith(PINS["typescript"]),
            f"oxlint-tsgolint {PINS['oxlint-tsgolint']} is not built on typescript {PINS['typescript']}",
        )


if __name__ == "__main__":
    unittest.main()
