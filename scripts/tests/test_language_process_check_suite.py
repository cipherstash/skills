"""Tests that the language skills process skill drafts the check suite and follows ADR 0002 on review tools.

The process skill lives in .claude/skills/ and is not published, so the validator does not read it. These tests pin
the decisions of ticket #128: design drafts the check suite and the execution surface, the review-tools gotcha says
what ADR 0002 says, and the ticket breakdown matches CONTRIBUTING.md's Language skills section.
"""

import importlib.util
from pathlib import Path
import re
import unittest


def _load_link_helpers():
    """Load the link helpers from test_contributing_links.py by path, so the test runs however it is started."""
    spec = importlib.util.spec_from_file_location(
        "contributing_links", Path(__file__).with_name("test_contributing_links.py")
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.anchors, module.relative_links


anchors, relative_links = _load_link_helpers()


REPO = Path(__file__).resolve().parents[2]
# Found by prefix, so the tests survive the planned rename to building-language-skills.
SKILL_DIR = next((REPO / ".claude/skills").glob("building-language-*"))
SKILL = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
GOTCHAS = (SKILL_DIR / "references/gotchas.md").read_text(encoding="utf-8")
TICKETS = (SKILL_DIR / "references/tickets.md").read_text(encoding="utf-8")


def gotcha(title):
    """Return the bullet in gotchas.md whose bold title is this, up to the next bullet or heading."""
    marker = f"- **{title}**"
    if marker not in GOTCHAS:
        raise AssertionError(f"gotchas.md has no item {title!r}")
    return GOTCHAS.split(marker, 1)[1].split("\n- ", 1)[0].split("\n#", 1)[0]


class ReviewToolsGotchaTest(unittest.TestCase):
    def test_the_no_installs_gotcha_is_gone(self):
        self.assertNotIn("No installs during a review", GOTCHAS)

    def test_the_gotcha_states_adr_0002(self):
        text = gotcha("Reviews fetch only the suite's tools.")
        for phrase in (
            "docs/adr/0002-reviews-run-no-code-from-the-change-without-a-yes.md",
            "`.<lang>-review-tools/`",
            "pins",
            "install scripts",
            "never installs the change's dependencies",
            "limit",
            "execution surface",
            "yes",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)


def proves(number):
    """Return ticket number's entry under "What each ticket proves" in tickets.md."""
    section = TICKETS.split("## What each ticket proves", 1)[1].split("\n## ", 1)[0]
    items = re.split(r"\n(?=\d+\. \*\*)", section)
    for item in items:
        if item.lstrip().startswith(f"{number}. **"):
            return item
    raise AssertionError(f"tickets.md proves nothing for ticket {number}")


class TicketOneTest(unittest.TestCase):
    def test_the_script_test_runs_no_checks(self):
        self.assertNotIn("runs the language's checks", TICKETS)
        text = proves(1)
        self.assertIn("runs none of the suite's checks", text)
        self.assertIn("matches every quoted block to its source", text)

    def test_ticket_one_builds_the_check_suite(self):
        text = proves(1)
        for phrase in ("`references/checks.md`", "CI job", "over the examples", "drift test"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)


class ReviewTicketsTest(unittest.TestCase):
    def test_ticket_three_quotes_ci_and_fetches_pinned_tools(self):
        text = proves(3)
        for phrase in ("quotes CI", "fetches", "pinned", "`.<lang>-review-tools/`", "execution surface"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_ticket_four_adds_the_repository_standards_step(self):
        text = proves(4)
        for phrase in (
            "Repository standards",
            "missing check is a line in the report",
            "weakened check is a `major` finding",
            "missing untrusted-input test is a `minor` finding",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)


def design_step(title):
    """Return the numbered step under "## Design" in SKILL.md whose bold title starts with title."""
    section = SKILL.split("\n## Design\n", 1)[1].split("\n## ", 1)[0]
    for item in re.split(r"\n(?=\d+\. \*\*)", section):
        if re.match(rf"\s*\d+\. \*\*{re.escape(title)}", item):
            return item
    raise AssertionError(f"SKILL.md has no design step {title!r}")


class ChecklistStepTest(unittest.TestCase):
    def setUp(self):
        self.step = design_step("Write the checklist")

    def test_it_drafts_the_check_suite(self):
        for phrase in (
            "check suite",
            "pinned version",
            "floats",
            "untrusted input",
            "fuzz target or a property test",
            "why neither fits",
            "#87",
            "The spec records",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.step)

    def test_it_lists_the_execution_surface(self):
        for phrase in ("execution surface", "GLOSSARY.md#language-skills", "files and flags", "ticket 3"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.step)

    def test_it_allows_review_areas_beyond_go(self):
        for phrase in ("beyond Go's ten", "CONTRIBUTING.md", "the spec records why"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.step)

    def test_its_done_condition_covers_the_suite_and_surface(self):
        done = self.step.split("Done when", 1)[1]
        self.assertIn("check suite", done)
        self.assertIn("execution surface", done)

    def test_its_done_condition_covers_fixed_fuzz_inputs(self):
        done = self.step.split("Done when", 1)[1]
        self.assertIn("how pull request CI keeps its inputs fixed", done)

    def test_it_skips_the_suite_draft_under_option_two(self):
        self.assertIn("option two", self.step)
        self.assertIn("skips the check suite draft", self.step)


def option_two():
    """Return the paragraph in tickets.md that says what changes when the grill, design step 4, picks option two."""
    for paragraph in TICKETS.split("\n\n"):
        if paragraph.startswith("When the grill, design step 4, decided"):
            return paragraph
    raise AssertionError("tickets.md has no paragraph for the grill's option two")


class OptionTwoTest(unittest.TestCase):
    """With tickets 1 and 2 dropped, no ticket builds the suite, so the paragraph must say what happens to it."""

    def test_it_says_the_pair_has_no_check_suite(self):
        text = option_two()
        for phrase in ("no check suite", "Rust exemption", "CONTRIBUTING.md"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_it_changes_tickets_three_and_four(self):
        text = option_two()
        for phrase in ("Ticket 3 fetches no tools", "limit", "Ticket 4 has no Repository standards step"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)


class LinksTest(unittest.TestCase):
    def test_relative_links_resolve(self):
        for path in (SKILL_DIR / "SKILL.md", SKILL_DIR / "references/gotchas.md", SKILL_DIR / "references/tickets.md"):
            for target in relative_links(path.read_text(encoding="utf-8")):
                with self.subTest(file=path.name, target=target):
                    file, _, anchor = target.partition("#")
                    resolved = (path.parent / file) if file else path
                    self.assertTrue(resolved.exists(), f"{file} does not exist")
                    if anchor and resolved.suffix == ".md":
                        self.assertIn(anchor, anchors(resolved))


if __name__ == "__main__":
    unittest.main()
