"""Tests that CONTRIBUTING.md points skill authors at the shared language decisions, and that its links resolve.

The shared rules for every language's skills are settled in GLOSSARY.md and docs/adr/ (ADR 0003). CONTRIBUTING.md's
Language skills section states them and links their source, so an author reads them once instead of deciding again.
"""

from pathlib import Path
import re
import tempfile
import unittest


REPO = Path(__file__).resolve().parents[2]
CONTRIBUTING = REPO / "CONTRIBUTING.md"
# A link's target: bare, or in angle brackets when it holds spaces, optionally followed by a quoted title.
LINK = re.compile(r'\[[^\]]*\]\(\s*(?:<([^>\n]+)>|([^)\s]+))(?:\s+"[^"]*")?\s*\)')
# A fenced code block opens with three or more backticks or tildes, indented by at most three spaces.
FENCE = re.compile(r" {0,3}(`{3,}|~{3,})")
CODE_SPAN = re.compile(r"(`+).+?\1")


def section(text, heading):
    """Return the body of the level-2 section with this heading, up to the next level-2 heading."""
    marker = f"\n## {heading}\n"
    text = "\n" + text
    if marker not in text:
        raise ValueError(f"no '## {heading}' heading")
    return text.split(marker, 1)[1].split("\n## ", 1)[0]


def unfenced_lines(text):
    """Yield the lines of Markdown text that are outside fenced code blocks.

    As CommonMark does, a fence closes only on the same character as the one that opened it, at least as long, with
    nothing after it.
    """
    fence = None
    for line in text.splitlines():
        match = FENCE.match(line)
        if fence is None:
            if match:
                fence = match.group(1)
            else:
                yield line
        elif (
            match
            and match.group(1)[0] == fence[0]
            and len(match.group(1)) >= len(fence)
            and not line[match.end():].strip()
        ):
            fence = None


def anchors(path):
    """Return the GitHub anchors of the Markdown headings in a file.

    As GitHub does, keep letters, digits, underscores, hyphens and spaces, turn spaces into hyphens, and give the
    second and later headings with the same anchor a -1, -2, ... suffix.
    """
    found = set()
    seen = {}
    for line in unfenced_lines(path.read_text(encoding="utf-8")):
        match = re.match(r"#{1,6} +(.*?) *#*$", line)
        if match:
            slug = re.sub(r"[^\w\- ]", "", match.group(1).lower()).replace(" ", "-")
            count = seen.get(slug, 0)
            seen[slug] = count + 1
            found.add(f"{slug}-{count}" if count else slug)
    return found


def relative_links(text):
    """Yield each link target that is not an absolute URL, skipping links quoted in code."""
    prose = "\n".join(CODE_SPAN.sub("", line) for line in unfenced_lines(text))
    for angled, bare in LINK.findall(prose):
        target = angled or bare
        if not re.match(r"[a-z]+:", target):
            yield target


class AnchorsTest(unittest.TestCase):
    def anchors_of(self, markdown):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "doc.md"
            path.write_text(markdown, encoding="utf-8")
            return anchors(path)

    def test_keeps_underscores_as_github_does(self):
        self.assertIn(
            "the-allow_implicit_invocation-policy",
            self.anchors_of("## The `allow_implicit_invocation` policy\n"),
        )

    def test_numbers_repeated_headings_as_github_does(self):
        self.assertEqual(
            {"setup", "setup-1", "setup-2"},
            self.anchors_of("## Setup\n\n### Setup\n\n## Setup\n"),
        )

    def test_skips_headings_in_tilde_and_indented_fences(self):
        for fence in ("~~~", "  ```"):
            with self.subTest(fence=fence):
                self.assertEqual({"setup"}, self.anchors_of(f"{fence}\n# Setup\n{fence}\n\n## Setup\n"))

    def test_closes_a_fence_only_on_its_own_marker_at_its_length(self):
        self.assertEqual(
            {"setup"},
            self.anchors_of("````\n```\n# Setup\n```\n~~~\n````\n\n## Setup\n"),
        )


class RelativeLinksTest(unittest.TestCase):
    def test_reads_titled_and_angle_bracket_targets(self):
        self.assertEqual(
            ["GLOSARY.md", "a b.md"],
            list(relative_links('[x](GLOSARY.md "t") and [y](<a b.md>)')),
        )

    def test_skips_links_quoted_in_code(self):
        self.assertEqual(
            ["real.md"],
            list(relative_links("`[x](y)`\n\n```\n[x](z)\n```\n\n[r](real.md)\n")),
        )


class SectionTest(unittest.TestCase):
    def test_names_a_missing_heading(self):
        with self.assertRaises(Exception) as raised:
            section("# x\n## Other\n", "Language skills")
        self.assertIsInstance(raised.exception, ValueError)
        self.assertIn("## Language skills", str(raised.exception))

    def test_matches_only_a_level_2_heading(self):
        self.assertEqual("b", section("# x\n### Pinned\na\n## Pinned\nb\n## Next\n", "Pinned"))


class ContributingLinksTest(unittest.TestCase):
    def setUp(self):
        self.text = CONTRIBUTING.read_text(encoding="utf-8")

    def test_language_skills_links_the_shared_decisions(self):
        links = set(relative_links(section(self.text, "Language skills")))
        for target in (
            "docs/adr/0001-one-check-suite-policy-for-every-language.md",
            "docs/adr/0002-reviews-run-no-code-from-the-change-without-a-yes.md",
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
