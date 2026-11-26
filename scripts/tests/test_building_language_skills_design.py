"""Tests that the language skills process skill drafts the check suite in design and follows ADR 0002.

The process skill lives in .claude/skills/ and is not published, so the validator does not read it. These tests pin
ticket #128: design step 2 drafts the check suite and lists the execution surface, the review-tools gotcha states
ADR 0002's rule, and the ticket breakdown matches CONTRIBUTING.md's Language skills section.
"""

import importlib.util
from pathlib import Path
import re
import unittest


def _load_link_helpers():
    """Load the link helpers from test_contributing_links.py by path, however the tests are started."""
    spec = importlib.util.spec_from_file_location(
        "contributing_links", Path(__file__).with_name("test_contributing_links.py")
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.anchors, module.relative_links


anchors, relative_links = _load_link_helpers()


REPO = Path(__file__).resolve().parents[2]
# Found by prefix, so the tests survive the planned rename to building-language-skills (#130).
SKILL_DIR = next((REPO / ".claude/skills").glob("building-language-*"))
SKILL = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
GOTCHAS = (SKILL_DIR / "references/gotchas.md").read_text(encoding="utf-8")
TICKETS = (SKILL_DIR / "references/tickets.md").read_text(encoding="utf-8")


def gotcha(title):
    """Return the gotchas.md bullet whose bold title is this, up to the next bullet or heading."""
    marker = f"- **{title}**"
    if marker not in GOTCHAS:
        raise AssertionError(f"gotchas.md has no item {title!r}")
    return re.split(r"\n(?:- |#)", GOTCHAS.split(marker, 1)[1], maxsplit=1)[0]


class ReviewToolsGotchaTest(unittest.TestCase):
    def test_the_contradicting_gotcha_is_gone(self):
        self.assertNotIn("No installs during a review", GOTCHAS)
        self.assertNotIn("installs nothing", GOTCHAS)

    def test_it_states_adr_0002(self):
        text = gotcha("A review fetches only its suite's tools.")
        for phrase in (
            "docs/adr/0002-reviews-run-no-code-from-the-change-without-a-yes.md",
            "versions the practices skill pins",
            "`.<lang>-review-tools/`",
            "install scripts turned off",
            "never installs the change's dependencies",
            "limit of the review",
            "configuration from the base commit",
            "execution surface",
            "until the user says yes",
            "**Criterion** for ticket 3",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)


def proves(number):
    """Return ticket number's entry under "What each ticket proves" in tickets.md."""
    section = TICKETS.split("\n## What each ticket proves\n", 1)[1].split("\n## ", 1)[0]
    for item in re.split(r"\n(?=\d+\. \*\*)", section):
        if item.lstrip().startswith(f"{number}. **"):
            return item
    raise AssertionError(f"tickets.md proves nothing for ticket {number}")


class TicketOneTest(unittest.TestCase):
    def test_its_script_test_runs_no_checks(self):
        self.assertNotIn("runs the language's checks", TICKETS)
        text = proves(1)
        self.assertIn("runs none of the suite's checks", text)
        self.assertIn("matches every quoted block to its source", text)

    def test_it_builds_the_check_suite(self):
        text = proves(1)
        for phrase in ("`references/checks.md`", "pinned-versions table", "CI job", "over the examples", "drift test"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)


class ReviewTicketsTest(unittest.TestCase):
    def test_ticket_three_quotes_ci_and_fetches_pinned_tools(self):
        text = proves(3)
        for phrase in (
            "quotes CI's result",
            "fetches only",
            "version the practices skill pins",
            "`.<lang>-review-tools/`",
            "install scripts off",
            "execution surface",
            "until the user says yes",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_ticket_four_adds_the_repository_standards_step(self):
        text = proves(4)
        for phrase in (
            "Repository standards step",
            "A missing check is a line in the report, not a finding",
            "A weakened check is a `major` finding",
            "A missing untrusted-input test is a `minor` finding",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)


def option_two():
    """Return the tickets.md paragraphs on design step 1's option two, which drops tickets 1 and 2."""
    found = [p for p in TICKETS.split("\n\n") if p.startswith(("When design step 1 decided", "Under option two"))]
    if not found:
        raise AssertionError("tickets.md has no paragraph for design step 1's option two")
    return "\n\n".join(found)


class OptionTwoTest(unittest.TestCase):
    """With ticket 1 dropped, nothing builds a suite, so tickets 3 and 4 cannot rely on one."""

    def test_it_says_there_is_no_check_suite(self):
        text = option_two()
        for phrase in ("no check suite", "Rust exemption"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_it_changes_tickets_three_and_four(self):
        text = option_two()
        for phrase in ("Ticket 3 fetches no tools", "limit of the review", "Ticket 4 has no Repository standards step"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)


def design_step(number):
    """Return the numbered step under "## Design" in SKILL.md, up to the next step."""
    section = SKILL.split("\n## Design\n", 1)[1].split("\n## ", 1)[0]
    for item in re.split(r"\n(?=\d+\. \*\*)", section):
        if item.lstrip().startswith(f"{number}. **"):
            return item
    raise AssertionError(f"SKILL.md has no design step {number}")


class DesignStepTwoTest(unittest.TestCase):
    def setUp(self):
        self.step = design_step(2)
        self.done = self.step.split("Done when", 1)[1]

    def test_it_drafts_the_check_suite(self):
        for phrase in (
            "check suite",
            "**Tools**",
            "**Pinned versions**",
            "**What floats**",
            "**Untrusted input**",
            "fuzz target or a property test",
            "why neither fits",
            "#87",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.step)

    def test_it_lists_the_execution_surface_for_ticket_three(self):
        for phrase in ("execution surface", "GLOSSARY.md#language-skills", "files and flags", "ticket 3"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.step)

    def test_the_spec_records_both(self):
        self.assertRegex(self.step, r"The spec records [^.]*check suite[^.]*execution surface")

    def test_it_allows_review_areas_beyond_gos_ten(self):
        for phrase in ("beyond Go's ten", "CONTRIBUTING.md#shared-rules-for-every-language", "the spec records why"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.step)

    def test_it_skips_the_suite_under_option_two(self):
        self.assertIn("option two", self.step)
        self.assertIn("no check suite", self.done)

    def test_its_done_condition_covers_the_suite_and_surface(self):
        for phrase in ("pinned version", "floats", "untrusted-input", "execution surface"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.done)


class LinksTest(unittest.TestCase):
    def test_relative_links_resolve(self):
        for path in (SKILL_DIR / "SKILL.md", SKILL_DIR / "references/gotchas.md", SKILL_DIR / "references/tickets.md"):
            for target in relative_links(path.read_text(encoding="utf-8")):
                with self.subTest(file=path.name, target=target):
                    file, _, anchor = target.partition("#")
                    resolved = (path.parent / file) if file else path
                    self.assertTrue(resolved.exists(), f"{target} does not exist")
                    if anchor and resolved.suffix == ".md":
                        self.assertIn(anchor, anchors(resolved))


if __name__ == "__main__":
    unittest.main()
