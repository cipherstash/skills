"""Tests that the building-language-pairs process skill runs ADR 0003's design loop, steps 1 to 4.

ADR 0003 (docs/adr/0003-settle-shared-language-decisions-once.md) has each language researched, its open decisions
sorted into shared and language-only, and only the language-only ones taken to a grill that writes docs and no code.
The research and grill outcome are saved on the language's parent ticket, so a resumed session finds them (#92 G2).
"""

from pathlib import Path
import re
import unittest


REPO = Path(__file__).resolve().parents[2]
SKILL = REPO / ".claude" / "skills" / "building-language-pairs" / "SKILL.md"
STEP = re.compile(r"^(\d+)\. \*\*(.+?)\*\*(.*)$", re.MULTILINE)


def section(text, heading):
    """Return the body of the level-2 section with this heading, up to the next level-2 heading."""
    return text.split(f"\n## {heading}\n", 1)[1].split("\n## ", 1)[0]


def steps(text):
    """Return the numbered steps of a section as (number, title, body) tuples, in order."""
    return [(int(number), title, title + rest) for number, title, rest in STEP.findall(text)]


def step_named(design, word):
    """Return the one design step whose bold title contains this word, as (number, title, body)."""
    found = [step for step in steps(design) if word in step[1].lower()]
    if len(found) != 1:
        raise AssertionError(f"expected one design step titled with {word!r}, found {[s[1] for s in found]}")
    return found[0]


class DesignLoopTest(unittest.TestCase):
    def setUp(self):
        self.text = SKILL.read_text(encoding="utf-8")
        self.design = section(self.text, "Design")

    def test_research_sorts_open_decisions_into_shared_and_language_only(self):
        number, _, body = step_named(self.design, "research")
        self.assertEqual(number, 1, "research is the first design step")
        for phrase in ("open decision", "shared", "language-only", "**Language skills**", "docs/adr/",
                       "its own ticket"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, body)

    def test_grill_follows_research_and_comes_before_the_spec(self):
        research, _, _ = step_named(self.design, "research")
        grill, _, _ = step_named(self.design, "grill")
        spec, _, _ = step_named(self.design, "spec")
        self.assertLess(research, grill)
        self.assertLess(grill, spec)

    def test_grill_writes_only_docs_and_ends_at_shared_understanding(self):
        _, _, body = step_named(self.design, "grill")
        for phrase in ("language-only", "only GLOSSARY entries and ADRs", "shared understanding", "no code",
                       "not a go-ahead"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, body)

    def test_every_step_before_the_spec_saves_its_result_on_the_parent_ticket(self):
        spec, _, _ = step_named(self.design, "spec")
        for number, title, body in steps(self.design):
            if number < spec:
                with self.subTest(step=title):
                    done = body.split("Done when", 1)[1]
                    self.assertIn("comment on the parent ticket", done)

    def test_checklist_step_sends_open_questions_to_the_grill(self):
        _, _, body = step_named(self.design, "checklist")
        self.assertNotIn("Answer each open question", body)
        self.assertIn("grill", body)

    def test_resuming_reads_the_design_state_from_the_parent_ticket(self):
        resuming = section(self.text, "Resuming")
        for phrase in ("parent ticket's comments", "research report", "grill outcome"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, resuming)


if __name__ == "__main__":
    unittest.main()
