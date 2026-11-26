"""Tests that the language skills process skill keeps its PRs clean and feeds what it learned back, ADR 0003 steps 5 to 7.

Ticket #130: review fixes land on the reviewed PR's own branch, deferred findings are filed before a PR merges, a
language's PRs leave shared files alone, each run ends by filing what it learned, and the skill is named
`building-language-skills`, since GLOSSARY.md lists "pair" under Avoid.
"""

from pathlib import Path
import re
import subprocess
import unittest


REPO = Path(__file__).resolve().parents[2]
SKILL_DIR = REPO / ".claude" / "skills" / "building-language-skills"
# Built from parts, so this file does not itself hold the old name.
OLD_NAME = "building-language-" + "pairs"
PAIR = re.compile(r"\bpairs?\b", re.IGNORECASE)


def read(path):
    return path.read_text(encoding="utf-8")


def section(text, heading):
    """Return the body of the level-2 section with this heading, up to the next level-2 heading."""
    return text.split(f"\n## {heading}\n", 1)[1].split("\n## ", 1)[0]


def numbered_steps(text):
    """Return a section's numbered steps as (number, title, body), each running to the next numbered step."""
    pattern = re.compile(r"^(\d+)\. \*\*(.+?)\*\*(.*?)(?=^\d+\. \*\*|\Z)", re.MULTILINE | re.DOTALL)
    return [(int(n), title, title + rest) for n, title, rest in pattern.findall(text)]


def build_step(title_start):
    """Return the one build step whose bold title starts with these words, as (number, title, body)."""
    build = section(read(SKILL_DIR / "SKILL.md"), "Build")
    found = [step for step in numbered_steps(build) if step[1].startswith(title_start)]
    if len(found) != 1:
        raise AssertionError(f"expected one build step titled {title_start!r}, found {[s[1] for s in found]}")
    return found[0]


def gotcha(title):
    """Return the bullet in gotchas.md whose bold title is this, up to the next bullet or heading."""
    text = read(SKILL_DIR / "references" / "gotchas.md")
    marker = f"- **{title}**"
    if marker not in text:
        raise AssertionError(f"gotchas.md has no item {title!r}")
    return text.split(marker, 1)[1].split("\n- ", 1)[0].split("\n#", 1)[0]


STACK_GOTCHA = "Fix a PR's findings where the line was added, never on a later branch."


class StackGotchaTest(unittest.TestCase):
    def test_review_fixes_stay_on_the_reviewed_prs_branch(self):
        text = gotcha(STACK_GOTCHA)
        for phrase in ("that PR's branch", "never on a later one", "one job", "#91", "#92"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_review_fixes_may_land_on_the_open_earlier_branch_that_added_the_line(self):
        # A stacked PR's diff can show an earlier branch's lines. The gotcha sends the fix there while that PR is
        # open, and back to the reviewed PR's branch once it has merged.
        text = gotcha(STACK_GOTCHA)
        for phrase in ("`git blame`", "earlier PR", "still open", "has already merged"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_the_rule_is_stated_once_and_the_steps_link_to_it(self):
        # Four copies of the rule had already drifted apart.
        gotchas = read(SKILL_DIR / "references" / "gotchas.md")
        self.assertNotIn("- **Fix where the line was added.**", gotchas)
        self.assertNotIn("- **Fix a PR's findings on its own branch.**", gotchas)
        for title in ("Review each PR", "Merge fixes through the stack"):
            _, _, body = build_step(title)
            with self.subTest(step=title):
                self.assertIn(f"**{STACK_GOTCHA[:-1]}**", body)
                self.assertNotIn("the earlier branch whose commit added the line", body)
                self.assertNotIn("Fix each line on the branch that added it", body)

    def test_the_gotcha_sits_under_the_stack(self):
        stack = read(SKILL_DIR / "references" / "gotchas.md").split("\n## The stack\n", 1)[1].split("\n## ", 1)[0]
        self.assertIn(f"- **{STACK_GOTCHA}**", stack)


class DeferredFindingsTest(unittest.TestCase):
    def test_the_review_step_files_each_deferred_finding_before_the_pr_merges(self):
        # The ticket says "build step 8", counting before #127 added a design step; that step is now 9.
        number, _, body = build_step("Review each PR")
        self.assertEqual(number, 9)
        for phrase in ("Before a PR merges", "deferred", "filed as an issue", "linked from the PR body"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, body)


class SharedFilesTest(unittest.TestCase):
    def test_ticket_prs_change_only_the_languages_own_files(self):
        _, _, body = build_step("Build each ticket")
        self.assertIn("only its own skill directories, its own CI job, and its own drift test", body)
        self.assertIn("](../../../CONTRIBUTING.md#shared-rules-for-every-language)", body)

    def test_the_version_bump_happens_only_in_the_main_pr_after_merging_main(self):
        _, _, body = build_step("Open the main PR")
        for phrase in ("merge `origin/main`", "Only the main PR bumps the version", "after that merge",
                       "](../../../CONTRIBUTING.md#"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, body)

    def test_the_main_pr_bump_is_in_its_done_condition(self):
        # validate.py checks only that the three versions agree, not that the main PR moved them past main.
        _, _, body = build_step("Open the main PR")
        done = body.split("Done when", 1)[1]
        self.assertIn("bumps the version in all three manifests", done)
        self.assertIn("past the one `main` has", done)

    def test_the_main_pr_may_open_from_a_working_branch(self):
        # Go's agent could not push to the integration branch and opened #102 from a working branch.
        _, _, body = build_step("Open the main PR")
        self.assertIn("working branch", body)
        self.assertIn("#102", body)

    def test_the_release_ticket_pr_does_the_readme_and_catalogs(self):
        # CONTRIBUTING.md Pull requests: the release ticket PR updates the catalogs, the dependencies, and the
        # README; the main PR bumps the version. The skill, the ticket breakdown, and the gotchas must agree.
        _, _, build = build_step("Build each ticket")
        self.assertIn("the release ticket PR updates the README, the catalogs, and the company-skills dependencies",
                      build)
        _, _, main_pr = build_step("Open the main PR")
        self.assertNotIn("README, catalog, and version changes", main_pr)
        tickets = read(SKILL_DIR / "references" / "tickets.md")
        release = next(line for line in tickets.splitlines() if line.startswith("5. **Release ticket.**"))
        for phrase in ("remove it from every catalog", "Update the README", "uninstall steps", "main PR"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, release)
        self.assertIn("**Criterion** for ticket 5.", gotcha("The validator checks both catalogs."))
        contributing = read(REPO / "CONTRIBUTING.md")
        upstream = section(contributing, "Language skills").split("### Taking in upstream material", 1)[1]
        self.assertIn("The release ticket PR", upstream)
        self.assertNotIn("The language's main PR, which merges", upstream)

    def test_agents_md_lets_ticket_prs_leave_the_readme(self):
        # AGENTS.md otherwise makes a README update part of every published-skill change.
        agents = read(REPO / "AGENTS.md")
        self.assertIn("release ticket PR", agents)

    def test_no_ticket_bumps_the_version(self):
        tickets = read(SKILL_DIR / "references" / "tickets.md")
        self.assertNotIn("Bump the version", tickets)
        self.assertIn("main PR bumps the version", tickets)


class FeedBackTest(unittest.TestCase):
    def test_the_last_build_step_files_what_the_run_learned(self):
        build = section(read(SKILL_DIR / "SKILL.md"), "Build")
        number, title, body = numbered_steps(build)[-1]
        main_pr, _, _ = build_step("Open the main PR")
        self.assertGreater(number, main_pr)
        self.assertEqual(title, "File what the run learned.")
        for phrase in ("one issue", "deviations", "process findings", "`building-language-skills`",
                       "linked from the main PR", "next pass"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, body)

    def test_the_report_names_the_feed_back_issue(self):
        report = section(read(SKILL_DIR / "SKILL.md"), "Report")
        self.assertIn("deviations and process findings", report)


class RenameTest(unittest.TestCase):
    def test_the_skill_is_named_building_language_skills(self):
        self.assertTrue((SKILL_DIR / "SKILL.md").exists())
        self.assertFalse((REPO / ".claude" / "skills" / OLD_NAME).exists())
        self.assertIn("\nname: building-language-skills\n", read(SKILL_DIR / "SKILL.md"))

    def test_no_tracked_file_names_the_old_skill(self):
        # -z keeps paths with spaces whole and stops git quoting non-ASCII paths.
        files = subprocess.run(["git", "ls-files", "-z"], cwd=REPO, capture_output=True, text=True, check=True).stdout
        for name in filter(None, files.split("\0")):
            path = REPO / name
            if not path.is_file() or path.suffix not in {".md", ".py", ".js", ".json", ".yml", ".yaml", ".toml"}:
                continue
            with self.subTest(file=name):
                self.assertNotIn(OLD_NAME, read(path))

    def test_the_description_still_triggers_on_a_pair_request(self):
        frontmatter = read(SKILL_DIR / "SKILL.md").split("\n---\n", 1)[0]
        description = next(line for line in frontmatter.splitlines() if line.startswith("description:"))
        self.assertIn("Python pair", description)

    def test_pair_is_not_used_outside_the_description(self):
        paths = [REPO / "CONTRIBUTING.md", REPO / "README.md", REPO / "AGENTS.md"]
        paths += sorted(SKILL_DIR.rglob("*.md"))
        for path in paths:
            text = read(path)
            if path == SKILL_DIR / "SKILL.md":
                text = "\n".join(line for line in text.splitlines() if not line.startswith("description:"))
            with self.subTest(file=str(path.relative_to(REPO))):
                self.assertEqual(PAIR.findall(text), [])


if __name__ == "__main__":
    unittest.main()
