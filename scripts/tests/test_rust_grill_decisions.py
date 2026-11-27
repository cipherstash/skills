"""Tests that the Rust grill's decisions are recorded in the shared text, as ticket #153 drafted them.

The Rust grill folded `rust-sdk-dx`, `rust-security` and `rust-testing` into `rust-practices` (ADR 0004), widened
Rust's execution surface to any dependency change (ADR 0005), and gave Rust's check suite conditional checks
(ADR 0006, GLOSSARY.md **Conditional check**). A Rust PR may not write shared text, so these land on their own.
With `rust-practices` coming, CONTRIBUTING.md no longer exempts Rust from the practices-skill rules.
"""

from pathlib import Path
import unittest

from test_contributing_links import relative_links, section


REPO = Path(__file__).resolve().parents[2]
ADR = REPO / "docs/adr"
CONTRIBUTING = REPO / "CONTRIBUTING.md"
GLOSSARY = REPO / "GLOSSARY.md"
TICKETS = REPO / ".claude/skills/building-language-skills/references/tickets.md"

ADR_0004 = "docs/adr/0004-fold-the-rust-convention-skills-into-rust-practices.md"
ADR_0005 = "docs/adr/0005-rust-reviews-ask-before-building-any-dependency-change.md"
ADR_0006 = "docs/adr/0006-rust-check-suite-has-conditional-checks.md"


def read(path):
    return path.read_text(encoding="utf-8")


class AdrTest(unittest.TestCase):
    def assert_adr(self, path, title, phrases):
        file = REPO / path
        self.assertTrue(file.exists(), f"{path} does not exist")
        text = read(file)
        self.assertTrue(text.startswith(f"# {title}\n\nStatus: accepted, 2026-11-27\n"), text[:200])
        for heading in ("## Considered options", "## Consequences"):
            with self.subTest(heading=heading):
                self.assertIn(f"\n{heading}\n", text)
        for phrase in phrases:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_adr_0004_folds_the_three_skills_into_rust_practices(self):
        self.assert_adr(ADR_0004, "Fold the Rust convention skills into rust-practices", (
            "We fold the three into `rust-practices` as references",
            "`rust-review` reads only `rust-practices`",
            "**Add `rust-practices` beside the three, linking to them by name.** Rejected",
            "deprecated aliases for one release, under **Renaming a skill**",
        ))

    def test_adr_0005_puts_every_dependency_change_on_the_execution_surface(self):
        self.assert_adr(ADR_0005, "Rust reviews ask before building any dependency change", (
            "any added or changed dependency in `Cargo.toml` or `Cargo.lock`",
            "Compiles run offline.",
            "never with `cargo install`",
            "**Trust dependencies once they are in the lockfile.** Rejected",
            "Every Dependabot PR asks before clippy or tests run.",
        ))

    def test_adr_0006_gives_rusts_suite_conditional_checks(self):
        self.assert_adr(ADR_0006, "Rust's check suite has conditional checks", (
            "Miri for `unsafe`, cargo-semver-checks and a publish dry run for published crates",
            "the review reports a missing-check line",
            "**Require them for every crate.** Rejected",
            "this ADR covers only Rust",
        ))

    def test_numbers_are_unique(self):
        numbers = [path.name[:4] for path in ADR.glob("[0-9][0-9][0-9][0-9]-*.md")]
        self.assertEqual(sorted(set(numbers)), sorted(numbers))


class GlossaryTest(unittest.TestCase):
    def test_conditional_check_is_a_language_skills_term(self):
        body = section(read(GLOSSARY), "Language skills")
        self.assertIn(
            "**Conditional check**:\n"
            "A check in a language's check suite that applies only to a module or crate with a named property, such as "
            "Rust's Miri for crates that contain `unsafe`. Where the property holds, the check must be in place like "
            "any other.\n"
            "_Avoid_: Optional check, tier 2\n",
            body,
        )


class ContributingTest(unittest.TestCase):
    def setUp(self):
        self.text = read(CONTRIBUTING)
        self.language_skills = section(self.text, "Language skills")

    def test_rust_is_no_longer_exempt(self):
        for phrase in ("Rust is exempt", "The exemption ends when a `rust-practices` skill is added."):
            with self.subTest(phrase=phrase):
                self.assertNotIn(phrase, self.text)

    def test_names_rusts_decision_and_links_adr_0004(self):
        self.assertIn(
            "A language that already has convention skills needs a decision like this before you build its skills. "
            "Rust folded its three into `rust-practices` ([ADR 0004](" + ADR_0004 + ")).",
            self.language_skills,
        )
        self.assertIn(ADR_0004, set(relative_links(self.language_skills)))

    def test_release_ticket_may_update_skills_that_name_replaced_ones(self):
        pull_requests = self.language_skills.split("\nPull requests:\n", 1)[1].split("\n### ", 1)[0]
        self.assertIn(
            "- When a language's skills replace released convention skills, the release ticket PR may also update "
            "other skills that name them, as Rust's does for `aws-service-architecture` and `review-post`.\n",
            pull_requests,
        )


class TicketsTest(unittest.TestCase):
    def test_option_two_no_longer_cites_the_rust_exemption(self):
        text = read(TICKETS)
        self.assertNotIn("Rust exemption", text)


if __name__ == "__main__":
    unittest.main()
