"""Tests for language_drift, the shared helper behind each language's check suite drift test."""

import copy
from pathlib import Path
import tempfile
import unittest

import yaml

import language_drift
from language_drift import Pin


TABLE = """# Checks

## Pinned versions

Every tool version is pinned.

| Tool | Version | Package |
| --- | --- | --- |
| golangci-lint | `v2.15.0` | `github.com/golangci/golangci-lint/v2/cmd/golangci-lint` |
| `semgrep` | `1.186.0` | `semgrep` on PyPI |

## The checks

| tool | `9.9.9` | not a pin |
"""


class ReadPinsTests(unittest.TestCase):
    def checks_md(self, text):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name, "checks.md")
        path.write_text(text, encoding="utf-8")
        return path

    def test_reads_each_row_of_the_pinned_versions_table(self):
        self.assertEqual(
            language_drift.read_pins(self.checks_md(TABLE)),
            {
                "golangci-lint": Pin("v2.15.0", "github.com/golangci/golangci-lint/v2/cmd/golangci-lint"),
                "semgrep": Pin("1.186.0", "semgrep"),
            },
        )

    def test_rejects_a_checks_md_with_no_pinned_versions_table(self):
        # A drift test with no pins would check nothing.
        with self.assertRaises(ValueError):
            language_drift.read_pins(self.checks_md("# Checks\n\n## The checks\n"))
        with self.assertRaises(ValueError):
            language_drift.read_pins(self.checks_md("## Pinned versions\n\nNone yet.\n"))


def workflow(job, on=None, **top):
    """Return a workflow, as PyYAML loads it, that holds one job named suite."""
    return {True: {"pull_request": None} if on is None else on, "jobs": {"suite": job}, **top}


def job(*steps, **keys):
    return {"runs-on": "ubuntu-latest", "steps": list(steps), **keys}


class TriggerTests(unittest.TestCase):
    def test_a_job_on_every_pull_request_passes(self):
        self.assertEqual(language_drift.trigger_problems(workflow(job({"run": "make check"})), "suite"), [])

    def test_a_job_that_some_pull_requests_skip_fails(self):
        cases = {
            "no pull_request trigger": workflow(job(), on={"push": None}),
            "a branch filter": workflow(job(), on={"pull_request": {"branches": ["main"]}}),
            "a path filter": workflow(job(), on={"pull_request": {"paths": ["src/**"]}}),
            "a job condition": workflow(job(**{"if": "github.event_name == 'push'"})),
        }
        for case, flow in cases.items():
            with self.subTest(case):
                self.assertNotEqual(language_drift.trigger_problems(flow, "suite"), [])

    def test_reads_the_on_key_whether_or_not_yaml_turned_it_into_true(self):
        flow = {"on": {"pull_request": None}, "jobs": {"suite": job()}}
        self.assertEqual(language_drift.trigger_problems(flow, "suite"), [])

    def test_reads_the_list_and_string_forms_of_on(self):
        for on in (["push", "pull_request"], "pull_request"):
            with self.subTest(on=on):
                self.assertEqual(language_drift.trigger_problems(workflow(job(), on=on), "suite"), [])
        self.assertNotEqual(language_drift.trigger_problems(workflow(job(), on="push"), "suite"), [])


class BlocksTests(unittest.TestCase):
    def test_a_job_whose_steps_all_fail_it_passes(self):
        flow = workflow(
            job(
                {"uses": "actions/checkout@v4"},
                {"name": "lint", "run": "lint .\ntest ."},
                defaults={"run": {"working-directory": "examples"}},
            )
        )
        self.assertEqual(language_drift.exit_problems(flow, "suite"), [])

    def test_a_step_that_can_fail_without_failing_the_job_fails(self):
        cases = {
            "job continue-on-error": workflow(job({"run": "lint ."}, **{"continue-on-error": True})),
            "step continue-on-error": workflow(job({"run": "lint .", "continue-on-error": True})),
            # A skipped step passes.
            "step condition": workflow(job({"run": "lint .", "if": "always()"})),
            # A shell set without -e, such as `bash {0}`, lets a failing line pass if a later line passes.
            "step shell": workflow(job({"run": "lint .\ntrue", "shell": "bash {0}"})),
            "job default shell": workflow(job({"run": "lint ."}, defaults={"run": {"shell": "bash {0}"}})),
            "workflow default shell": workflow(job({"run": "lint ."}), defaults={"run": {"shell": "bash {0}"}}),
            "or true": workflow(job({"run": "lint . || true"})),
            "or colon": workflow(job({"run": "lint .  ||  :"})),
            "or true mid-line": workflow(job({"run": "lint . || true; echo done"})),
        }
        for case, flow in cases.items():
            with self.subTest(case):
                self.assertNotEqual(language_drift.exit_problems(flow, "suite"), [])


PINS = {"vulncheck": Pin("v1.10.0", "example.com/vulncheck"), "linter": Pin("2.0.0", "linter")}


class ExactPinTests(unittest.TestCase):
    def test_a_step_that_names_each_tool_at_its_pinned_version_passes(self):
        flow = workflow(
            job(
                {"run": "go run example.com/vulncheck@v1.10.0 ./..."},
                {"uses": "example/linter-action@v9", "with": {"version": "2.0.0"}},
            )
        )
        self.assertEqual(language_drift.pin_problems(flow, "suite", PINS), [])

    def test_a_tool_at_another_version_or_none_fails(self):
        linter = {"run": "pip install linter==2.0.0"}
        cases = {
            "latest": [{"run": "go run example.com/vulncheck@latest ./..."}, linter],
            "another version": [{"run": "go run example.com/vulncheck@v1.10.1 ./..."}, linter],
            "a longer version": [{"run": "go run example.com/vulncheck@v1.10.0-rc.1 ./..."}, linter],
            "missing": [linter],
            # The version belongs to another step, so it does not pin this tool.
            "version on another step": [{"run": "vulncheck ./..."}, {"run": "pip install linter==2.0.0 x==v1.10.0"}],
        }
        for case, steps in cases.items():
            with self.subTest(case):
                problems = language_drift.pin_problems(workflow(job(*steps)), "suite", PINS)
                self.assertEqual(len(problems), 1, problems)
                self.assertIn("vulncheck", problems[0])


class LockfilePinTests(unittest.TestCase):
    """A version also counts as pinned when a committed lockfile fixes it and CI installs it frozen or locked."""

    FIXTURE = Path(__file__).resolve().parent / "fixtures/lockfile-pin"
    LOCKFILES = {"fixlint": "tools/tools.lock"}

    def setUp(self):
        self.workflow = yaml.safe_load((self.FIXTURE / "workflow.yml").read_text(encoding="utf-8"))
        self.pins = language_drift.read_pins(self.FIXTURE / "checks.md")

    def problems(self, flow=None, pins=None, lockfiles=None):
        return language_drift.pin_problems(
            flow or self.workflow,
            "suite",
            pins or self.pins,
            root=self.FIXTURE,
            lockfiles=lockfiles or self.LOCKFILES,
        )

    def install_step(self, flow):
        return next(step for step in flow["jobs"]["suite"]["steps"] if step.get("name") == "Install the locked tools")

    def test_a_tool_fixed_by_a_lockfile_installed_frozen_passes(self):
        self.assertEqual(self.pins, {"fixlint": Pin("2.4.1", "fixlint")})
        self.assertEqual(self.problems(), [])

    def test_each_locked_or_frozen_install_flag_counts(self):
        for command in ("pkg install --locked", "pkg sync --frozen-lockfile", "pkg install --immutable", "npm ci"):
            with self.subTest(command):
                flow = copy.deepcopy(self.workflow)
                self.install_step(flow)["run"] = command
                self.assertEqual(self.problems(flow), [])

    def test_an_install_that_may_change_the_lockfile_fails(self):
        flow = copy.deepcopy(self.workflow)
        self.install_step(flow)["run"] = "pkg install"
        self.assertEqual(len(self.problems(flow)), 1)

    def test_a_frozen_install_in_another_directory_fails(self):
        flow = copy.deepcopy(self.workflow)
        self.install_step(flow)["working-directory"] = "."
        self.assertEqual(len(self.problems(flow)), 1)

    def test_a_lockfile_at_another_version_fails(self):
        # 9.9.9 is fixlint-plugin's version, not fixlint's.
        for version in ("2.4.2", "9.9.9"):
            with self.subTest(version):
                self.assertEqual(len(self.problems(pins={"fixlint": Pin(version, "fixlint")})), 1)

    def test_a_missing_lockfile_fails(self):
        self.assertEqual(len(self.problems(lockfiles={"fixlint": "tools/missing.lock"})), 1)


class DriftTestsTests(unittest.TestCase):
    """A language's drift test subclasses DriftTests and names its checks.md and CI job."""

    def run_drift_test(self, **settings):
        fixture = LockfilePinTests.FIXTURE
        attributes = {
            "CHECKS": fixture / "checks.md",
            "JOB": "suite",
            "WORKFLOW": fixture / "workflow.yml",
            "ROOT": fixture,
            "LOCKFILES": LockfilePinTests.LOCKFILES,
            **settings,
        }
        drift_test = type("FixtureDriftTests", (language_drift.DriftTests, unittest.TestCase), attributes)
        result = unittest.TestResult()
        unittest.defaultTestLoader.loadTestsFromTestCase(drift_test).run(result)
        return result

    def test_passes_on_a_suite_in_place(self):
        result = self.run_drift_test()
        self.assertEqual(result.testsRun, 3)
        self.assertTrue(result.wasSuccessful(), result.failures + result.errors)

    def test_fails_on_a_suite_whose_pin_drifted(self):
        result = self.run_drift_test(LOCKFILES={})
        self.assertEqual(len(result.failures), 1)
        self.assertIn("fixlint", result.failures[0][1])


if __name__ == "__main__":
    unittest.main()
