"""Tests that CONTRIBUTING.md points skill authors at the shared language decisions, and that its links resolve.

The shared rules for every language's skills are settled in GLOSSARY.md and docs/adr/ (ADR 0003). CONTRIBUTING.md's
Language skills section states them and links their source, so an author reads them once instead of deciding again.
"""

from pathlib import Path
import re
import unittest


REPO = Path(__file__).resolve().parents[2]
CONTRIBUTING = REPO / "CONTRIBUTING.md"
LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")


def section(text, heading):
    """Return the body of the level-2 section with this heading, up to the next level-2 heading."""
    return text.split(f"\n## {heading}\n", 1)[1].split("\n## ", 1)[0]


def anchors(path):
    """Return the GitHub anchors of the Markdown headings in a file."""
    found = set()
    in_fence = False
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("```"):
            in_fence = not in_fence
            continue
        match = None if in_fence else re.match(r"#{1,6} +(.*?) *#*$", line)
        if match:
            title = re.sub(r"[`*_]", "", match.group(1)).lower()
            found.add(re.sub(r"[^\w\- ]", "", title).replace(" ", "-"))
    return found


def relative_links(text):
    """Yield each link target that is not an absolute URL."""
    for target in LINK.findall(text):
        if not re.match(r"[a-z]+:", target):
            yield target


class ContributingLinksTest(unittest.TestCase):
    def setUp(self):
        self.text = CONTRIBUTING.read_text(encoding="utf-8")
        self.language_skills = section(self.text, "Language skills")

    def test_language_skills_links_the_shared_decisions(self):
        links = set(relative_links(self.language_skills))
        for target in (
            "docs/adr/0001-one-check-suite-policy-for-every-language.md",
            "docs/adr/0003-settle-shared-language-decisions-once.md",
            "GLOSSARY.md#language-skills",
        ):
            with self.subTest(target=target):
                self.assertIn(target, links)

    def test_relative_links_resolve(self):
        for target in relative_links(self.text):
            with self.subTest(target=target):
                path, _, anchor = target.partition("#")
                resolved = (CONTRIBUTING.parent / path) if path else CONTRIBUTING
                self.assertTrue(resolved.exists(), f"{path} does not exist")
                if anchor and resolved.suffix == ".md":
                    self.assertIn(anchor, anchors(resolved))


if __name__ == "__main__":
    unittest.main()
