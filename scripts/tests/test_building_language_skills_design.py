"""Tests that the language skills process skill drafts the check suite in design and follows ADR 0002.

The process skill lives in .claude/skills/ and is not published, so the validator does not read it. These tests pin
ticket #128: design step 2 drafts the check suite and lists the execution surface, the review-tools gotcha states
ADR 0002's rule, and the ticket breakdown matches CONTRIBUTING.md's Language skills section.
"""

from pathlib import Path
import re
import unittest


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


if __name__ == "__main__":
    unittest.main()
