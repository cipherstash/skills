# Tests for scripts/check.py, prose.py, and settings.py.
# Run: python3 -m unittest discover -s tests (from the skill directory).
# Ported from https://github.com/auxesis/plain-language-skill (Apache-2.0), without the
# tests for that plugin's hooks, which this port does not ship.
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
import warnings

SKILL = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
sys.path[:0] = [os.path.join(SKILL, "scripts")]

from check import findings, load_rules  # noqa: E402
from prose import count_words, prose_units, sentences  # noqa: E402
from settings import SettingsError, names_for  # noqa: E402

rules = load_rules()

def ids(text, mode="file"):
    return [one["id"] for one in findings(text, rules, mode=mode)]


def blocking(text, mode="file"):
    return [one["id"] for one in findings(text, rules, mode=mode) if one["severity"] == "block"]


def temporary_folder(test):
    folder = tempfile.TemporaryDirectory(prefix="plain-language-")
    test.addCleanup(folder.cleanup)
    return folder.name


def write(path, text):
    with open(path, "w", encoding="utf-8", newline="") as handle:
        handle.write(text)


def add_cases(cls, name, cases, check):
    """Adds one test method to `cls` for each case, so each case passes or fails on its own."""
    for index, case in enumerate(cases):
        def test(self, case=case):
            check(self, case)

        slug = re.sub(r"\W+", "_", str(case[0] if isinstance(case, tuple) else case)).strip("_").lower()[:40]
        test.__doc__ = f"{name}: {case}"
        setattr(cls, f"test_{name}_{index:02d}_{slug}", test)


class ReadingMarkdownAsProse(unittest.TestCase):
    def test_leaves_out_fenced_code_and_turns_inline_code_and_urls_into_one_word_each(self):
        units = prose_units("Run `npm run build --workspace a/b` now. See https://example.com/x.\n\n```\nin order to\n```\n")
        self.assertEqual([unit.text for unit in units], ["Run CODE now. See URL."])

    def test_makes_each_list_item_heading_and_table_cell_its_own_piece(self):
        units = prose_units("# Title\n\n- one\n- two\n  continued\n\n| a | b |\n|---|---|\n| c | d |\n")
        self.assertEqual(
            [(unit.kind, unit.text) for unit in units],
            [
                ("heading", "Title"),
                ("item", "one"),
                ("item", "two continued"),
                ("cell", "a"),
                ("cell", "b"),
                ("cell", "c"),
                ("cell", "d"),
            ],
        )

    def test_keeps_metadata_lines_apart_so_they_are_not_read_as_one_sentence(self):
        units = prose_units("purpose: Find your record\nrelated: Topic 2\nneeds: Nothing\n")
        self.assertEqual(len(units), 3)

    def test_joins_hard_wrapped_lines_and_still_knows_which_line_each_part_came_from(self):
        [unit] = prose_units("First line of a sentence\nthat wraps onto line two.")
        self.assertEqual(unit.text, "First line of a sentence that wraps onto line two.")
        self.assertEqual(unit.line_at(unit.text.index("wraps")), 2)

    def test_skips_front_matter_html_comments_and_lines_marked_plain_language_allow(self):
        text = "---\ntitle: in order to\n---\n<!--\nin order to\n-->\nIn order to go. <!-- plain-language-allow -->\nKept."
        self.assertEqual([unit.text for unit in prose_units(text)], ["Kept."])

    def test_does_not_end_a_sentence_at_e_g_or_a_version_number(self):
        self.assertEqual(len(sentences("Use a tool, e.g. Make. Version 1.2 works. Done.")), 3)

    def test_counts_a_word_only_when_it_has_a_letter_or_a_digit_in_it(self):
        self.assertEqual(count_words("A — B (C) + 4"), 4)

    # The tests below are new in the Python version. They cover the places where the
    # port had to replace a JavaScript feature that Python's re module does not have.

    def test_ends_a_sentence_before_a_capital_letter_that_is_not_ascii(self):
        self.assertEqual(len(sentences("It works. Émile agrees.")), 2)
        self.assertEqual(len(sentences("It works. émile agrees.")), 1)

    def test_counts_a_word_made_of_letters_that_are_not_ascii(self):
        self.assertEqual(count_words("café — naïve ½"), 3)


PHRASE_CASES = [
    ("wordy", "We did this in order to test it."),
    ("smothered-verb", "We need to make a decision today."),
    ("hidden-actor", "It was decided that the job stops."),
    ("throat-clearing", "It is worth noting that the job stops."),
    ("flattery-or-filler-closer", "Great question. The job stops."),
    ("cliche", "This is low-hanging fruit."),
    ("idiom", "These tests are load-bearing."),
    ("shorthand", "Run it w/ the flag."),
    ("arrow", "The value goes from 1 → 2."),
    ("stacked-hedge", "This could potentially fail."),
    ("negative-contraction", "It doesn't work."),
    ("date-format", "It ran on October 21, 2026."),
    ("inclusive-language", "Add it to the whitelist."),
    ("figurative", "Each claim rests on these measurements."),
    ("figurative", "New pull requests drove the cost."),
    ("figurative", "The smaller figure strengthens the case for skipping it."),
    ("symbol-shorthand", "The cost is ≈ $3,300."),
    ("symbol-shorthand", "The cost is $3.3k a month."),
    ("symbol-shorthand", "That is a 22× jump."),
    ("symbol-shorthand", "Compare light vs heavy jobs."),
    ("month-abbreviation", "The cuts are live by 1 Nov."),
    ("govuk-words-to-avoid", "We will liaise with the team."),
    ("govuk-tone", "Please note that the job stops."),
    ("govuk-tone", "The member can do it if he or she wants."),
    ("govuk-tone", "You should've run it first."),
]


class PhraseRules(unittest.TestCase):
    def test_does_not_block_plain_text(self):
        self.assertEqual(blocking("The job stops at midnight. You can start it again from the settings page.", "chat"), [])

    def test_does_not_check_words_inside_quotation_marks_or_inline_code(self):
        self.assertEqual(blocking('Write "to", not "in order to". Leave `in order to` alone.', "chat"), [])
        self.assertEqual(blocking("Write 'to', not 'in order to'.", "chat"), [])

    def test_does_not_read_an_apostrophe_as_a_quotation_mark(self):
        self.assertIn("negative-contraction", blocking("The member's record doesn't change.", "chat"))

    def test_does_not_report_a_literal_use_that_the_pattern_excludes(self):
        self.assertNotIn("figurative-jargon", ids("Print it in landscape orientation."))

    # New in the Python version: rules.json contains JavaScript patterns.

    def test_compiles_every_pattern_in_rules_json_without_a_warning(self):
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            load_rules()

    def test_reports_an_emoji_but_not_a_trademark_sign(self):
        self.assertIn("emoji", ids("The build passed 🎉 today."))
        self.assertNotIn("emoji", ids("Claude™ is a name."))


def _blocks_phrase(self, case):
    rule, text = case
    self.assertIn(rule, blocking(text, "chat"), f"{rule} not found in: {text}")


add_cases(PhraseRules, "blocks", PHRASE_CASES, _blocks_phrase)

LONG = " ".join(f"word{i}" for i in range(26)) + "."


class SentenceAndParagraphRules(unittest.TestCase):
    def test_blocks_a_sentence_over_25_words_and_allows_one_of_25(self):
        self.assertIn("long-sentence", blocking(LONG))
        ok = " ".join(f"word{i}" for i in range(25)) + "."
        self.assertNotIn("long-sentence", blocking(ok))

    def test_measures_each_list_item_on_its_own(self):
        items = "\n".join(f"- Item {i} has six words here" for i in range(6))
        self.assertEqual(blocking(items), [])

    def test_blocks_a_paragraph_of_six_sentences_but_not_a_list_of_six_items(self):
        self.assertIn("long-paragraph", blocking("One. Two. Three. Four. Five. Six."))
        self.assertNotIn("long-paragraph", blocking("- One.\n- Two.\n- Three.\n- Four.\n- Five.\n- Six."))

    def test_blocks_an_aside_of_five_words_or_more_in_the_middle_of_a_sentence(self):
        self.assertIn("aside-interrupts-sentence", blocking("The job stops — unless somebody has paused it first — at midnight."))
        self.assertIn("aside-interrupts-sentence", blocking("The job stops (unless somebody has paused it first) at midnight."))

    def test_does_not_block_a_short_aside_a_dash_that_ends_a_sentence_or_a_pair_across_two_sentences(self):
        self.assertEqual(blocking("The job (nightly) stops at midnight."), [])
        self.assertEqual(blocking("The job stops at midnight — every night."), [])
        self.assertEqual(blocking("One part — a short clause. Then another sentence starts — and ends here."), [])


class Advice(unittest.TestCase):
    def test_reports_an_abbreviation_that_is_never_spelled_out_once(self):
        found = [one for one in findings("The FFR report and the FFR view.", rules) if one["id"] == "undefined-abbreviation"]
        self.assertEqual(len(found), 1)

    def test_does_not_report_an_abbreviation_spelled_out_in_the_text_or_a_known_one(self):
        self.assertNotIn("undefined-abbreviation", ids("Fit for Role (FFR) matters. The FFR view."))
        self.assertNotIn("undefined-abbreviation", ids("Read the API docs and the JSON file."))

    def test_reports_a_shouted_word_as_shouting_not_as_an_abbreviation(self):
        found = ids("You MUST run it.")
        self.assertIn("shouted-word", found)
        self.assertNotIn("undefined-abbreviation", found)

    def test_never_blocks_on_advice(self):
        self.assertEqual(blocking("This is very clear: 3x faster & simpler.", "chat"), [])

    def test_allows_a_short_month_name_inside_a_table_and_nowhere_else(self):
        table = "| Month | Cost |\n|---|---:|\n| Sep | 189 |\n| Oct | 3865 |\n"
        self.assertNotIn("month-abbreviation", blocking(table))

    def test_reports_a_fragment_with_no_subject_and_not_a_whole_sentence_that_starts_the_same_way(self):
        self.assertIn("no-subject", ids("Checking the filter now.", "chat"))
        self.assertNotIn("no-subject", ids("Getting under $1,000 means a 74% cut.", "chat"))
        self.assertNotIn("no-subject", ids("Nothing changes.", "chat"))

    # New in the Python version. Python's \b treats "É" as part of a word, so it does
    # not find the abbreviation "COLE" inside "ÉCOLE", as the JavaScript version did.
    def test_does_not_report_part_of_a_word_that_starts_with_a_letter_that_is_not_ascii(self):
        self.assertNotIn("undefined-abbreviation", ids("The ÉCOLE report is ready."))


ROUND_TWO_BLOCKED = [
    ("two-ideas-in-one-sentence", "A light job is one small enough for GitHub's runners, which cost nothing."),
    ("two-ideas-in-one-sentence", "Six decisions are made and eight are waiting on you."),
    ("thing-given-person-verb", "`.github/CONTEXT.md` is new and holds the CI glossary."),
    ("thing-given-person-verb", "`CONTEXT-MAP.md` gains one link to it."),
    ("thing-given-person-verb", "The function knows which row to read."),
    ("condition-after-instruction", "Tell me where you would like it kept if you need it."),
    ("figurative", "The stack repository is on pace to spend $4,000."),
]

ROUND_TWO_ALLOWED = [
    "A member holds the Boat Operator capability.",
    "Done when someone who reads the first paragraph knows what it says.",
    "Check if your code is incorrect, or if it has expired.",
    "Read a record Slipstream has nothing in, and know what to do about it.",
    "Topic 3 covers what a capability is, and what an assessment is.",
    "Use a technical term only if the reader already uses it.",
    "Write must for a rule that has consequences if it is broken.",
]


class RulesFromTheReviewOfRoundTwo(unittest.TestCase):
    def test_asks_for_a_comma_after_an_opening_clause_and_not_in_a_question(self):
        self.assertIn("comma-after-opening-clause", blocking("If you need it tell me where to keep it.", "chat"))
        self.assertEqual(blocking("If you need it, tell me where to keep it.", "chat"), [])
        self.assertEqual(blocking("When does the nightly job run?", "chat"), [])

    def test_asks_for_a_serial_comma_in_a_list_and_not_in_a_phrase_or_a_name(self):
        self.assertIn("serial-comma", blocking("It covers words, headings and links.", "chat"))
        self.assertEqual(blocking("It covers words, headings, and links.", "chat"), [])
        self.assertEqual(blocking("An assessment can have a level, such as Lift and Shift Level 2.", "chat"), [])
        self.assertEqual(blocking("Your row shows it as Paused, with your reason and the date.", "chat"), [])
        self.assertEqual(blocking("Comment on a line, or select lines and suggest a change.", "chat"), [])
        self.assertEqual(blocking("Eight test inputs, run before and after the change.", "chat"), [])
        self.assertEqual(blocking("I checked the page, before and after the change.", "chat"), [])
        self.assertNotIn("serial-comma", blocking("The report, written last week and sent today, lists the results.", "chat"))
        self.assertEqual(blocking("For the run without the skill, all hooks and skills were turned off.", "chat"), [])
        self.assertIn("serial-comma", blocking("For the test, it covers words, headings and links.", "chat"))


def _blocks_round_two(self, case):
    rule, text = case
    self.assertIn(rule, blocking(text, "chat"))


def _allows_round_two(self, text):
    self.assertEqual(blocking(text, "chat"), [])


add_cases(RulesFromTheReviewOfRoundTwo, "blocks", ROUND_TWO_BLOCKED, _blocks_round_two)
add_cases(RulesFromTheReviewOfRoundTwo, "allows", ROUND_TWO_ALLOWED, _allows_round_two)

# The review of round three is in pull request 1. Most of these texts are quoted from it.
ROUND_THREE_BLOCKED = [
    ("repeated-word", "Now the stand-in in each test:"),
    ("repeated-word", "Read the the file first."),
    ("question-heading-items", "## Questions for the next round\n\n- **Weekly cost estimate:** where it gets posted.\n"),
    ("question-heading-items", "## Questions for the next round\n\n- **Tool setup:** the mise tool-setup step takes about 16% of all job time.\n"),
    ("question-heading-items", "## Open questions\n\n### Billing\n\n1. The names of the summary checks that become required.\n"),
    ("whether-item", "## Facts I still need to check\n\n- Whether the RunsOn trial licence has an end date.\n"),
    ("whether-item", "- **Dependabot:** whether to group its updates.\n"),
    # From the review of the first description of pull request 10: things given a person's
    # verb, in headings as well as in sentences.
    ("thing-given-person-verb", "## What the checker cannot see\n\nThe checker never checks code blocks.\n"),
    ("thing-given-person-verb", "## How the checks behave on real text\n\nThe checks ran over 77 files.\n"),
    ("thing-given-person-verb", "## Each review comment, and the change that answers it\n\nThe table lists them.\n"),
    ("thing-given-person-verb", "The test cannot see the new file."),
]

ROUND_THREE_ALLOWED = [
    "Now the stand-in for each test:",
    "The reviewer answered each comment.",
    "You can see the file in the pull request.",
    "You can see the table below.",
    # Database documentation says that a transaction sees data. The user allowed it.
    "Under SERIALIZABLE, each transaction sees the data as it was when the transaction started.",
    "## Review comments and changes\n\nThe checker skips code blocks.\n",
    "Run `npm test` `--watch` again.",
    "## Questions for the next round\n\n- **Dependabot:** should updates be grouped?\n  In 20 days, 40 Dependabot branches cost $115.\n- **Weekly cost estimate:** where does it get posted?\n",
    "## Questions\n\n- Is the job done?\n\n## Next steps\n\n- Run the tests again.\n",
    "## Decisions\n\n- **Dependabot:** updates are grouped by week.\n",
    "- Whether or not you use mise, run the tests before you push.\n",
    # Found in the sample of real replies: inline code becomes the word CODE.
    "It cancels one of the transactions with a serialisation error, code `40001`.",
    # A nested item under a question contains a detail.
    "## Questions waiting for your answers\n\n1. **Q2:** which checks run only once per pull request?\n   - The Test EQL heavy suite.\n   - udeps and Miri.\n",
    # A part that asks its questions in paragraphs has lists of options.
    "## Questions\n\n**Q1:** Should stack use a merge queue? These are the choices:\n\n- (a) A merge queue.\n- (b) A label that a person adds.\n",
    "## Questions for this round\n\n**Q1. What starts the pre-merge run.** There are two options:\n\n1. A GitHub merge queue.\n2. A label that a person adds.\n\nShall the pre-merge run be a GitHub merge queue?\n",
]

ROUND_THREE_ADVISED = [
    ("pronoun-start", "They skip any new or unstaged file without failing."),
    ("pronoun-start", "Their output does not list which files they read."),
    ("pronoun-start", "It runs at midnight."),
    ("pronoun-start", "This means that the job stops."),
    ("pronoun-start", "These are the two options."),
    ("purpose-last", "- calls the callback with an empty list of entries and the observer, to match the real callback signature\n"),
    ("purpose-last", "We call the job twice, to make sure it stops."),
]

ROUND_THREE_NOT_ADVISED = [
    ("pronoun-start", "The guards skip any new or unstaged file without failing."),
    ("pronoun-start", "This file is new, and these tests pass."),
    ("pronoun-start", "This process runs every night."),
    ("pronoun-start", "The guards read only files that git tracks, so they skip new files."),
    ("purpose-last", "- match the real callback signature, by calling the callback with the observer and an empty list of entries\n"),
    ("purpose-last", "Give the report to the team, to the person on call, or to me."),
]


class RulesFromTheReviewOfRoundThree(unittest.TestCase):
    def test_reports_a_question_heading_item_only_under_that_heading(self):
        text = "## Questions\n\n- Is the job done?\n- The job is done.\n\n## Notes\n\n- The job is done.\n"
        found = [one["line"] for one in findings(text, rules) if one["id"] == "question-heading-items"]
        self.assertEqual(found, [4])

    def test_never_blocks_on_a_pronoun_or_a_purpose_at_the_end(self):
        for _, text in ROUND_THREE_ADVISED:
            with self.subTest(text=text):
                self.assertEqual(blocking(text, "chat"), [])


def _blocks_round_three(self, case):
    rule, text = case
    self.assertIn(rule, blocking(text, "chat"))


def _allows_round_three(self, text):
    self.assertEqual(blocking(text, "chat"), [])


def _advises_round_three(self, case):
    rule, text = case
    self.assertIn(rule, ids(text, "chat"))


def _does_not_advise_round_three(self, case):
    rule, text = case
    self.assertNotIn(rule, ids(text, "chat"))


add_cases(RulesFromTheReviewOfRoundThree, "blocks", ROUND_THREE_BLOCKED, _blocks_round_three)
add_cases(RulesFromTheReviewOfRoundThree, "allows", ROUND_THREE_ALLOWED, _allows_round_three)
add_cases(RulesFromTheReviewOfRoundThree, "advises", ROUND_THREE_ADVISED, _advises_round_three)
add_cases(RulesFromTheReviewOfRoundThree, "does_not_advise", ROUND_THREE_NOT_ADVISED, _does_not_advise_round_three)


class StructureRules(unittest.TestCase):
    def test_blocks_a_heading_that_is_a_question(self):
        self.assertIn("heading-is-a-question", blocking("## Which members have no unit?\n\nText."))

    def test_blocks_a_heading_that_skips_a_level_and_allows_going_back_up(self):
        self.assertIn("heading-level-skipped", blocking("## One\n\n#### Two\n"))
        self.assertNotIn("heading-level-skipped", blocking("## One\n\n### Two\n\n## Three\n"))

    def test_reports_percentages_that_add_up_to_more_than_the_whole_even_with_notes_in_the_cells(self):
        table = "\n".join(
            [
                "| Slice | Share of cost |",
                "|---|---:|",
                "| Pull requests | 89% |",
                "| 16-vCPU runners | 76% |",
                "| Test EQL | 52% ($1,700 a month) |",
            ]
        )
        self.assertIn("parts-exceed-whole", ids(table))
        whole = "| Part | Share |\n|---|---:|\n| A | 60% |\n| B | 30% |\n| C | 10% |\n"
        self.assertNotIn("parts-exceed-whole", ids(whole))

    def test_reports_a_column_of_numbers_that_is_not_right_aligned_and_an_empty_cell(self):
        found = ids("| Repo | Cost |\n|---|---|\n| stack | 3865 |\n| proxy |  |\n| suite | 67 |\n")
        self.assertIn("empty-table-cell", found)
        self.assertIn("numbers-not-right-aligned", ids("| Repo | Cost |\n|---|---|\n| stack | 3865 |\n| proxy | 325 |\n"))

    def test_reports_the_same_link_text_going_to_two_places(self):
        self.assertIn("link-text-reused", ids("See [the guide](a.md) and [the guide](b.md)."))

    # New in the Python version. Python's \s does not match U+FEFF, the byte order mark.
    def test_reads_the_first_line_of_a_file_with_a_byte_order_mark_as_a_heading(self):
        self.assertIn("heading-is-a-question", blocking("﻿## Which members have no unit?\n\nText."))


CLI = os.path.join(SKILL, "scripts", "check.py")


def run(arguments, text=None, cwd=None, env=None):
    return subprocess.run(
        [sys.executable, "-I", *arguments],
        input=text,
        capture_output=True,
        encoding="utf-8",
        cwd=cwd,
        env=env,
    )


class TheCommandLine(unittest.TestCase):
    def test_exits_1_when_something_must_be_fixed_and_0_when_nothing_must(self):
        self.assertEqual(run([CLI, "--chat"], "We did it in order to test it.").returncode, 1)
        self.assertEqual(run([CLI, "--chat"], "We did it to test it.").returncode, 0)

    def test_runs_when_it_is_reached_through_a_symlink(self):
        link = os.path.join(temporary_folder(self), "check.py")
        os.symlink(CLI, link)
        bad = run([link, "--chat"], "We did it in order to test it.")
        self.assertEqual(bad.returncode, 1)
        self.assertRegex(bad.stdout, "must fix")

    def test_passes_its_own_skill_files(self):
        files = [os.path.join(SKILL, file) for file in ("SKILL.md", "references/core.md", "references/guidelines.md")]
        out = json.loads(run([CLI, "--json", *files]).stdout)
        self.assertEqual(out["mustFix"], 0)



GLOSSARY = "- **Fit for Role assessment** — one of the eight Fit for Role assessments.\n  They are Swim, Lift and Shift, Carry, Hike, Drag, Haul, Hold, and Ladder Climb and Lift.\n"
CLUSTER = "For a whole cluster, select every unit in it, and the cluster's own name too. aXcelerate's filter does not accept a cluster name on its own.\n"
RANK = "The Rank and Insignia Procedure awards a rank on three things: training and skills, service experience and proficiency, and aptitude and behaviour.\n"
NAMED_CASES = [
    ("a name with and in it is not the end of a list", GLOSSARY, "Lift and Shift", "serial-comma"),
    ("a name that starts with a small letter can start a sentence", CLUSTER, "aXcelerate", "long-sentence"),
    ("a name made of a pair is one item in a list", RANK, "service experience and proficiency", "serial-comma"),
]


def blocking_with(text, names, mode="file"):
    return [one["id"] for one in findings(text, rules, mode=mode, names=names) if one["severity"] == "block"]


def repository(test, settings=None):
    """A temporary git repository, with a settings file at its top when `settings` is given."""
    root = temporary_folder(test)
    os.mkdir(os.path.join(root, ".git"))
    if settings is not None:
        write(os.path.join(root, ".plain-language.json"), settings if isinstance(settings, str) else json.dumps(settings))
    return root


class ProjectNames(unittest.TestCase):
    def test_a_name_counts_as_one_word(self):
        text = f"Members {' '.join(f'w{i}' for i in range(21))} passed Ladder Climb and Lift.\n"
        self.assertIn("long-sentence", blocking(text))
        self.assertNotIn("long-sentence", blocking_with(text, ("Ladder Climb and Lift",)))

    def test_matches_a_name_only_in_its_own_case_and_as_a_whole_word(self):
        for written in ("axcelerate", "aXcelerateX"):
            with self.subTest(written=written):
                self.assertIn("long-sentence", blocking_with(CLUSTER.replace("aXcelerate", written), ("aXcelerate",)))

    def test_shows_the_readers_own_words_in_every_finding(self):
        [wordy] = [one for one in findings("aXcelerate does it in order to test it.", rules, names=("aXcelerate",)) if one["id"] == "wordy"]
        self.assertEqual(wordy["excerpt"], "aXcelerate does it in order to test it.")
        [repeated] = [one for one in findings("Pass Lift and Shift Lift and Shift first.", rules, names=("Lift and Shift",)) if one["id"] == "repeated-word"]
        self.assertEqual(repeated["match"], "Lift and Shift Lift and Shift")

    def test_does_not_read_two_names_of_the_same_length_as_one_word_twice(self):
        self.assertNotIn("repeated-word", blocking_with("Pass Hike Drag first.", ("Hike", "Drag")))

    # Each name is read as one stand-in word of the same length. A rule that matched the
    # stand-in would report a problem the reader cannot see.
    def test_no_rule_matches_the_word_that_stands_in_for_a_name(self):
        for length in range(1, 61):
            name = "q" * length
            for text in (f"The {name} is here.", f"{name} is here.", f"- {name}"):
                with self.subTest(text=text):
                    self.assertEqual(findings(text, rules, mode="chat", names=(name,)), [])

    def test_finds_the_nearest_settings_file_up_to_the_top_of_the_repository(self):
        root = repository(self, {"names": ["aXcelerate"]})
        os.makedirs(os.path.join(root, "docs", "guide"))
        page = os.path.join(root, "docs", "guide", "page.md")
        self.assertEqual(names_for(page), ("aXcelerate",))
        write(os.path.join(root, "docs", ".plain-language.json"), json.dumps({"names": ["Lift and Shift"]}))
        self.assertEqual(names_for(page), ("Lift and Shift",))

    # In a git worktree, .git is a file, not a folder.
    def test_does_not_use_a_settings_file_above_the_top_of_the_repository(self):
        outer = temporary_folder(self)
        write(os.path.join(outer, ".plain-language.json"), json.dumps({"names": ["aXcelerate"]}))
        os.mkdir(os.path.join(outer, "project"))
        write(os.path.join(outer, "project", ".git"), "gitdir: /elsewhere\n")
        self.assertEqual(names_for(os.path.join(outer, "project", "page.md")), ())

    BROKEN = [
        ("not JSON", '{"names": ["aXcelerate"]', "cannot be read as JSON"),
        ("not an object", '["aXcelerate"]', "must be a JSON object"),
        ("an unknown setting", '{"names": [], "rules": {"long-sentence": false}}', '"rules" is not a setting'),
        ("names that are not a list", '{"names": "aXcelerate"}', '"names" must be a list'),
        ("a name that is not a string", '{"names": [7]}', "each name must be a string"),
        ("a name with no letter in it", '{"names": [" - "]}', "each name must be a string"),
        ("a name that ends with a space", '{"names": ["aXcelerate "]}', "starts or ends with a space"),
    ]

    def check_broken(self, case):
        _, content, reason = case
        root = repository(self, content)
        with self.assertRaises(SettingsError) as raised:
            names_for(root)
        self.assertEqual(raised.exception.path, os.path.join(root, ".plain-language.json"))
        self.assertIn(reason, raised.exception.reason)

    def test_the_command_line_reads_the_settings_file_for_each_file_and_for_standard_input(self):
        root = repository(self)
        page = os.path.join(root, "page.md")
        write(page, CLUSTER)
        self.assertEqual(run([CLI, page]).returncode, 1)
        self.assertEqual(run([CLI, "--chat"], CLUSTER, cwd=root).returncode, 1)
        write(os.path.join(root, ".plain-language.json"), json.dumps({"names": ["aXcelerate"]}))
        self.assertEqual(run([CLI, page]).returncode, 0)
        self.assertEqual(run([CLI, "--chat"], CLUSTER, cwd=root).returncode, 0)

    def test_the_command_line_exits_2_and_names_a_broken_settings_file(self):
        root = repository(self, '{"names": "aXcelerate"}')
        page = os.path.join(root, "page.md")
        write(page, CLUSTER)
        result = run([CLI, page])
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        self.assertIn(os.path.join(root, ".plain-language.json"), result.stderr)
        self.assertIn('"names" must be a list', result.stderr)

add_cases(
    ProjectNames,
    "names",
    NAMED_CASES,
    lambda self, case: (
        self.assertIn(case[3], blocking(case[1])),
        self.assertNotIn(case[3], blocking_with(case[1], (case[2],))),
    ),
)
add_cases(ProjectNames, "broken", ProjectNames.BROKEN, ProjectNames.check_broken)


if __name__ == "__main__":
    unittest.main()
