# Tests for python-review's seeded-defect fixture, its areas table, and the
# rules its text must keep.
# Run: python3 -m unittest discover -s tests (from the skill directory).
#
# The fixture is a few scripts before (base/) and after (head/) a sample change
# with one planted defect in each of the eleven areas this skill reviews.
# expected-findings.md lists what a correct review must report. These tests keep
# the fixture honest: every location in expected-findings.md is exactly the line
# it quotes, the base is clean, and each planted defect comes from the change.
# A probe with the standard library's ast or tokenize module, or a run of the
# scripts, shows each defect, so the tests need no suite tool. Where ruff, mypy,
# or uv is installed, they also show that the tool reports its defects at the
# head and nothing at the base; without them, those tests are skipped with a
# message.
import ast
import filecmp
import os
import re
import shutil
import subprocess
import sys
import tempfile
import tokenize
import tomllib
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
PRACTICES = SKILL.parent / "python-practices"
GOLANG_REVIEW = SKILL.parent / "golang-review"
REPO = SKILL.parents[3]
FIXTURE = SKILL / "tests" / "fixtures" / "seeded-change"
BASE = FIXTURE / "base"
HEAD = FIXTURE / "head"
EXPECTED = FIXTURE / "expected-findings.md"

# The eleven areas of spec #154's checklist, in its order, as SKILL.md's areas
# table names them, with the priority and the python-practices references the
# design step 2 comment on #64 gives each. Typing is Medium, as grill Q9 says.
SPEC_AREAS = [
    ("1", "Error handling", "High", ["references/errors.md"]),
    ("2", "Correctness and edge cases", "High", ["references/data-modelling.md", "references/errors.md"]),
    ("3", "Testing and coverage", "High", ["references/testing.md"]),
    ("4", "Typing", "Medium", ["references/typing.md"]),
    ("5", "Concurrency and async", "Medium", ["references/async.md"]),
    ("6", "Naming and style", "Medium", ["references/project-structure.md"]),
    ("7", "Security", "Medium", ["references/security.md"]),
    ("8", "Performance", "Medium", ["references/performance.md"]),
    ("9", "Dependency management", "Medium", ["references/dependencies.md"]),
    ("10", "Documentation", "Low", ["references/project-structure.md"]),
    ("11", "Breaking changes", "Low", ["references/project-structure.md", "references/dependencies.md"]),
]
AREAS = [(order, area) for order, area, _, _ in SPEC_AREAS]


def read(path):
    return path.read_text(encoding="utf-8")


def frontmatter(text):
    match = re.match(r"(?s)^---\n(.*?)\n---\n", text)
    if not match:
        raise AssertionError("SKILL.md has no frontmatter")
    return dict(re.findall(r"(?m)^([a-z-]+): (.*)$", match.group(1)))


def areas_table():
    """Return SKILL.md's areas table rows as lists of cell text."""
    section = read(SKILL / "SKILL.md").split("\n## Areas\n", 1)[1].split("\n## ", 1)[0]
    rows = [line for line in section.splitlines() if re.match(r"^\| \d+ \|", line)]
    return [[cell.strip() for cell in row.strip("|").split("|")] for row in rows]


class DescriptionTest(unittest.TestCase):
    def setUp(self):
        self.meta = frontmatter(read(SKILL / "SKILL.md"))
        self.description = self.meta["description"]

    def test_name_matches_the_directory(self):
        self.assertEqual(self.meta["name"], "python-review")

    def test_reviews_python_changes_even_when_the_request_does_not_say_python(self):
        self.assertIn("Reviews a Python change", self.description)
        self.assertIn("even when the request does not say Python", self.description)

    def test_names_area_only_requests(self):
        self.assertIn('"just check the async code"', self.description)

    def test_names_its_limits(self):
        for limit in (
            "Does not write Python (python-practices)",
            "fix findings (review-fix)",
            "post to a pull request (review-post)",
        ):
            with self.subTest(limit=limit):
                self.assertIn(limit, self.description)
        self.assertIn("Read-only", self.description)


class AreasTableTest(unittest.TestCase):
    def test_lists_the_areas_in_priority_order(self):
        self.assertEqual([(row[0], row[1]) for row in areas_table()], AREAS)

    def test_every_area_has_a_step_reference_and_a_practices_reference(self):
        for order, area, _, step, practices in areas_table():
            with self.subTest(area=area):
                link = re.search(r"\]\((references/step-[a-z-]+\.md)\)", step)
                self.assertIsNotNone(link, f"{area}: no step reference in {step!r}")
                step_file = SKILL / link.group(1)
                self.assertTrue(step_file.is_file(), f"{area}: {link.group(1)} does not exist")
                names = re.findall(r"`(references/[a-z-]+\.md)`", practices)
                self.assertTrue(names, f"{area}: no python-practices reference named")
                body = read(step_file)
                self.assertIn(f"Area {order},", body, f"{link.group(1)} does not state its area number")
                for name in names:
                    self.assertTrue((PRACTICES / name).is_file(), f"{area}: python-practices has no {name}")
                    self.assertIn(f"`{name}`", body, f"{link.group(1)} does not name {name}")

    def test_every_step_reference_is_in_the_table(self):
        named = {re.search(r"\]\((references/step-[a-z-]+\.md)\)", row[3]).group(1) for row in areas_table()}
        on_disk = {f"references/{p.name}" for p in (SKILL / "references").glob("step-*.md")}
        self.assertEqual(on_disk, named)

    def test_each_area_has_the_specs_priority_and_practices_references(self):
        for (order, area, priority, practices), row in zip(SPEC_AREAS, areas_table(), strict=True):
            with self.subTest(area=area):
                self.assertEqual(row[2], priority)
                self.assertEqual(re.findall(r"`(references/[a-z-]+\.md)`", row[4]), practices)
                self.assertIn(
                    f"Area {order}, {priority.lower()} priority.",
                    read(SKILL / re.search(r"\((references/step-[a-z-]+\.md)\)", row[3]).group(1)),
                )

    def test_records_why_typing_is_an_area(self):
        # Spec #154 (grill Q9): Typing is the area beyond Go's ten, because a
        # suite tool gives evidence for it and the fixture can plant a defect in it.
        areas = section("SKILL.md", "Areas")
        self.assertIn("Typing is the area beyond golang-review's ten", areas)
        self.assertIn("`mypy --strict` gives evidence for it", areas)
        self.assertIn("a function that returns `Any`", areas)

    def test_the_skill_names_no_area_as_missing_its_step_reference(self):
        for page in ("SKILL.md", "references/output.md", "tests/prompts.md"):
            with self.subTest(page=page):
                self.assertNotIn("no step reference", read(SKILL / page))

    def test_native_extensions_is_read_for_a_pyo3_change(self):
        # The design step 2 comment: these four areas read native-extensions.md
        # when the change is in a native extension.
        paragraph = next(p for p in section("SKILL.md", "Areas").split("\n\n") if "native-extensions.md" in p)
        self.assertIn("python-practices' `references/native-extensions.md`", paragraph)
        for area in ("Error handling", "Typing", "Concurrency and async", "Dependency management"):
            with self.subTest(area=area):
                self.assertIn(area, paragraph)
        for page in ("step-error-handling.md", "step-typing.md", "step-concurrency.md", "step-dependencies.md"):
            with self.subTest(page=page):
                self.assertIn("`references/native-extensions.md`", read(SKILL / "references" / page))


def section(page, heading, level="##"):
    """Return the text under `<level> heading` in page, up to the next heading of that level or higher."""
    text = read(SKILL / page)
    stop = "|".join(re.escape("#" * n + " ") for n in range(1, len(level) + 1))
    match = re.search(rf"(?ms)^{re.escape(level)} {re.escape(heading)}\n(.*?)(?=^(?:{stop})|\Z)", text)
    if not match:
        raise AssertionError(f"{page} has no '{level} {heading}'")
    return match.group(1)


def step(number):
    """Return SKILL.md's numbered step, up to the next one or the next section."""
    text = read(SKILL / "SKILL.md")
    match = re.search(rf"(?ms)^{number}\. \*\*.*?(?=^{number + 1}\. \*\*|^## )", text)
    if not match:
        raise AssertionError(f"SKILL.md has no step {number}")
    return match.group(0)


def severities(page):
    """Return the severity bullets of a finding contract: {severity: text}."""
    contract = page.read_text(encoding="utf-8").split("\n## Finding contract\n", 1)[1].split("\n## ", 1)[0]
    return dict(re.findall(r"(?m)^  - `(critical|major|minor)`: (.+)$", contract))


class FindingContractTest(unittest.TestCase):
    def test_severities_are_copied_from_golang_review(self):
        ours, go = severities(SKILL / "SKILL.md"), severities(GOLANG_REVIEW / "SKILL.md")
        self.assertEqual(set(ours), {"critical", "major", "minor"})
        self.assertEqual(ours["critical"], go["critical"])
        self.assertEqual(ours["minor"], go["minor"])
        # A goroutine is Go's own; only that example changes.
        self.assertEqual(ours["major"], go["major"].replace("a goroutine leak", "a task leak"))

    def test_the_verdict_ends_the_report(self):
        verdict = section("SKILL.md", "Verdict")
        self.assertIn("End the report with `APPROVE` or `REQUEST_CHANGES` and a summary", verdict)
        self.assertIn("`REQUEST_CHANGES` when any finding is critical or major.", verdict)
        shape = re.search(r"(?s)\n````markdown\n(.*?)\n````\n", read(SKILL / "references" / "output.md"))
        self.assertIsNotNone(shape, "output.md has no report template")
        self.assertRegex(shape.group(1), r"\n## Verdict\n\n(APPROVE|REQUEST_CHANGES): [^\n]+$")


class ReadingTest(unittest.TestCase):
    def test_review_step_makes_reading_the_references_mandatory_every_time(self):
        body = step(7)
        self.assertIn("Read its step reference now", body)
        self.assertIn("then each practices reference the table names for it", body)
        self.assertIn("every time", body)
        self.assertIn("An area whose step reference was not read is not reviewed", body)

    def test_loads_python_practices_by_name(self):
        body = step(4)
        self.assertIn("Invoke the `python-practices` skill by name", body)
        self.assertIn("`company-skills:python-practices`", body)

    def test_report_lists_the_files_read_for_each_area(self):
        coverage = section("references/output.md", "Coverage and limits")
        rows = dict(re.findall(r"(?m)^  \d+\. ([^:]+): read (.+)$", coverage))
        for _, area, _, step_cell, practices in areas_table():
            with self.subTest(area=area):
                self.assertIn(area, rows)
                step_name = re.search(r"\]\((references/step-[a-z-]+\.md)\)", step_cell).group(1)
                self.assertIn(f"`{step_name}`", rows[area])
                for name in re.findall(r"`(references/[a-z-]+\.md)`", practices):
                    self.assertIn(f"python-practices `{name}`", rows[area])
        self.assertIn("step reference not read", read(SKILL / "references" / "output.md"))

    def test_no_file_the_review_reads_links_to_python_practices(self):
        # The review reads python-practices through the loaded skill's directory,
        # never by a path out of its own.
        pages = [SKILL / "SKILL.md", *sorted((SKILL / "references").glob("*.md"))]
        for page in pages:
            with self.subTest(page=page.name):
                self.assertNotIn("../python-practices", read(page))
                self.assertNotRegex(read(page), r"\]\(\.\./")


class VersionFloorTest(unittest.TestCase):
    def test_reads_requires_python_before_a_version_sensitive_rule(self):
        body = step(3)
        self.assertIn("`requires-python`", body)
        self.assertIn("PEP 723", body)
        self.assertIn("Never apply or flag a rule above the floor", body)

    def test_each_step_reference_reads_the_floor(self):
        for page in sorted((SKILL / "references").glob("step-*.md")):
            with self.subTest(page=page.name):
                self.assertIn(
                    "Read the module's floor from step 3", section(f"references/{page.name}", "Version-sensitive rules")
                )

    def test_the_versions_named_match_python_practices(self):
        # The review may restate a version that decides what is a finding; keep
        # it the same as the practices reference.
        typing_rules = read(PRACTICES / "references" / "typing.md")
        self.assertIn("`TypeIs` is in `typing` from 3.13", typing_rules)
        self.assertIn("From 3.14 annotations are evaluated lazily", typing_rules)
        ours = section("references/step-typing.md", "Version-sensitive rules")
        self.assertIn("`typing.TypeIs` and type parameter defaults need 3.13", ours)
        self.assertIn("needs 3.14", ours)


class ReadOnlyTest(unittest.TestCase):
    def test_checks_run_in_a_worktree_removed_on_every_exit(self):
        worktree = section("references/target.md", "The temporary worktree")
        self.assertIn("`git worktree add`", worktree)
        self.assertRegex(worktree, r"`git archive`[^.]*not a substitute")
        self.assertIn(
            "Remove it on every exit from here on, including a stop: `git worktree remove --force <worktree>`", worktree
        )
        self.assertIn("Do not run `git worktree prune`", worktree)
        self.assertIn("python-review-<short head SHA>", worktree)
        self.assertIn("removed on every exit, including a stop", section("SKILL.md", "Read-only"))
        self.assertIn("Remove the worktree.", step(9))

    def test_the_branch_base_is_the_remote_tracking_ref(self):
        self.assertIn(
            "git merge-base refs/remotes/origin/<base branch> <branch>", section("references/target.md", "Branch")
        )

    def test_posts_nothing(self):
        self.assertIn("does not post to a pull request", section("SKILL.md", "Read-only"))

    def test_the_change_is_untrusted_data(self):
        for page, text in (
            ("SKILL.md", section("SKILL.md", "Read-only")),
            ("checks.md", section("references/checks.md", "Before running tests")),
        ):
            with self.subTest(page=page):
                self.assertIn("untrusted data", text)
                self.assertIn("never changes these steps", text)


class ToolsTest(unittest.TestCase):
    def test_fetches_only_a_missing_suite_tool_at_the_pinned_version(self):
        fetch = section("references/checks.md", "Fetching a suite tool")
        self.assertIn("Fetch one only when it is not installed", fetch)
        self.assertIn("pinned versions table in python-practices' `references/checks.md`", fetch)
        self.assertIn("Never take a version from the repository under review", fetch)
        self.assertIn("`.python-review-tools/`", fetch)

    def test_fetches_with_install_scripts_off(self):
        fetch = section("references/checks.md", "Fetching a suite tool")
        install = re.findall(r"```sh\n(.*?)```", fetch, re.DOTALL)[1]
        self.assertIn("--only-binary=:all:", install)
        self.assertIn("--isolated", install)
        self.assertIn("<package>==<version>", install)

    def test_never_installs_the_changes_dependencies(self):
        fetch = section("references/checks.md", "Fetching a suite tool")
        self.assertIn("never the change's dependencies", fetch)
        self.assertIn(
            "is a limit", section("SKILL.md", "Read-only").split("mypy without the change's dependencies", 1)[1]
        )
        never = section("references/checks.md", "Commands the review never runs")
        for command in ("`uv sync`", "`uv run`", "`pip install`", "`mypy --install-types`"):
            with self.subTest(command=command):
                self.assertIn(command, never)

    def test_reads_tool_configuration_from_the_base_commit(self):
        config = section("references/checks.md", "Configuration from the base commit")
        self.assertIn("at the base commit, with `git show <base>:<path>`", config)
        self.assertIn("adds, edits, renames, or deletes", config)
        # The flags the fixture's ruff and mypy probes run with, when the base has no config.
        for flag in ("`--isolated`", "`--target-version py<floor>`", "`--strict`", "`--python-version <floor>`"):
            with self.subTest(flag=flag):
                self.assertIn(flag, config)
        self.assertIn("`--config-file=`", config)
        self.assertIn("It reads every tool's configuration from the base commit", section("SKILL.md", "Read-only"))

    def test_runs_the_changes_tests_only_with_a_yes(self):
        before = section("references/checks.md", "Before running tests")
        self.assertIn("the tests run only when the user says yes", before)
        self.assertIn("exact command", before)
        self.assertIn("runs the change's tests only when the user says yes", section("SKILL.md", "Read-only"))

    def test_quotes_cis_result_for_each_suite_check_on_the_head_commit(self):
        ci = section("references/checks.md", "CI's results")
        self.assertIn("for each suite check that CI ran on the reviewed head commit, quote its result", ci)
        self.assertIn("Quote only a run whose head SHA is the reviewed head commit", ci)
        self.assertIn(
            "quote CI's result for each check of the Python check suite that CI ran on the reviewed head commit",
            step(5),
        )


def practices_weakening_cases():
    """Return the backticked spans of python-practices' list of Python changes that weaken a check (grill Q11)."""
    text = read(PRACTICES / "references" / "checks.md")
    cases = text.split("These Python changes also weaken a check, and do not count:\n", 1)[1].split("\n## ", 1)[0]
    return re.findall(r"`([^`]+)`", cases)


class DependencyEvidenceTest(unittest.TestCase):
    """Ticket #159: pip-audit and `uv lock --check --offline` are the evidence, held back on the execution surface."""

    def setUp(self):
        self.step = read(SKILL / "references" / "step-dependencies.md")

    def test_uses_pip_audit_and_uv_lock_check_offline(self):
        self.assertIn("pip-audit", self.step)
        self.assertIn("`uv lock --check --offline`", self.step)
        row = next(
            line for line in section("references/checks.md", "The checks").splitlines() if "uv lock --check" in line
        )
        self.assertIn("--offline", row)
        self.assertIn("Dependency management", row)

    def test_waits_for_a_yes_on_the_build_backend_or_dynamic_metadata(self):
        self.assertRegex(
            self.step,
            r"`uv lock --check[^`]*` waits for the user's yes when the change touches the build backend or dynamic metadata",
        )
        self.assertIn("Otherwise the review reads the `uv.lock` diff", self.step)

    def test_a_script_without_its_lockfile_is_checked_by_its_own_command(self):
        self.assertIn("`uv lock --check --offline --script <file>`", read(SKILL / "references" / "checks.md"))


class BreakingChangesEvidenceTest(unittest.TestCase):
    def setUp(self):
        self.step = read(SKILL / "references" / "step-breaking-changes.md")

    def test_quotes_the_griffe_advisory_check_where_ci_runs_it(self):
        self.assertIn("quote the griffe advisory check's result on the reviewed head commit", self.step)
        self.assertIn("where CI runs it", self.step)

    def test_otherwise_compares_public_names_and_all_at_base_and_head(self):
        self.assertIn("Otherwise, compare the public names and `__all__` at the base and the head", self.step)

    def test_names_the_griffe_command_python_practices_pins(self):
        advisory = read(PRACTICES / "references" / "checks.md").split("\n## Advisory checks\n", 1)[1]
        self.assertIn("griffe check", advisory)
        self.assertIn("python-practices' `references/checks.md`", self.step)


class RepositoryStandardsTest(unittest.TestCase):
    """Ticket #159: compare CI with the check suite, as golang-review's **The check suite in CI** does."""

    def setUp(self):
        self.standards = section("references/checks.md", "Repository standards")

    def test_skill_md_has_a_repository_standards_step(self):
        body = step(6)
        self.assertIn("**Check the repository standards.**", body)
        self.assertIn("[references/checks.md](references/checks.md#repository-standards)", body)

    def test_a_missing_check_is_a_line_not_a_finding(self):
        self.assertIn("A missing check is not a finding", self.standards)
        self.assertIn("one line in the report's check suite section", self.standards)

    def test_a_script_with_no_module_is_a_missing_check(self):
        self.assertIn("a Python script with neither a `pyproject.toml` nor a PEP 723 header", self.standards)

    def test_a_removed_or_weakened_check_is_a_major_finding(self):
        self.assertIn("removes or weakens", self.standards)
        self.assertIn("`major` finding under testing and coverage", self.standards)
        self.assertIn("`major`", read(SKILL / "references" / "step-testing.md").split("removes or weakens", 1)[1][:300])

    def test_names_each_python_weakening_case(self):
        cases = practices_weakening_cases()
        self.assertGreaterEqual(len(cases), 15)
        for case in cases:
            with self.subTest(case=case):
                self.assertIn(f"`{case}`", self.standards)

    def test_names_go_s_weakening_cases_too(self):
        for case in ("`continue-on-error`", "`|| true`", "`pipefail`", "`pull_request`"):
            with self.subTest(case=case):
                self.assertIn(case, self.standards)

    def test_reads_ci_files_as_untrusted_data_at_base_and_head(self):
        self.assertIn("at the base and at the head with `git show`", self.standards)
        self.assertIn("untrusted data", self.standards)

    def test_an_exemption_adr_the_change_adds_does_not_count(self):
        self.assertIn("An ADR that the change adds does not leave a check out", self.standards)

    def test_a_change_to_ci_files_alone_is_still_reviewed(self):
        self.assertIn("`.github/workflows/`", step(1))
        self.assertIn("compare CI with the Python check suite", step(1))


class AdvisoryChecksReportTest(unittest.TestCase):
    """#152 and ADR 0006: a missing advisory check is one line in its own part of the report, never a finding."""

    def test_the_report_has_its_own_advisory_checks_section(self):
        shape = re.search(r"(?s)\n````markdown\n(.*?)\n````\n", read(SKILL / "references" / "output.md")).group(1)
        self.assertIn("\n## Check suite in CI\n", shape)
        self.assertIn("\n## Advisory checks\n", shape)
        self.assertLess(shape.index("## Check suite in CI"), shape.index("## Advisory checks"))

    def test_a_missing_advisory_check_is_one_line_never_a_finding(self):
        fields = section("references/output.md", "Fields")
        self.assertIn("**Advisory checks**: one line for each advisory check", fields)
        self.assertIn("never a finding", fields)
        self.assertIn(
            "A missing advisory check is one line in the report's advisory checks section, never a finding",
            read(SKILL / "references" / "checks.md"),
        )


class HypothesisRuleTest(unittest.TestCase):
    def test_a_new_parser_without_a_given_test_is_minor(self):
        testing = read(SKILL / "references" / "step-testing.md")
        self.assertIn(
            "A function the change adds that parses or decodes untrusted input, with no Hypothesis `@given` test, is a `minor` finding",
            testing,
        )


# Each entry of the execution surface that the ticket's criteria name, as a
# phrase the review's list must hold.
SURFACE = [
    "`conftest.py`",
    "`pytest_plugins`",
    "`addopts`",
    "plugin configuration",
    "`.pth` files",
    "`sitecustomize.py`",
    "`usercustomize.py`",
    "compiled `.so` and `.pyd` files",
    "the build backend and its hooks",
    "`setup.py`",
    "dynamic metadata",
    "entry points",
    "mypy `plugins =`",
    "Rust crate that a pyo3 or maturin package builds",
    "any test file",
]


class ExecutionSurfaceTest(unittest.TestCase):
    def setUp(self):
        self.surface = section("references/checks.md", "The execution surface")

    def test_names_each_entry(self):
        for entry in SURFACE:
            with self.subTest(entry=entry):
                self.assertIn(entry, self.surface)

    def test_agrees_with_python_practices(self):
        practices = (
            read(PRACTICES / "references" / "checks.md").split("\n## Execution surface\n", 1)[1].split("\n## ", 1)[0]
        )
        ours = dict.fromkeys(re.findall(r"(?m)^- (.+?);?$", self.surface))
        theirs = re.findall(r"(?m)^- (.+?)[;.]?$", practices)
        self.assertEqual(len(ours), len(theirs))
        for entry in SURFACE:
            if entry in ("any test file", "plugin configuration", "dynamic metadata"):
                continue
            with self.subTest(entry=entry):
                self.assertIn(entry, practices)

    def test_runs_nothing_that_runs_the_changes_code_until_a_yes(self):
        self.assertIn("before running any tool that runs the change's code", self.surface)
        self.assertIn("ruff, semgrep, pip-audit on an exported lockfile, and griffe", self.surface)
        skill = section("SKILL.md", "Read-only")
        self.assertIn("the review runs no tool that runs the change's code until the user says yes", skill)
        self.assertIn(
            "ruff, semgrep, pip-audit on an exported lockfile, and griffe only read code, so they still run", skill
        )


class FetchSuiteToolTest(unittest.TestCase):
    """The change controls the worktree, so it can commit `.python-review-tools/`.

    A committed `venv/bin/ruff` would then run as the tool, and a failed `mkdir`
    would send the install to the agent's working directory. These tests run the
    setup block from checks.md, then the venv and install commands with stand-in
    `python3` and `pip` that only record what they would do.
    """

    def setUp(self):
        for tool in ("bash", "git"):
            if shutil.which(tool) is None:
                self.skipTest(f"{tool} is not on PATH")
        fetch = section("references/checks.md", "Fetching a suite tool")
        self.fetch_text = fetch
        self.setup_block, self.install_block = re.findall(r"```sh\n(.*?)```", fetch, re.DOTALL)
        venv = re.search(r"create an environment there once, with `([^`]+)`", fetch)
        self.assertIsNotNone(venv)
        self.venv_command = venv.group(1)
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)

    def fetch(self, planted=None, untracked=None, tools=("ruff==0.17.6",)):
        user = self.tmp / "user"
        worktree = self.tmp / "review" / "wt"
        git = [
            "git",
            "-c",
            "user.email=r@example.com",
            "-c",
            "user.name=r",
            "-c",
            "core.hooksPath=/dev/null",
            "-c",
            "commit.gpgsign=false",
        ]
        user.mkdir()
        subprocess.run([*git, "init", "-q"], cwd=user, check=True)
        (user / "app.py").write_text("print('hi')\n", encoding="utf-8")
        if planted:
            path = user / planted
            path.parent.mkdir(parents=True)
            path.write_text("#!/bin/sh\necho planted\n", encoding="utf-8")
        subprocess.run([*git, "add", "-A", "-f"], cwd=user, check=True)
        subprocess.run([*git, "commit", "-qm", "head"], cwd=user, check=True)
        subprocess.run([*git, "worktree", "add", "-q", "--detach", str(worktree), "HEAD"], cwd=user, check=True)
        if untracked:
            (worktree / untracked).mkdir(parents=True)
        record = self.tmp / "calls"
        fake = self.tmp / "fakebin"
        fake.mkdir()
        # A stand-in python3 that makes the venv's python, which records each install.
        (fake / "python3").write_text(
            "#!/bin/sh\n"
            f'printf "venv %s\\n" "$4" >> {record}\n'
            'mkdir -p "$4/bin"\n'
            f'printf \'#!/bin/sh\\nprintf "install %%s %%s\\\\n" "$0" "$9" >> {record}\\n\' > "$4/bin/python"\n'
            'chmod +x "$4/bin/python"\n',
            encoding="utf-8",
        )
        (fake / "python3").chmod(0o755)
        env = dict(os.environ, PATH=f"{fake}{os.pathsep}{os.environ['PATH']}")

        def run(block):
            script = block.replace("<worktree>", str(worktree))
            return subprocess.run(
                ["bash", "-c", script], cwd=user, env=env, capture_output=True, check=False
            ).returncode

        code = run(self.setup_block)
        if code == 0:
            code = run(self.venv_command)
        for tool in tools:
            if code != 0:
                break
            code = run(self.install_block.replace("<package>==<version>", tool))
        calls = record.read_text(encoding="utf-8") if record.exists() else None
        listing = sorted(p.name for p in user.iterdir())
        return code, calls, listing, worktree

    def test_fetches_into_the_worktree_when_the_directory_is_absent(self):
        code, calls, listing, worktree = self.fetch(tools=("ruff==0.17.6", "mypy==2.4.1"))
        venv = worktree / ".python-review-tools" / "venv"
        self.assertEqual(code, 0)
        self.assertEqual(
            calls,
            f"venv {venv}\ninstall {venv / 'bin' / 'python'} ruff==0.17.6\n"
            f"install {venv / 'bin' / 'python'} mypy==2.4.1\n",
        )
        self.assertEqual(listing, [".git", "app.py"])

    def test_refuses_a_tools_directory_the_change_commits(self):
        code, calls, listing, _ = self.fetch(planted=".python-review-tools/venv/bin/ruff")
        self.assertNotEqual(code, 0)
        self.assertIsNone(calls, "the fetch ran")
        self.assertEqual(listing, [".git", ".python-review-tools", "app.py"])

    def test_refuses_a_tools_directory_already_on_disk(self):
        # Uncommitted changes are copied into a worktree made at HEAD, so the
        # head tree alone does not show everything on disk.
        code, calls, listing, _ = self.fetch(untracked=".python-review-tools/venv")
        self.assertNotEqual(code, 0)
        self.assertIsNone(calls, "the fetch ran")
        self.assertEqual(listing, [".git", "app.py"])

    def test_the_blocks_use_absolute_paths_and_never_change_directory(self):
        blocks = self.setup_block + self.install_block + self.venv_command
        self.assertNotIn("$PWD", blocks)
        self.assertNotRegex(blocks, r"(?m)(^|&&|;)\s*cd ")
        self.assertNotIn("mkdir -p", blocks)
        self.assertIn("git -C <worktree> ls-tree HEAD .python-review-tools", self.fetch_text)


class SnapshotCopyTest(unittest.TestCase):
    """The user's git config must not change the patch copied into the worktree."""

    def setUp(self):
        for tool in ("bash", "git"):
            if shutil.which(tool) is None:
                self.skipTest(f"{tool} is not on PATH")
        found = re.search(
            r"(?m)^4\. For uncommitted changes.*?copy the changes in with `([^`]+)`",
            read(SKILL / "references" / "target.md"),
        )
        self.assertIsNotNone(found)
        self.command = found.group(1)
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)

    def test_copies_the_changes_whatever_the_users_diff_config(self):
        user = self.tmp / "user"
        worktree = self.tmp / "review" / "wt"
        git = [
            "git",
            "-c",
            "user.email=r@example.com",
            "-c",
            "user.name=r",
            "-c",
            "core.hooksPath=/dev/null",
            "-c",
            "commit.gpgsign=false",
        ]
        user.mkdir()
        subprocess.run([*git, "init", "-q"], cwd=user, check=True)
        (user / "app.py").write_text("VERSION = 1\n", encoding="utf-8")
        subprocess.run([*git, "add", "-A"], cwd=user, check=True)
        subprocess.run([*git, "commit", "-qm", "head"], cwd=user, check=True)
        subprocess.run([*git, "worktree", "add", "-q", "--detach", str(worktree), "HEAD"], cwd=user, check=True)
        subprocess.run(["git", "config", "diff.noprefix", "true"], cwd=user, check=True)
        subprocess.run(["git", "config", "color.diff", "always"], cwd=user, check=True)
        (user / "pkg").mkdir()
        (user / "pkg" / "new.py").write_text("X = 1\n", encoding="utf-8")
        subprocess.run(["git", "add", "pkg/new.py"], cwd=user, check=True)
        (user / "app.py").write_text("VERSION = 2\n", encoding="utf-8")

        result = subprocess.run(
            ["bash", "-c", self.command.replace("<worktree>", str(worktree))],
            cwd=user,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((worktree / "pkg" / "new.py").is_file())
        self.assertFalse((worktree / "new.py").exists())
        self.assertIn("VERSION = 2", (worktree / "app.py").read_text(encoding="utf-8"))


# One expected finding: "## P1 · major · typing" and, below it,
# "- Location: `head/<path>:<line>`" and "- Line: `<text quoted from that line>`".
# A finding on a line the change deletes is located at the base, as
# "- Location: `base/<path>:<line>` (deleted)".
FINDING_RE = re.compile(r"(?m)^## (P\d+) · (critical|major|minor) · (.+)$")
LOCATION_RE = re.compile(r"(?m)^- Location: `(head|base)/([^`:]+):(\d+)`( \(deleted\))?$")
LINE_RE = re.compile(r"(?m)^- Line: `(.+)`$")

# The ruff rule each planted defect shows as, by area, when ruff runs as the
# review runs it on a module with no config. The other areas have none.
RUFF_CODES = {
    "error handling": "B904",
    "concurrency and async": "RUF006",
    "security": "S501",
    "performance": "PERF401",
}


def expected_findings():
    """Return {id: dict(area, severity, side, path, line, deleted, quoted)} from expected-findings.md."""
    text = read(EXPECTED)
    headings = list(FINDING_RE.finditer(text))
    findings = {}
    for index, heading in enumerate(headings):
        end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
        body = text[heading.end() : end]
        location, quoted = LOCATION_RE.search(body), LINE_RE.search(body)
        if heading.group(1) in findings:
            raise AssertionError(f"expected-findings.md lists {heading.group(1)} twice")
        findings[heading.group(1)] = {
            "area": heading.group(3).strip(),
            "severity": heading.group(2),
            "side": location.group(1) if location else None,
            "path": location.group(2) if location else None,
            "line": int(location.group(3)) if location else None,
            "deleted": bool(location and location.group(4)),
            "quoted": quoted.group(1) if quoted else None,
        }
    return findings


def finding(area):
    found = [f for f in expected_findings().values() if f["area"] == area]
    if len(found) != 1:
        raise AssertionError(f"expected-findings.md has {len(found)} {area} findings")
    return found[0]


def changed_files(base=BASE, head=HEAD):
    """Return the paths, relative to the fixture's trees, of files that differ between base and head."""

    def files(root):
        return {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()}

    left, right = files(base), files(head)
    changed = left ^ right
    changed |= {path for path in left & right if not filecmp.cmp(base / path, head / path, shallow=False)}
    return sorted(changed)


def script_metadata(path):
    """Return the TOML of a PEP 723 `# /// script` block, parsed, or None."""
    match = re.search(r"(?ms)^# /// script$\s(?P<content>(^#(| .*)$\s)+)^# ///$", read(path))
    if not match:
        return None
    toml = "".join(line[2:] if line.startswith("# ") else line[1:] for line in match.group("content").splitlines(True))
    return tomllib.loads(toml)


def tree(path):
    return ast.parse(read(path))


def raises_without_from_in_except(path):
    """Return the line numbers of each `raise X(...)` with no `from` inside an `except` block."""
    lines = []
    for node in ast.walk(tree(path)):
        if isinstance(node, ast.ExceptHandler):
            for inner in ast.walk(node):
                if isinstance(inner, ast.Raise) and inner.exc is not None and inner.cause is None:
                    lines.append(inner.lineno)
    return lines


def returns_of_json_loads(path):
    """Return {function name: annotation} for each function that returns json.loads(...) directly."""
    found = {}
    for node in ast.walk(tree(path)):
        if isinstance(node, ast.FunctionDef):
            for inner in ast.walk(node):
                if (
                    isinstance(inner, ast.Return)
                    and isinstance(inner.value, ast.Call)
                    and ast.unparse(inner.value.func) == "json.loads"
                ):
                    found[node.name] = ast.unparse(node.returns) if node.returns else None
    return found


def python_files(root):
    return sorted(root.rglob("*.py"))


def discarded_create_tasks(path):
    """Return the line of each `asyncio.create_task(...)` whose result nothing keeps."""
    return [
        node.lineno
        for node in ast.walk(tree(path))
        if isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Call)
        and ast.unparse(node.value.func) == "asyncio.create_task"
    ]


def verify_false(path):
    """Return the line of each call that passes `verify=False`."""
    return [
        node.lineno
        for node in ast.walk(tree(path))
        if isinstance(node, ast.Call)
        and any(
            k.arg == "verify" and isinstance(k.value, ast.Constant) and k.value.value is False for k in node.keywords
        )
    ]


def append_loops(path):
    """Return the line of each `append` call that is the whole body of a `for` loop."""
    return [
        node.body[0].lineno
        for node in ast.walk(tree(path))
        if isinstance(node, ast.For)
        and len(node.body) == 1
        and isinstance(node.body[0], ast.Expr)
        and isinstance(node.body[0].value, ast.Call)
        and isinstance(node.body[0].value.func, ast.Attribute)
        and node.body[0].value.func.attr == "append"
    ]


def single_quoted_strings(path):
    """Return the line of each string literal written with single quotes, which ruff format rewrites."""
    with path.open(encoding="utf-8") as source:
        return [
            token.start[0]
            for token in tokenize.generate_tokens(source.readline)
            if token.type == tokenize.STRING and token.string.lstrip("rbuRBUfF").startswith("'")
        ]


def function(path, name):
    return next(n for n in ast.walk(tree(path)) if isinstance(n, ast.FunctionDef) and n.name == name)


def module_all(path):
    """Return the names in a module's `__all__`, or None."""
    for node in tree(path).body:
        if isinstance(node, ast.Assign) and [ast.unparse(t) for t in node.targets] == ["__all__"]:
            return ast.literal_eval(node.value)
    return None


def run_script(path, *args, cwd, isolated=True):
    """Run a fixture script with no bytecode written, and return (exit status, stdout, stderr)."""
    # -I leaves the script's directory off sys.path. A script that imports its
    # neighbour, as an importer of a public name does, needs it, so it runs
    # with -E -s instead.
    flags = ["-I"] if isolated else ["-E", "-s"]
    result = subprocess.run(
        [sys.executable, "-B", *flags, str(path), *args], capture_output=True, text=True, cwd=cwd, check=False
    )
    return result.returncode, result.stdout, result.stderr


class ExpectedFindingsTest(unittest.TestCase):
    def test_lists_one_finding_for_each_area(self):
        self.assertEqual(sorted(f["area"] for f in expected_findings().values()), sorted(a.lower() for _, a in AREAS))

    def test_findings_are_numbered_most_severe_first(self):
        order = {"critical": 0, "major": 1, "minor": 2}
        findings = expected_findings()
        self.assertEqual(list(findings), [f"P{n}" for n in range(1, len(findings) + 1)])
        severities = [order[f["severity"]] for f in findings.values()]
        self.assertEqual(severities, sorted(severities))

    def test_each_finding_quotes_the_line_it_names(self):
        for key, f in expected_findings().items():
            with self.subTest(id=key):
                self.assertIsNotNone(f["side"], f"{key}: no '- Location: `head/<path>:<line>`'")
                self.assertIsNotNone(f["quoted"], f"{key}: no '- Line: `<text>`'")
                # A base location is for a deleted line only, and says so.
                self.assertEqual(f["side"] == "base", f["deleted"], f"{key}: a base location must say (deleted)")
                lines = read(FIXTURE / f["side"] / f["path"]).splitlines()
                self.assertLessEqual(f["line"], len(lines))
                # The whole line, not a substring, so a fix on the same line fails here.
                self.assertEqual(lines[f["line"] - 1].strip(), f["quoted"])
                if f["deleted"]:
                    head = [line.strip() for line in read(HEAD / f["path"]).splitlines()]
                    self.assertNotIn(f["quoted"], head, f"{key}: the deleted line is still at the head")

    def test_findings_point_at_changed_files(self):
        for key, f in expected_findings().items():
            with self.subTest(id=key):
                self.assertIn(f["path"], changed_files())

    def test_the_change_touches_only_the_planted_files(self):
        # price_list.py is unchanged: it is the importer the breaking change breaks.
        self.assertEqual(changed_files(), ["get_rates.py", "postage.py"])
        self.assertTrue((BASE / "price_list.py").is_file())

    def test_each_script_declares_its_floor(self):
        # The review reads requires-python from the PEP 723 header before any
        # version-sensitive rule. postage.py has no dependencies, so mypy sees
        # every type in it; get_rates.py needs httpx, which the review never installs.
        expected = {
            BASE / "postage.py": [],
            HEAD / "postage.py": [],
            HEAD / "get_rates.py": ["httpx"],
        }
        for path, dependencies in expected.items():
            with self.subTest(path=path.relative_to(FIXTURE).as_posix()):
                metadata = script_metadata(path)
                self.assertEqual(metadata, {"requires-python": ">=3.12", "dependencies": dependencies})

    def test_one_script_has_no_module(self):
        # A script with neither a pyproject.toml nor a PEP 723 header is a
        # missing check in the report, never a finding.
        for root in (BASE, HEAD):
            with self.subTest(tree=root.name):
                self.assertIsNone(script_metadata(root / "price_list.py"))
        self.assertRegex(read(EXPECTED), r"(?m)^- .*`price_list\.py`.*neither a `pyproject\.toml` nor a PEP 723 header")

    def test_the_fixture_is_scripts_not_a_project(self):
        # Every pyproject.toml project gets the full suite, and the suite's drift
        # test checks that the examples project is the only one.
        for name in ("pyproject.toml", "setup.py", "setup.cfg", "ruff.toml", ".ruff.toml", "mypy.ini", "uv.lock"):
            with self.subTest(name=name):
                self.assertEqual(list(FIXTURE.rglob(name)), [])

    def test_the_fixture_has_no_ci(self):
        # So every suite check and the advisory check are missing: lines in the
        # report, not findings.
        self.assertEqual(list(FIXTURE.rglob(".github")), [])
        missing = read(EXPECTED).split("\n## Check suite in CI\n", 1)[1].split("\n## ", 1)[0]
        for check in (
            "ruff format --check",
            "ruff check",
            "mypy --strict",
            "pytest --cov --cov-branch",
            "pip-audit",
            "semgrep",
        ):
            with self.subTest(check=check):
                self.assertIn(f"`{check}`", missing)
        self.assertIn("`griffe check`", read(EXPECTED).split("\n## Advisory checks\n", 1)[1].split("\n## ", 1)[0])

    def test_the_version_case_needs_a_later_python_to_drop_its_quotes(self):
        # Must not report: the quoted annotation names an import under
        # TYPE_CHECKING. Below 3.14 the quotes are needed, so a review that
        # applies the 3.14 rule at this 3.12 floor reports it wrongly.
        text = read(EXPECTED)
        self.assertRegex(text, r"(?m)^- `head/postage\.py:\d+`.*3\.14")
        line = int(re.search(r"(?m)^- `head/postage\.py:(\d+)`.*3\.14", text).group(1))
        source = read(HEAD / "postage.py")
        self.assertIn('"Mapping[str, int]"', source.splitlines()[line - 1])
        self.assertIn("if TYPE_CHECKING:\n    from collections.abc import Mapping\n", source)


class PlantedDefectTest(unittest.TestCase):
    """The probes show each defect at the head and not at the base, with no suite tool."""

    def test_the_lost_cause_comes_from_the_change(self):
        f = finding("error handling")
        self.assertEqual(raises_without_from_in_except(BASE / "postage.py"), [])
        self.assertEqual(raises_without_from_in_except(HEAD / f["path"]), [f["line"]])

    def test_the_off_by_one_charge_comes_from_the_change(self):
        # Correctness: a parcel of exactly 200 g is two started 100 g, as the
        # docstring says, and the base charges two. The head charges three.
        f = finding("correctness and edge cases")
        self.assertEqual(f["path"], "postage.py")
        self.assertIn("grams // 100 + 1", f["quoted"])
        with tempfile.TemporaryDirectory() as tmp:
            rates = Path(tmp) / "r.json"
            rates.write_text('{"local": 45}', encoding="utf-8")
            self.assertEqual(run_script(BASE / "postage.py", "local", "200", cwd=tmp)[:2], (0, "90\n"))
            self.assertEqual(run_script(HEAD / "postage.py", str(rates), "local", "200", cwd=tmp)[:2], (0, "135\n"))
            # Between the multiples of 100 g the two agree.
            self.assertEqual(run_script(BASE / "postage.py", "local", "250", cwd=tmp)[:2], (0, "135\n"))
            self.assertEqual(run_script(HEAD / "postage.py", str(rates), "local", "250", cwd=tmp)[:2], (0, "135\n"))

    def test_the_untested_decoder_comes_from_the_change(self):
        # Testing: the change adds a function that decodes a file, which is
        # untrusted input, and no Hypothesis @given test for it.
        f = finding("testing and coverage")
        self.assertEqual(
            f["quoted"],
            read(HEAD / f["path"]).splitlines()[function(HEAD / f["path"], "load_rates").lineno - 1].strip(),
        )
        self.assertEqual(returns_of_json_loads(BASE / "postage.py"), {})
        for path in python_files(HEAD):
            with self.subTest(path=path.name):
                self.assertNotIn("hypothesis", read(path))
                self.assertNotIn("@given", read(path))

    def test_the_any_return_comes_from_the_change(self):
        f = finding("typing")
        self.assertEqual(returns_of_json_loads(BASE / "postage.py"), {})
        found = returns_of_json_loads(HEAD / f["path"])
        self.assertEqual(list(found.values()), ["dict[str, int]"])
        self.assertIn("json.loads(", f["quoted"])

    def test_a_string_rate_gives_a_wrong_postage_with_no_error(self):
        # The typing finding's trigger and consequence: a rate file whose value
        # is a string passes through as dict[str, int], and the postage is the
        # string repeated, printed as if it were a price.
        with tempfile.TemporaryDirectory() as tmp:
            rates = Path(tmp) / "rates.json"
            rates.write_text('{"local": "45"}', encoding="utf-8")
            status, out, err = run_script(HEAD / "postage.py", str(rates), "local", "250", cwd=tmp)
        self.assertEqual((status, out), (0, "454545\n"), err)

    def test_the_base_still_prices_a_parcel(self):
        with tempfile.TemporaryDirectory() as tmp:
            status, out, err = run_script(BASE / "postage.py", "local", "250", cwd=tmp)
        self.assertEqual((status, out), (0, "135\n"), err)

    def test_the_dropped_task_comes_from_the_change(self):
        f = finding("concurrency and async")
        self.assertEqual(f["path"], "get_rates.py")
        for path in python_files(BASE):
            self.assertEqual(discarded_create_tasks(path), [])
        self.assertEqual(discarded_create_tasks(HEAD / f["path"]), [f["line"]])
        # Nothing awaits the task before the client closes and the function returns.
        body = ast.unparse(function_async(HEAD / f["path"], "get_all"))
        self.assertNotIn("TaskGroup", body)
        self.assertNotIn("gather", body)

    def test_the_format_change_comes_from_the_change(self):
        f = finding("naming and style")
        for path in python_files(BASE):
            self.assertEqual(single_quoted_strings(path), [])
        self.assertEqual(single_quoted_strings(HEAD / f["path"]), [f["line"]])

    def test_the_skipped_tls_check_comes_from_the_change(self):
        f = finding("security")
        for path in python_files(BASE):
            self.assertEqual(verify_false(path), [])
        self.assertEqual(verify_false(HEAD / f["path"]), [f["line"]])

    def test_the_append_loop_comes_from_the_change(self):
        f = finding("performance")
        for path in python_files(BASE):
            self.assertEqual(append_loops(path), [])
        self.assertEqual(append_loops(HEAD / f["path"]), [f["line"]])

    def test_the_unlocked_dependency_comes_from_the_change(self):
        # The new script declares a dependency with no version and commits no
        # <file>.lock, which uv lock --script would write beside it.
        f = finding("dependency management")
        self.assertEqual(f["quoted"], '# dependencies = ["httpx"]')
        self.assertFalse((HEAD / f"{f['path']}.lock").exists())
        self.assertEqual([p.name for p in FIXTURE.rglob("*.lock")], [])
        self.assertFalse((BASE / f["path"]).exists())

    def test_the_stale_docstring_comes_from_the_change(self):
        # Documentation: the change makes main read a rate file and several
        # weights, and leaves its docstring as it was.
        f = finding("documentation")
        base_main, head_main = function(BASE / "postage.py", "main"), function(HEAD / f["path"], "main")
        self.assertEqual(ast.get_docstring(base_main), ast.get_docstring(head_main))
        self.assertEqual(head_main.body[0].lineno, f["line"])
        self.assertNotEqual(ast.unparse(base_main.body[1]), ast.unparse(head_main.body[1]))
        self.assertIn("rates_file", ast.unparse(head_main.body[1]))

    def test_the_removed_public_name_comes_from_the_change(self):
        # Breaking changes: the base exports RATES, the head deletes it, and the
        # unchanged price_list.py still imports it.
        f = finding("breaking changes")
        self.assertEqual((f["side"], f["deleted"]), ("base", True))
        self.assertIn("RATES", module_all(BASE / "postage.py"))
        self.assertNotIn("RATES", module_all(HEAD / "postage.py"))
        self.assertTrue(f["quoted"].startswith("RATES = "))
        with tempfile.TemporaryDirectory() as tmp:
            base = run_script(BASE / "price_list.py", cwd=tmp, isolated=False)
            head = run_script(HEAD / "price_list.py", cwd=tmp, isolated=False)
        self.assertEqual(base[0], 0, base[2])
        self.assertIn("local: 45", base[1])
        self.assertNotEqual(head[0], 0)
        self.assertIn("ImportError: cannot import name 'RATES'", head[2])


def function_async(path, name):
    return next(n for n in ast.walk(tree(path)) if isinstance(n, ast.AsyncFunctionDef) and n.name == name)


def suite_families():
    """Return the ruff rule families python-practices' check suite selects."""
    checks = read(PRACTICES / "references" / "checks.md")
    line = re.search(r"(?m)^- \*\*Lint\*\*: .*$", checks).group(0)
    families = re.search(r"Select at least the rule families (.*?)\.", line).group(1)
    return re.findall(r"`([A-Z]+)`", families)


class ToolProbeTest(unittest.TestCase):
    """ruff, mypy, and uv, run as the review runs them on a module with no config, report each defect at the head only.

    They are not part of the validate job, so these tests skip when the tool is
    not on PATH. The probes above always run.
    """

    def tool(self, name):
        path = shutil.which(name)
        if path is None:
            self.skipTest(f"{name} is not on PATH")
        return path

    def ruff(self, *args):
        ruff = self.tool("ruff")
        return subprocess.run(
            [ruff, *args, "--isolated", "--no-cache", "--target-version", "py312"],
            capture_output=True,
            text=True,
            check=False,
        )

    def ruff_check(self, root):
        return self.ruff(
            "check",
            "--no-fix",
            "--output-format=concise",
            "--select",
            ",".join(suite_families()),
            *map(str, python_files(root)),
        )

    def mypy(self, path):
        mypy = self.tool("mypy")
        with tempfile.TemporaryDirectory() as cache:
            return subprocess.run(
                [mypy, "--config-file=", "--strict", "--python-version", "3.12", f"--cache-dir={cache}", str(path)],
                capture_output=True,
                text=True,
                check=False,
            )

    def test_ruff_reports_each_planted_rule_and_nothing_else(self):
        base = self.ruff_check(BASE)
        self.assertEqual(base.returncode, 0, base.stdout)
        head = self.ruff_check(HEAD)
        reported = sorted(re.findall(r"(?m)^.*/([a-z_]+\.py):(\d+):\d+: ([A-Z]+\d+) ", head.stdout))
        expected = sorted(
            (finding(area)["path"], str(finding(area)["line"]), code) for area, code in RUFF_CODES.items()
        )
        self.assertEqual(reported, expected, head.stdout)

    def test_ruff_format_changes_only_the_planted_line(self):
        base = self.ruff("format", "--check", *map(str, python_files(BASE)))
        self.assertEqual(base.returncode, 0, base.stdout)
        f = finding("naming and style")
        for path in python_files(HEAD):
            with self.subTest(path=path.name):
                result = self.ruff("format", "--check", "--diff", str(path))
                if path.name != f["path"]:
                    self.assertEqual(result.returncode, 0, result.stdout)
                    continue
                self.assertNotEqual(result.returncode, 0)
                removed = re.findall(r"(?m)^-(?!--)(.*)$", result.stdout)
                self.assertEqual([line.strip() for line in removed], [f["quoted"]], result.stdout)

    def test_mypy_reports_only_the_any_return(self):
        base = self.mypy(BASE / "postage.py")
        self.assertEqual(base.returncode, 0, base.stdout)
        head = self.mypy(HEAD / "postage.py")
        line = finding("typing")["line"]
        errors = re.findall(r"(?m)^.*postage\.py:(\d+): error: .*\[([a-z-]+)\]$", head.stdout)
        self.assertEqual(errors, [(str(line), "no-any-return")], head.stdout)

    def test_mypy_on_the_new_script_reports_at_most_its_missing_dependency(self):
        # Without httpx installed, mypy's import-not-found is a limit of the
        # review, not a finding. With it, mypy passes.
        result = self.mypy(HEAD / "get_rates.py")
        errors = re.findall(r"(?m)^.*get_rates\.py:\d+: error: (.*)$", result.stdout)
        for error in errors:
            with self.subTest(error=error):
                self.assertRegex(error, r'module named "httpx"\s+\[import-not-found\]$')

    def test_uv_lock_check_finds_no_lockfile_for_the_new_script(self):
        uv = self.tool("uv")
        with tempfile.TemporaryDirectory() as tmp:
            script = Path(tmp) / "get_rates.py"
            shutil.copy(HEAD / "get_rates.py", script)
            env = dict(os.environ, UV_NO_CONFIG="1", UV_OFFLINE="1", UV_PYTHON_DOWNLOADS="never")
            result = subprocess.run(
                [uv, "lock", "--check", "--offline", "--script", str(script)],
                capture_output=True,
                text=True,
                cwd=tmp,
                env=env,
                check=False,
            )
            self.assertEqual(sorted(p.name for p in Path(tmp).iterdir()), ["get_rates.py"])
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Unable to find lockfile", result.stderr)


class FixtureExclusionTest(unittest.TestCase):
    """The fixture holds planted defects, so neither the check suite nor any ruff configuration covers it."""

    def test_the_suite_job_leaves_the_fixture_out(self):
        workflow = read(REPO / ".github" / "workflows" / "validate.yml")
        job = workflow.split("\n  python-check-suite:\n", 1)[1].split("\n\n  #", 1)[0]
        self.assertNotIn("python-review", job)
        self.assertIn("working-directory: plugins/company-skills/skills/python-practices/examples", job)

    def test_no_ruff_configuration_covers_the_fixture(self):
        # ruff takes its configuration from the closest ruff.toml, .ruff.toml, or
        # pyproject.toml with a [tool.ruff] table above a file.
        configs = [
            path.parent
            for name in ("ruff.toml", ".ruff.toml", "pyproject.toml")
            for path in REPO.rglob(name)
            if not {".git", ".venv"} & set(path.relative_to(REPO).parts)
            and (name != "pyproject.toml" or "[tool.ruff" in read(path))
        ]
        self.assertTrue(configs, "found no ruff configuration at all")
        for directory in configs:
            with self.subTest(config=directory.relative_to(REPO).as_posix()):
                self.assertFalse(FIXTURE.is_relative_to(directory))


# Words the fixture declares that are also ordinary English or Python words, so
# they may appear in the skill text for their own sake.
COMMON_WORDS = {"__init__", "__all__", "main"}

# Values from the fixture's code and expected results that are not declared
# names but would still give its answers away.
FIXTURE_LITERALS = ["454545", "1.5kg", "rates.json", "rates-<n>.json", "per started 100 g"]


def fixture_terms():
    """Return the names, paths, and values that identify the fixture."""
    terms = set(FIXTURE_LITERALS)
    for root in (BASE, HEAD):
        for path in root.rglob("*.py"):
            tree = ast.parse(read(path))
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    terms.add(node.name)
                elif isinstance(node, ast.Assign):
                    terms.update(target.id for target in node.targets if isinstance(target, ast.Name))
            terms.add(path.relative_to(root).as_posix())
    return terms - COMMON_WORDS


class AnswerKeyTest(unittest.TestCase):
    """The skill text must not contain the fixture's answers.

    A run of the skill against the fixture shows that the skill finds the
    planted defects only if nothing it reads names them.
    """

    def test_derives_the_fixture_terms(self):
        terms = fixture_terms()
        for term in (
            "postage.py",
            "get_rates.py",
            "price_list.py",
            "parse_grams",
            "load_rates",
            "get_all",
            "PostageError",
        ):
            self.assertIn(term, terms)

    def test_skill_text_does_not_name_the_fixture(self):
        pattern = re.compile(
            r"(?<![\w/-])("
            + "|".join(re.escape(t) for t in sorted(fixture_terms(), key=len, reverse=True))
            + r")(?![\w-])"
        )
        pages = [SKILL / "SKILL.md", *sorted((SKILL / "references").glob("*.md"))]
        pages += [PRACTICES / "SKILL.md", *sorted((PRACTICES / "references").glob("*.md"))]
        found = []
        for page in pages:
            for number, line in enumerate(read(page).splitlines(), 1):
                found += [f"{page.relative_to(SKILL.parent)}:{number}: {m.group(1)}" for m in pattern.finditer(line)]
        self.assertEqual(found, [], "fixture terms in the skill text:\n" + "\n".join(found))


def cases(heading):
    """Return the bullet text under a heading of tests/prompts.md."""
    text = read(SKILL / "tests" / "prompts.md")
    body = text.split(f"\n## {heading}\n", 1)[1].split("\n## ", 1)[0]
    return re.findall(r"(?m)^- (.+)$", body)


class BehaviourCasesTest(unittest.TestCase):
    def test_should_activate_has_each_kind_of_request(self):
        activate = cases("Should activate")
        for kind in ("Direct:", "Indirect:", "Area only:", "No target:"):
            with self.subTest(kind=kind):
                self.assertTrue(any(case.startswith(kind) for case in activate), f"no '{kind}' case")
        area_only = next(case for case in activate if case.startswith("Area only:"))
        self.assertIn("just check", area_only.lower())
        indirect = next(case for case in activate if case.startswith("Indirect:"))
        self.assertNotIn("review", indirect.split('"')[1].lower())
        self.assertNotIn("python", indirect.split('"')[1].lower())

    def test_fixture_locations_in_the_cases_are_expected_findings(self):
        # A case that names a fixture line must name one expected-findings.md lists.
        locations = {f"{f['path']}:{f['line']}" for f in expected_findings().values()}
        named = re.findall(r"`((?:postage|get_rates|price_list)\.py:\d+)`", read(SKILL / "tests" / "prompts.md"))
        self.assertTrue(named)
        for location in named:
            with self.subTest(location=location):
                self.assertIn(location, locations)

    def test_should_not_activate_has_a_request_to_write_python(self):
        self.assertTrue(any(case.startswith("Writing Python:") for case in cases("Should not activate")))

    def test_a_request_with_no_target_stops_without_a_question(self):
        no_target = next(case for case in cases("Should activate") if case.startswith("No target:"))
        self.assertIn("asks no question", no_target)


if __name__ == "__main__":
    unittest.main()
