"""Tests that the Python check suite gates pull requests in .github/workflows/validate.yml.

The suite and its pinned versions are listed in python-practices' references/checks.md. These tests check that each
suite check is in place over the python-practices examples project, and that each pinned version matches that list.
The checks every language shares come from language_drift.DriftTests; the rest are Python's own, including the
griffe advisory check, which runs on every pull request but never blocks.
"""

from pathlib import Path
import re
import tempfile
import unittest

import yaml

import language_drift
from test_go_check_suite_workflow import semgrep_ignored


REPO = language_drift.REPO
PRACTICES = REPO / "plugins/company-skills/skills/python-practices"
CHECKS = PRACTICES / "references/checks.md"
EXAMPLES = "plugins/company-skills/skills/python-practices/examples"
LOCKFILE = f"{EXAMPLES}/uv.lock"
WORKFLOW = yaml.safe_load((REPO / ".github/workflows/validate.yml").read_text(encoding="utf-8"))
SUITE_JOB = "python-check-suite"
ADVISORY_JOB = "python-advisory-checks"
PINS = {tool: pin.version for tool, pin in language_drift.read_pins(CHECKS).items()}
# The tools the examples project's dev dependency group holds at exact versions, fixed by its committed uv.lock.
LOCKED_TOOLS = ("ruff", "mypy", "pytest", "pytest-cov", "hypothesis", "pip-audit")


def advisory_pins():
    """Return {tool: Pin} from checks.md's ## Advisory checks table, read with the shared parser.

    The shared parser reads only the ## Pinned versions section, so the advisory table is handed to it under that
    heading, in a file of its own. The parser itself does not change.
    """
    text = CHECKS.read_text(encoding="utf-8")
    heading = re.search(r"^## Advisory checks[ \t]*$", text, re.MULTILINE)
    if not heading:
        raise AssertionError(f"{CHECKS} has no ## Advisory checks section")
    section = text[heading.end():].split("\n## ", 1)[0]
    with tempfile.TemporaryDirectory() as scratch:
        path = Path(scratch, "checks.md")
        path.write_text("## Pinned versions\n" + section, encoding="utf-8")
        return language_drift.read_pins(path)


def commands_in(job, directory):
    return [command for cwd, command in language_drift.run_lines(WORKFLOW, job) if cwd == directory]


def steps_using(job, action):
    return [step for step in WORKFLOW["jobs"][job]["steps"] if step.get("uses", "").startswith(action + "@")]


def step_using(job, action):
    matches = steps_using(job, action)
    if len(matches) != 1:
        raise AssertionError(f"want one step in {job} that uses {action}, found {len(matches)}")
    return matches[0]


class PythonCheckSuiteWorkflowTests(language_drift.DriftTests, unittest.TestCase):
    CHECKS = CHECKS
    JOB = SUITE_JOB
    LOCKFILES = {tool: LOCKFILE for tool in LOCKED_TOOLS}

    def assertRuns(self, pattern, directory=EXAMPLES, job=SUITE_JOB):
        commands = commands_in(job, directory)
        self.assertTrue(
            any(re.search(pattern, command) for command in commands),
            f"no step of {job} in {directory} runs {pattern!r}; steps there run: {commands}",
        )

    # DriftTests checks that the suite runs on every pull request with no filter or job condition, that no job, step
    # or default sets continue-on-error, a condition, or a shell, and that each tool is pinned: uv and semgrep in the
    # workflow, and the others through uv.lock, installed with `uv sync --locked`.

    def test_reference_pins_every_suite_tool(self):
        self.assertEqual(set(PINS), {*LOCKED_TOOLS, "semgrep", "uv"})

    def test_semgrep_shares_the_go_pin(self):
        # semgrep has one pin, shared by every language.
        go = language_drift.read_pins(REPO / "plugins/company-skills/skills/golang-practices/references/checks.md")
        self.assertEqual(PINS["semgrep"], go["semgrep"].version)

    def test_sets_no_defaults_but_the_examples_project(self):
        self.assertNotIn("defaults", WORKFLOW)
        self.assertEqual(WORKFLOW["jobs"][SUITE_JOB]["defaults"], {"run": {"working-directory": EXAMPLES}})

    def test_uses_the_latest_stable_cpython_and_no_other(self):
        self.assertEqual(step_using(SUITE_JOB, "actions/setup-python")["with"]["python-version"], "3.x")
        self.assertNotIn("allow-prereleases", step_using(SUITE_JOB, "actions/setup-python")["with"])
        # uv uses the CPython that setup-python installed, never one it downloads itself.
        self.assertEqual(WORKFLOW["jobs"][SUITE_JOB]["env"]["UV_PYTHON_DOWNLOADS"], "never")

    def test_installs_uv_at_the_pinned_version(self):
        self.assertEqual(step_using(SUITE_JOB, "astral-sh/setup-uv")["with"]["version"], PINS["uv"])

    def test_installs_the_examples_project_from_its_lockfile(self):
        self.assertRuns(r"^uv sync --locked$")

    def test_every_other_uv_command_leaves_the_lockfile_alone(self):
        # `uv run` locks and syncs again unless told not to, which could move a pinned tool.
        for command in commands_in(SUITE_JOB, EXAMPLES):
            if command.startswith("uv run"):
                with self.subTest(command=command):
                    self.assertTrue(command.startswith("uv run --no-sync "), command)

    def test_dev_group_holds_each_locked_tool_at_its_exact_version(self):
        text = (REPO / EXAMPLES / "pyproject.toml").read_text(encoding="utf-8")
        for tool in LOCKED_TOOLS:
            with self.subTest(tool=tool):
                self.assertIn(f'"{tool}=={PINS[tool]}"', text)

    def test_checks_the_format(self):
        self.assertRuns(r"^uv run --no-sync ruff format --check$")

    def test_lints(self):
        self.assertRuns(r"^uv run --no-sync ruff check$")

    def test_type_checks_the_source_and_the_tests_strictly(self):
        self.assertRuns(r"^uv run --no-sync mypy --strict src tests$")

    def test_runs_the_tests_with_branch_coverage_and_the_derandomized_profile(self):
        self.assertRuns(r"^uv run --no-sync pytest --cov --cov-branch --hypothesis-profile=ci$")

    def test_audits_the_locked_dependencies(self):
        self.assertRuns(r"^uv export --locked --no-emit-project --output-file requirements\.txt$")
        self.assertRuns(r"^uv run --no-sync pip-audit --strict --disable-pip --requirement requirements\.txt$")

    def test_semgrep_runs_p_python_and_the_local_rules_at_the_pinned_version(self):
        self.assertRuns(rf"pip install semgrep=={re.escape(PINS['semgrep'])}$", directory=".")
        # From the repository root, so the optional .semgrep/ directory is found there.
        self.assertRuns(r"if \[ -d \.semgrep \]; then .*--config \.semgrep", directory=".")
        self.assertRuns(
            rf'^semgrep scan --config p/python "\$\{{local_rules\[@\]\}}" --error --metrics=off {EXAMPLES}$',
            directory=".",
        )

    def test_semgrep_scans_the_test_files(self):
        # A root .semgrepignore replaces semgrep's default list, which skips test directories.
        ignore = REPO / ".semgrepignore"
        test_files = sorted(path.relative_to(REPO).as_posix() for path in (REPO / EXAMPLES / "tests").rglob("*.py"))
        self.assertTrue(test_files)
        self.assertEqual(semgrep_ignored(ignore.read_text(encoding="utf-8"), test_files), [])

    def test_covers_every_python_project_in_the_repository(self):
        # Every pyproject.toml project is a module that gets the full suite, and the suite runs over the examples
        # project only, so a project anywhere else would go unchecked.
        projects = {
            path.parent.relative_to(REPO).as_posix()
            for path in REPO.rglob("pyproject.toml")
            if not {".git", ".venv"} & set(path.relative_to(REPO).parts)
        }
        self.assertEqual(projects, {EXAMPLES})

    def test_lints_and_type_checks_every_python_file_in_the_project(self):
        # ruff and mypy are given the project, and src and tests, so every source file must sit in one of them.
        project = REPO / EXAMPLES
        stray = [
            path.relative_to(project).as_posix()
            for path in project.rglob("*.py")
            if path.relative_to(project).parts[0] not in ("src", "tests", ".venv")
        ]
        self.assertEqual(stray, [])


class PythonAdvisoryChecksWorkflowTests(unittest.TestCase):
    """The griffe advisory check runs on every pull request at its pinned version. It is not checked for blocking."""

    @classmethod
    def setUpClass(cls):
        cls.pins = advisory_pins()

    def test_reference_lists_griffe_as_the_advisory_check(self):
        self.assertEqual(set(self.pins), {"griffe"})

    def test_advisory_tools_are_not_suite_tools(self):
        self.assertFalse(set(self.pins) & set(PINS))

    def test_runs_on_every_pull_request(self):
        self.assertEqual(language_drift.trigger_problems(WORKFLOW, ADVISORY_JOB), [])

    def test_runs_griffe_check_against_the_base_at_the_pinned_version(self):
        version = re.escape(self.pins["griffe"].version)
        # From the repository root: griffe reads the base from a git worktree of the whole repository, so the search
        # path must be the project's src from the root, for the head and the base alike.
        self.assertRegex(
            "\n".join(commands_in(ADVISORY_JOB, ".")),
            rf"(?m)^uvx griffe@{version} check practices --search {EXAMPLES}/src"
            rf' --against "origin/\$BASE_REF" --format github$',
        )
        step = next(step for step in WORKFLOW["jobs"][ADVISORY_JOB]["steps"] if "griffe" in (step.get("run") or ""))
        self.assertEqual(step["env"]["BASE_REF"], "${{ github.base_ref }}")

    def test_fetches_the_history_griffe_compares_against(self):
        self.assertEqual(step_using(ADVISORY_JOB, "actions/checkout")["with"]["fetch-depth"], 0)

    def test_installs_uv_at_the_suite_pin(self):
        self.assertEqual(step_using(ADVISORY_JOB, "astral-sh/setup-uv")["with"]["version"], PINS["uv"])

    def test_never_blocks_the_merge(self):
        # An advisory check reports without blocking (ADR 0006), so it stays out of the suite job.
        step = next(step for step in WORKFLOW["jobs"][ADVISORY_JOB]["steps"] if "griffe" in (step.get("run") or ""))
        self.assertIs(step["continue-on-error"], True)
        self.assertNotIn("griffe", yaml.safe_dump(WORKFLOW["jobs"][SUITE_JOB]))


if __name__ == "__main__":
    unittest.main()
