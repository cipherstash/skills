"""Tests that the Go check suite gates pull requests in .github/workflows/validate.yml.

The suite and its pinned versions are listed in golang-practices' references/checks.md. These tests check that each
suite check is in place over the golang-practices examples module, and that each pinned version matches that list.
"""

import fnmatch
from pathlib import Path
import re
import unittest

import yaml


REPO = Path(__file__).resolve().parents[2]
PRACTICES = REPO / "plugins/company-skills/skills/golang-practices"
EXAMPLES = "plugins/company-skills/skills/golang-practices/examples"
WORKFLOW = yaml.safe_load((REPO / ".github/workflows/validate.yml").read_text())
# PyYAML reads the bare key `on` as the boolean true.
TRIGGERS = WORKFLOW.get("on", WORKFLOW.get(True))
SUITE = WORKFLOW["jobs"]["go-check-suite"]
STEPS = SUITE["steps"]


def pinned_versions():
    """Return {tool: version} from the pinned versions table in references/checks.md."""
    text = (PRACTICES / "references/checks.md").read_text(encoding="utf-8")
    section = text.split("## Pinned versions", 1)[1].split("\n## ", 1)[0]
    rows = re.findall(r"^\| *`?([\w-]+)`? *\| *`([^`]+)` *\|", section, re.MULTILINE)
    return dict(rows)


PINS = pinned_versions()


def run_lines():
    """Yield (working directory, command line with whitespace collapsed) for each line of each run step."""
    default = SUITE.get("defaults", {}).get("run", {}).get("working-directory", ".")
    for step in STEPS:
        for line in step.get("run", "").splitlines():
            if line.strip():
                yield step.get("working-directory", default), re.sub(r"\s+", " ", line).strip()


def steps_using(action):
    return [step for step in STEPS if step.get("uses", "").startswith(action + "@")]


def step_using(action):
    matches = steps_using(action)
    if len(matches) != 1:
        raise AssertionError(f"want one step that uses {action}, found {len(matches)}")
    return matches[0]


def commands_in(directory):
    return [command for cwd, command in run_lines() if cwd == directory]


class CheckSuiteWorkflowTests(unittest.TestCase):
    def assertRuns(self, pattern, directory=EXAMPLES):
        commands = commands_in(directory)
        self.assertTrue(
            any(re.search(pattern, command) for command in commands),
            f"no step in {directory} runs {pattern!r}; steps there run: {commands}",
        )

    def test_runs_on_every_pull_request(self):
        self.assertIn("pull_request", TRIGGERS)
        # A branch or path filter would let some pull requests skip the suite.
        self.assertFalse(TRIGGERS["pull_request"])
        self.assertNotIn("if", SUITE)

    def test_no_check_may_fail_without_failing_the_job(self):
        self.assertNotIn("continue-on-error", SUITE)
        for step in STEPS:
            with self.subTest(step=step.get("name") or step.get("uses") or step.get("run")):
                self.assertNotIn("continue-on-error", step)
                self.assertNotIn("if", step)
        # A shell set without -e, such as `bash +e {0}`, would let a failing line pass.
        self.assertNotIn("defaults", WORKFLOW)
        self.assertEqual(SUITE["defaults"], {"run": {"working-directory": EXAMPLES}})

    def test_uses_the_latest_stable_go_release(self):
        self.assertEqual(step_using("actions/setup-go")["with"]["go-version"], "stable")

    def test_leaves_out_the_golang_review_fixture(self):
        # The fixture holds planted defects, so the suite would fail on it.
        self.assertNotIn("golang-review", yaml.safe_dump(SUITE))

    def test_covers_every_go_module_except_the_golang_review_fixture(self):
        # The suite's checks run over the examples module only, and `./...` stops at a nested module's go.mod, so a
        # module anywhere else would go unchecked.
        fixtures = REPO / "plugins/company-skills/skills/golang-review/tests/fixtures"
        modules = {
            path.parent.relative_to(REPO).as_posix()
            for path in REPO.rglob("go.mod")
            if ".git" not in path.relative_to(REPO).parts and not path.is_relative_to(fixtures)
        }
        self.assertEqual(modules, {EXAMPLES})

    def test_reference_pins_every_suite_tool(self):
        self.assertEqual(set(PINS), {"golangci-lint", "govulncheck", "semgrep"})

    def test_golangci_lint_runs_the_template_config_at_the_pinned_version(self):
        # Files behind a build constraint load only when it holds, so the default run misses them.
        runs = set()
        for step in steps_using("golangci/golangci-lint-action"):
            with self.subTest(step=step):
                self.assertEqual(step["with"]["version"], PINS["golangci-lint"])
                self.assertEqual(step["with"]["working-directory"], EXAMPLES)
                self.assertNotIn("only-new-issues", step["with"])
                runs.add((step.get("env", {}).get("GOOS"), step["with"]["args"]))
        config = "--config=../assets/golangci.yml"
        self.assertEqual(
            runs, {(None, config), (None, config + " --build-tags=integration"), ("windows", config)}
        )

    def test_config_template_enables_the_suite_linters_and_gofumpt(self):
        config = yaml.safe_load((PRACTICES / "assets/golangci.yml").read_text())
        self.assertEqual(config["version"], "2")
        self.assertLessEqual({"govet", "staticcheck", "gosec"}, set(config["linters"]["enable"]))
        self.assertIn("gofumpt", config["formatters"]["enable"])
        # Exclusions or skipped test files would hide files from the suite.
        self.assertNotIn("exclusions", config["linters"])
        self.assertNotIn("exclusions", config["formatters"])
        self.assertNotEqual(config.get("run", {}).get("tests"), False)

    def test_govulncheck_runs_at_the_pinned_version(self):
        self.assertRuns(rf"^go run golang\.org/x/vuln/cmd/govulncheck@{re.escape(PINS['govulncheck'])} \./\.\.\.$")

    def test_semgrep_runs_p_golang_and_the_local_rules_at_the_pinned_version(self):
        self.assertRuns(rf"pip install semgrep=={re.escape(PINS['semgrep'])}$", directory=".")
        # From the repository root, so the optional .semgrep/ directory is found there.
        self.assertRuns(r"if \[ -d \.semgrep \]; then .*--config \.semgrep", directory=".")
        self.assertRuns(
            rf'^semgrep scan --config p/golang "\$\{{local_rules\[@\]\}}" --error --metrics=off {EXAMPLES}$',
            directory=".",
        )

    def test_semgrep_scans_the_test_files(self):
        # Without a .semgrepignore at the repository root, semgrep uses its default list, which skips *_test.go files
        # and test directories. A root .semgrepignore replaces that list.
        ignore = REPO / ".semgrepignore"
        self.assertTrue(ignore.is_file(), "no .semgrepignore at the repository root, so semgrep skips test files")
        patterns = [
            line.strip()
            for line in ignore.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]
        test_files = sorted((REPO / EXAMPLES).rglob("*_test.go"))
        self.assertTrue(test_files)
        for path in test_files:
            parts = path.relative_to(REPO).parts
            for pattern in patterns:
                with self.subTest(file="/".join(parts), pattern=pattern):
                    glob = pattern.strip("/")
                    self.assertFalse(any(fnmatch.fnmatchcase(part, glob) for part in parts))

    def test_runs_the_tests_with_the_race_detector_and_reports_coverage(self):
        self.assertRuns(r"^go test -race -coverprofile=coverage\.out \./\.\.\.$")
        self.assertRuns(r"^go tool cover -func=coverage\.out$")

    def test_vets_for_windows_and_vets_and_tests_behind_the_integration_tag(self):
        # Files behind a build constraint compile only when it holds, so the default runs miss them.
        self.assertRuns(r"^GOOS=windows go vet \./\.\.\.$")
        self.assertRuns(r"^go vet -tags integration \./\.\.\.$")
        self.assertRuns(r"^go test -race -tags integration \./\.\.\.$")


if __name__ == "__main__":
    unittest.main()
