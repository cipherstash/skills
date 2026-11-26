"""Tests that the building-language-skills process skill runs ADR 0003's design loop, steps 1 to 4.

ADR 0003 (docs/adr/0003-settle-shared-language-decisions-once.md) has each language researched, its open decisions
sorted into shared and language-only, and only the language-only ones taken to a grill that writes docs and no code.
The research and grill outcome are saved on the language's parent ticket, so a resumed session finds them (#92 G2).
"""

from pathlib import Path
import re
from typing import NamedTuple
import unittest

from test_contributing_links import section


REPO = Path(__file__).resolve().parents[2]
SKILL = REPO / ".claude" / "skills" / "building-language-skills" / "SKILL.md"
TICKETS = SKILL.parent / "references" / "tickets.md"
CONTRIBUTING = REPO / "CONTRIBUTING.md"
STEP_START = re.compile(r"^(\d+)\. \*\*(.+?)\*\*", re.MULTILINE)
STEP_REFERENCE = re.compile(r"\b(?:design |build )?steps? \d+(?: to \d+)?\b", re.IGNORECASE)


class Step(NamedTuple):
    number: int
    title: str
    text: str
    """The whole step: its title line and any indented lines under it."""


def steps(text):
    """Return the numbered steps of a section, in order. A step runs up to the next step or the end of the section."""
    starts = list(STEP_START.finditer(text))
    found = []
    for index, match in enumerate(starts):
        end = starts[index + 1].start() if index + 1 < len(starts) else len(text)
        found.append(Step(int(match.group(1)), match.group(2), text[match.start(2):end]))
    return found


def step_named(design, word):
    """Return the one design step whose bold title contains this word."""
    found = [step for step in steps(design) if word in step.title.lower()]
    if len(found) != 1:
        raise AssertionError(f"expected one design step titled with {word!r}, found {[s.title for s in found]}")
    return found[0]


def done_condition(step):
    """Return the text after "Done when" in a step."""
    if "Done when" not in step.text:
        raise AssertionError(f"step {step.number} ({step.title}) has no done condition")
    return step.text.split("Done when", 1)[1]


class DesignLoopTest(unittest.TestCase):
    def setUp(self):
        self.text = SKILL.read_text(encoding="utf-8")
        self.design = section(self.text, "Design")

    def test_research_sorts_open_decisions_into_shared_and_language_only(self):
        research = step_named(self.design, "research")
        self.assertEqual(research.number, 1, "research is the first design step")
        for phrase in ("open decision", "shared", "language-only", "**Language skills**", "docs/adr/",
                       "its own ticket"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, research.text)

    def test_research_searches_for_an_existing_shared_ticket_before_filing_one(self):
        # Languages designed in parallel would each file a ticket for the same shared question.
        research = step_named(self.design, "research")
        self.assertIn("search the open issues", research.text)
        self.assertIn("filing-github-issues", research.text)
        self.assertIn("link the match", research.text)

    def test_grill_follows_research_and_comes_before_the_spec(self):
        research = step_named(self.design, "research")
        grill = step_named(self.design, "grill")
        spec = step_named(self.design, "spec")
        self.assertLess(research.number, grill.number)
        self.assertLess(grill.number, spec.number)

    def test_grill_writes_only_docs_and_ends_at_shared_understanding(self):
        grill = step_named(self.design, "grill")
        for phrase in ("language-only", "only GLOSSARY entries and ADRs", "shared understanding", "no code",
                       "not a go-ahead"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, grill.text)

    def test_no_design_step_answers_open_questions_itself(self):
        # The grill takes them to the person, so no step may tell the agent to answer them.
        for step in steps(self.design):
            with self.subTest(step=step.title):
                self.assertNotRegex(step.text, r"(?i)\banswer (each|every|the) (language-only )?open")
        self.assertIn("Answer no open decision yourself", step_named(self.design, "research").text)
        self.assertIn("Do not answer open questions yourself", step_named(self.design, "checklist").text)

    def test_every_step_before_the_spec_saves_its_result_on_the_parent_ticket(self):
        spec = step_named(self.design, "spec")
        for step in steps(self.design):
            if step.number < spec.number:
                with self.subTest(step=step.title):
                    self.assertIn("comment on the parent ticket", done_condition(step))

    def test_steps_one_to_three_list_their_shared_tickets_in_their_comment(self):
        # Resuming rebuilds the list of shared tickets that the grill waits for from these comments.
        for word in ("research", "checklist", "audit"):
            step = step_named(self.design, word)
            with self.subTest(step=step.title):
                self.assertIn("filed or linked", done_condition(step))

    def test_done_conditions_of_steps_two_to_four_are_bulleted_lists(self):
        # Inline, "or recorded it as unbuildable" could be read as covering the clauses after it.
        for word in ("checklist", "audit", "grill"):
            step = step_named(self.design, word)
            with self.subTest(step=step.title):
                done = done_condition(step)
                self.assertRegex(done, r"^[^\n]*:\n   - ", "the done condition opens a bulleted list")

    def test_audit_with_no_upstream_skill_still_posts_its_comment(self):
        # Otherwise a resumed session finds step 3 unmet and goes back to it.
        audit = step_named(self.design, "audit")
        self.assertNotIn("record that and go to step 4", audit.text)
        self.assertIn("With no upstream skill, post a comment on the parent ticket saying so", audit.text)
        self.assertIn("no upstream skill", done_condition(audit))

    def test_steps_two_and_three_sort_new_questions_as_step_one_says(self):
        # ADR 0003 item 2 and #127: a shared question goes to its own ticket, never to the language's grill.
        research = step_named(self.design, "research")
        self.assertIn("its own ticket", research.text)
        self.assertIn("It never goes to this language's grill", research.text)
        for word in ("checklist", "audit"):
            step = step_named(self.design, word)
            with self.subTest(step=step.title):
                self.assertIn("step 1's list", step.text)
                self.assertIn("sort it as step 1 says", step.text)
                self.assertIn("settled or has its own ticket", done_condition(step))

    def test_grill_waits_for_every_shared_ticket_whoever_filed_it(self):
        # ADR 0003 item 2: settle the shared questions before any language grill, including another language's ticket.
        grill = step_named(self.design, "grill")
        self.assertIn("Start only once every shared ticket that steps 1 to 3 name is settled, whoever filed it",
                      grill.text)
        self.assertIn("stop and report", grill.text)

    def test_grill_adrs_and_glossary_entries_do_not_land_in_a_language_pr(self):
        # CONTRIBUTING.md Pull requests and ADR 0003 item 5: shared text changes only through its own ticket.
        grill = step_named(self.design, "grill")
        self.assertNotIn("first ticket, and", grill.text)
        self.assertNotIn("land with the language's first ticket", grill.text)
        self.assertIn("shared-text ticket", grill.text)
        self.assertIn("blocks the first ticket of the language's layout", grill.text)
        self.assertIn("shared-text ticket", done_condition(grill))

    def test_grill_drafts_its_records_in_the_shared_text_ticket(self):
        # No branch exists during design, so the grill cannot write files in docs/adr/ itself.
        grill = step_named(self.design, "grill")
        self.assertNotIn("becomes an ADR in `docs/adr/`", grill.text)
        self.assertIn("body of one shared-text ticket", grill.text)
        self.assertIn("written when that ticket is built", grill.text)

    def test_spec_step_blocks_the_first_ticket_on_the_shared_text_ticket_if_one_was_filed(self):
        spec = step_named(self.design, "spec")
        self.assertIn("If step 4 filed a shared-text ticket, block the layout's first ticket on it", spec.text)

    def test_stop_step_sends_new_questions_back_instead_of_answering_them(self):
        stop = step_named(self.design, "stop")
        self.assertNotIn("the open questions", stop.text)
        self.assertIn("grill outcome", stop.text)
        self.assertIn("as step 1 says", stop.text)

    def test_design_leaves_private_details_out_of_public_comments(self):
        # The repository is public, and every design step posts on the parent ticket.
        intro = self.design.split("\n1. **", 1)[0]
        for phrase in ("public", "private repositories", "security gap", "stop and ask the person"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, intro)

    def test_ticket_breakdown_sends_contributing_changes_to_their_own_ticket(self):
        text = TICKETS.read_text(encoding="utf-8")
        self.assertNotIn("Put a change that design settles in the first ticket", text)
        self.assertNotIn("in the ticket that finds it", text)
        self.assertNotIn("filed by the ticket that finds it", text)
        self.assertNotIn("changes CONTRIBUTING.md only when", text)
        self.assertIn("shared-text ticket", text)

    def test_ticket_breakdown_blocks_the_first_ticket_on_the_shared_text_ticket(self):
        text = TICKETS.read_text(encoding="utf-8")
        first = next((line for line in text.splitlines() if line.startswith("| 1 |")), None)
        self.assertIsNotNone(first, "tickets.md no longer has a row for ticket 1")
        self.assertIn("shared-text ticket", first)
        self.assertNotIn("blocked by nothing", text)
        self.assertIn("blocked only by the shared-text ticket from design step 4, if one exists", text)

    def test_contributing_names_research_and_the_grill(self):
        text = CONTRIBUTING.read_text(encoding="utf-8")
        line = next((l for l in text.splitlines() if "project skill. It takes a language ticket" in l), None)
        self.assertIsNotNone(line, "CONTRIBUTING.md no longer names the building-language-skills skill")
        for phrase in ("research", "grill"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, line)

    def test_resuming_reads_the_design_state_from_the_parent_ticket(self):
        resuming = section(self.text, "Resuming")
        for phrase in ("parent ticket's comments", "research report", "grill outcome", "shared tickets"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, resuming)


# Every "step N" reference in these files, by the phrase that holds it, and the title word of each step it names.
# A reference that is not listed here fails the test, so inserting a step cannot leave a reference stale unnoticed.
STEP_REFERENCES = {
    SKILL: {
        "section before step 1": {1: "research"},
        "Before step 1, look": {1: "research"},
        "from steps 1 to 4": {1: "research", 4: "grill"},
        "shared tickets that steps 1 to 3 filed": {1: "research", 3: "audit"},
        "step 4 takes the language-only": {4: "grill"},
        "the grill in step 4 may pick": {4: "grill"},
        "to step 1's list, and sort it as step 1 says": {1: "research"},
        "update step 2's examples list": {2: "checklist"},
        "go to step 4": {4: "grill"},
        "every shared ticket that steps 1 to 3 name": {1: "research", 3: "audit"},
        "decisions from steps 1 to 3": {1: "research", 3: "audit"},
        "as step 6 says": {6: "stop"},
        "If step 4 filed": {4: "grill"},
        "goes back to step 1's list and is sorted as step 1 says": {1: "research"},
        "The main PR bumps the version, as step 12 says": {12: "main pr"},
        "its own ticket, as step 8 says": {8: "build each ticket"},
        "Run step 8's checks": {8: "build each ticket"},
        "the issue from step 13": {13: "file what the run learned"},
    },
    TICKETS: {
        "When the grill, design step 4": {4: "grill"},
        "shared-text ticket from design step 4": {4: "grill"},
        "checks in build step 8": {8: "build each ticket"},
        "as build step 12 says": {12: "main pr"},
    },
}


class StepReferenceTest(unittest.TestCase):
    def setUp(self):
        text = SKILL.read_text(encoding="utf-8")
        self.titles = {step.number: step.title.lower()
                       for name in ("Design", "Build") for step in steps(section(text, name))}

    def test_each_step_reference_names_the_step_it_means(self):
        for path, references in STEP_REFERENCES.items():
            text = path.read_text(encoding="utf-8")
            for phrase, expected in references.items():
                with self.subTest(file=path.name, phrase=phrase):
                    self.assertIn(phrase, text, "the phrase is gone: update STEP_REFERENCES")
                    for number, word in expected.items():
                        self.assertIn(f"{number}", phrase)
                        self.assertIn(word, self.titles.get(number, ""), f"step {number} is not the {word} step")

    def test_every_step_reference_is_listed(self):
        for path, references in STEP_REFERENCES.items():
            text = path.read_text(encoding="utf-8")
            covered = [range(m.start(), m.end())
                       for phrase in references for m in re.finditer(re.escape(phrase), text)]
            for match in STEP_REFERENCE.finditer(text):
                with self.subTest(file=path.name, reference=match.group(0), at=match.start()):
                    self.assertTrue(any(match.start() in span and match.end() - 1 in span for span in covered),
                                    f"unlisted step reference: ...{text[max(0, match.start() - 30):match.end() + 10]}...")


if __name__ == "__main__":
    unittest.main()
