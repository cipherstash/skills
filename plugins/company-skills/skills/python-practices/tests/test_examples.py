# Tests for the python-practices references and the examples project they quote.
# Run: python3 -m unittest discover -s tests (from the skill directory).
#
# The Python check suite (references/checks.md) runs over the examples project in
# CI, in the validate workflow's python-check-suite job. These tests run none of
# the suite's checks. They check that every quoted block matches its source, and
# that the references and the config template say what the suite needs.
import re
import tomllib
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
EXAMPLES = SKILL / "examples"
REFERENCES = SKILL / "references"
TEMPLATE = SKILL / "assets" / "pyproject-checks.toml"

# The references this slice builds (cipherstash/skills#156). The rest of the
# areas in spec #154 arrive in later tickets, each adding its name here.
EXPECTED_REFERENCES = {"checks.md", "errors.md", "typing.md"}
# Each reference aims for under 100 lines. Spec #154 lets typing.md reach about 150.
LINE_LIMITS = {"typing.md": 150}
DEFAULT_LINE_LIMIT = 100

# Fenced code blocks follow CommonMark: an opener is up to three spaces of
# indent, then three or more backticks or tildes, then an info string whose
# first word is the language. A backtick opener's info string has no backtick.
OPENER_RE = re.compile(r"^(?P<indent> {0,3})(?P<fence>`{3,}|~{3,})(?P<info>.*)$")
LANGUAGES = ("python", "py", "python3", "pycon", "toml")
# Any line that looks like it opens a quoted block, at any indent. Every such
# line outside another block must be a real opener, so no block is skipped.
LIKE_RE = re.compile(
    rf"^\s*(?:`{{3,}}|~{{3,}})\s*(?:{'|'.join(LANGUAGES)})(?:\s|$)", re.IGNORECASE
)
SOURCE_RE = re.compile(r"\]\(\.\./examples/([^)#\s]+\.(?:py|toml))\)")
PYTHON_VERSION = "3.12"


def closes(line, fence):
    """Report whether line closes a block opened with fence.

    A closer has up to three spaces of indent, whatever the opener's indent, then
    at least as many of the same fence character, then only whitespace.
    """
    stripped = line.lstrip(" ")
    if len(line) - len(stripped) > 3:
        return False
    run = len(stripped) - len(stripped.lstrip(fence[0]))
    return run >= len(fence) and not stripped[run:].strip()


def swallows(line, fence):
    """Report whether line, inside a block opened with fence, looks like a missing closer.

    The line looks like a Python or TOML opener and uses the outer fence's
    character at least as many times, so it cannot be a fence nested on purpose:
    a nested block needs a shorter fence than the block around it. Such a line
    almost always means the block above it has no closer of its own.
    """
    if not LIKE_RE.match(line):
        return False
    stripped = line.lstrip()
    return len(stripped) - len(stripped.lstrip(fence[0])) >= len(fence)


def parse_fences(text):
    """Return (blocks, problems) for the quoted Python and TOML blocks in text.

    blocks is a list of (line number, source path or None, code). Each code line
    has up to the opener's indent removed. problems lists, by line, each line that
    looks like a Python or TOML fence but opens no block, each block of any
    language with no closer, and each line inside a block that looks like a
    missing closer (see swallows).
    """
    blocks, problems = [], []
    lines = text.splitlines(keepends=True)
    i = 0
    while i < len(lines):
        line = lines[i].rstrip("\n")
        opener = OPENER_RE.match(line)
        if opener and opener["fence"][0] == "`" and "`" in opener["info"]:
            opener = None
        if not opener:
            if LIKE_RE.match(line):
                problems.append(f"line {i + 1}: looks like a fence but does not open one")
            i += 1
            continue
        fence, indent = opener["fence"], len(opener["indent"])
        words = opener["info"].split()
        quoted = bool(words) and words[0].lower() in LANGUAGES
        body, j = [], i + 1
        while j < len(lines) and not closes(lines[j].rstrip("\n"), fence):
            content = lines[j]
            if swallows(content.rstrip("\n"), fence):
                problems.append(f"line {j + 1}: looks like a fence but sits inside the block opened on line {i + 1}")
            body.append(content[min(indent, len(content) - len(content.lstrip(" "))) :])
            j += 1
        if j == len(lines):
            problems.append(f"line {i + 1}: block has no closing fence")
        elif quoted:
            lead = next((l for l in reversed(lines[:i]) if l.strip()), "")
            source = SOURCE_RE.search(lead)
            blocks.append((i + 1, source.group(1) if source else None, "".join(body)))
        i = j + 1
    return blocks, problems


def quoted_blocks(text):
    """Yield (line number, source path or None, code) for each quoted block in text."""
    yield from parse_fences(text)[0]


def excerpt_problem(code, source_text):
    """Return why code is not a whole-item excerpt of source_text, or None.

    A quoted block must be non-empty and must match a run of whole lines in the
    source that starts after a blank line (or the start of the file) and ends
    before a blank line (or the end of the file), so it cannot begin or end in
    the middle of a definition, a table, or its docstring.
    """
    if not code.strip():
        return "block is empty"
    block = code.splitlines()
    lines = source_text.splitlines()
    for start in range(len(lines) - len(block) + 1):
        if lines[start : start + len(block)] != block:
            continue
        end = start + len(block)
        if (start == 0 or not lines[start - 1].strip()) and (
            end == len(lines) or not lines[end].strip()
        ):
            return None
    if code not in source_text:
        return "block is not a verbatim excerpt"
    return "block starts or ends inside a definition"


class QuotedSnippetsTest(unittest.TestCase):
    def references(self):
        paths = sorted(REFERENCES.glob("*.md"))
        self.assertTrue(paths, "no references found")
        return paths

    def test_every_block_is_quoted_from_the_examples_project(self):
        for path in self.references():
            text = path.read_text(encoding="utf-8")
            for line, source, code in quoted_blocks(text):
                where = f"{path.name}:{line}"
                with self.subTest(block=where):
                    self.assertIsNotNone(
                        source,
                        f"{where}: put a link to ../examples/<file> on the line before the block",
                    )
                    target = (EXAMPLES / source).resolve()
                    self.assertTrue(target.is_relative_to(EXAMPLES.resolve()), where)
                    self.assertTrue(target.is_file(), f"{where}: {source} does not exist")
                    problem = excerpt_problem(code, target.read_text(encoding="utf-8"))
                    self.assertIsNone(problem, f"{where}: {problem} (examples/{source})")

    def test_no_block_is_skipped(self):
        for path in self.references():
            with self.subTest(reference=path.name):
                self.assertEqual(parse_fences(path.read_text(encoding="utf-8"))[1], [])

    def test_each_reference_states_its_python_version_and_the_floor_rule(self):
        for path in self.references():
            text = path.read_text(encoding="utf-8")
            with self.subTest(reference=path.name):
                self.assertIn(f"targets Python {PYTHON_VERSION}", text)
                self.assertIn("`requires-python`", text)

    def test_each_reference_keeps_to_its_length(self):
        for path in self.references():
            lines = path.read_text(encoding="utf-8").splitlines()
            limit = LINE_LIMITS.get(path.name, DEFAULT_LINE_LIMIT)
            with self.subTest(reference=path.name):
                self.assertLessEqual(len(lines), limit)
                if len(lines) > 100:
                    first_section = next((l for l in lines if l.startswith("## ")), "")
                    self.assertEqual(first_section, "## Contents")


class ReferenceIndexTest(unittest.TestCase):
    def test_every_area_has_a_reference(self):
        found = {path.name for path in REFERENCES.glob("*.md")}
        self.assertEqual(found, EXPECTED_REFERENCES)

    def test_skill_md_links_every_reference(self):
        text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        for name in sorted(EXPECTED_REFERENCES):
            with self.subTest(reference=name):
                self.assertIn(f"](references/{name})", text)


class ConfigTemplateTest(unittest.TestCase):
    def test_the_examples_project_uses_the_template_unchanged(self):
        template = tomllib.loads(TEMPLATE.read_text(encoding="utf-8"))
        project = tomllib.loads((EXAMPLES / "pyproject.toml").read_text(encoding="utf-8"))
        for table, value in template.items():
            with self.subTest(table=table):
                self.assertEqual(project.get(table), value)
        self.assertEqual(
            set(project["tool"]), set(template["tool"]), "the project sets tool config the template lacks"
        )

    def test_the_template_selects_the_families_checks_md_lists(self):
        text = (REFERENCES / "checks.md").read_text(encoding="utf-8")
        lint = next(line for line in text.splitlines() if line.startswith("- **Lint**"))
        families = re.findall(r"`([A-Z]+[0-9]*)`", lint.split("Tests may ignore")[0])
        ignores = re.findall(r"`(S10[0-9])`", lint.split("Tests may ignore")[1])
        ruff = tomllib.loads(TEMPLATE.read_text(encoding="utf-8"))["tool"]["ruff"]["lint"]
        self.assertEqual(ruff["select"], families)
        for pattern, codes in ruff.get("per-file-ignores", {}).items():
            with self.subTest(pattern=pattern):
                self.assertLessEqual(set(codes), set(ignores))

    def test_the_template_is_strict_and_sets_no_threshold(self):
        template = tomllib.loads(TEMPLATE.read_text(encoding="utf-8"))
        self.assertEqual(template["tool"]["mypy"], {"python_version": PYTHON_VERSION, "strict": True})
        self.assertIs(template["tool"]["coverage"]["run"]["branch"], True)
        self.assertNotIn("fail_under", template["tool"]["coverage"].get("report", {}))

    def test_build_output_is_ignored(self):
        ignored = (EXAMPLES / ".gitignore").read_text(encoding="utf-8").splitlines()
        self.assertLessEqual({"__pycache__/", ".venv/"}, set(ignored))

    def test_the_lockfile_is_committed(self):
        self.assertTrue((EXAMPLES / "uv.lock").is_file())


class QuotedBlocksParserTest(unittest.TestCase):
    LINK = "From [`a.py`](../examples/src/pkg/a.py):\n\n"

    def test_reads_source_from_the_line_before_the_fence(self):
        text = self.LINK + "```python\ndef a() -> None: ...\n```\n"
        self.assertEqual(list(quoted_blocks(text)), [(3, "src/pkg/a.py", "def a() -> None: ...\n")])

    def test_reads_a_toml_source(self):
        text = "From [`pyproject.toml`](../examples/pyproject.toml):\n\n```toml\n[tool.mypy]\n```\n"
        self.assertEqual(list(quoted_blocks(text)), [(3, "pyproject.toml", "[tool.mypy]\n")])

    def test_block_without_a_source_link(self):
        text = "Some prose.\n\n```python\nx = 1\n```\n"
        self.assertEqual(list(quoted_blocks(text)), [(3, None, "x = 1\n")])

    def test_rejects_an_empty_block(self):
        self.assertEqual(excerpt_problem("\n", "x = 1\n"), "block is empty")

    def test_accepts_whole_definitions(self):
        source = '"""Doc."""\n\n\ndef a() -> None:\n    pass\n\n\ndef b() -> None:\n    pass\n'
        self.assertIsNone(excerpt_problem("def a() -> None:\n    pass\n", source))
        self.assertIsNone(excerpt_problem("def b() -> None:\n    pass\n", source))

    def test_rejects_a_partial_definition(self):
        source = "def a() -> None:\n    x = 1\n    return\n"
        cut = "block starts or ends inside a definition"
        self.assertEqual(excerpt_problem("def a() -> None:\n", source), cut)
        self.assertEqual(excerpt_problem("    return\n", source), cut)
        self.assertEqual(excerpt_problem("turn\n", source), cut)

    def test_rejects_text_not_in_the_source(self):
        self.assertEqual(excerpt_problem("y = 2\n", "x = 1\n"), "block is not a verbatim excerpt")

    def test_reads_every_alias_and_fence_form(self):
        for language in LANGUAGES + ("Python",):
            for fence, close in (("```", "```"), ("~~~", "~~~"), ("````", "````"), ("```", "````")):
                opener = f"{fence}{language} title"
                with self.subTest(opener=opener, close=close):
                    text = f"{self.LINK}{opener}\nx = 1\n{close}\n"
                    self.assertEqual(list(quoted_blocks(text)), [(3, "src/pkg/a.py", "x = 1\n")])

    def test_reads_an_indented_fence(self):
        text = "1. From [`a.py`](../examples/src/pkg/a.py):\n\n   ```py\n   x = 1\n   ```\n"
        self.assertEqual(list(quoted_blocks(text)), [(3, "src/pkg/a.py", "x = 1\n")])

    def test_reads_an_indented_fence_closed_at_column_zero(self):
        text = self.LINK + "  ```python\n  x = 1\n```\n"
        self.assertEqual(list(quoted_blocks(text)), [(3, "src/pkg/a.py", "x = 1\n")])

    def test_a_shorter_or_different_fence_does_not_close(self):
        text = "````python\nx = 1\n```\n~~~~\n````\n"
        self.assertEqual(list(quoted_blocks(text)), [(1, None, "x = 1\n```\n~~~~\n")])

    def test_a_closer_needs_only_whitespace_after_it(self):
        text = "```python\nx = 1\n``` x\n```  \n"
        self.assertEqual(list(quoted_blocks(text)), [(1, None, "x = 1\n``` x\n")])

    def test_reports_a_block_with_no_closer(self):
        for language in LANGUAGES:
            with self.subTest(language=language):
                self.assertEqual(
                    parse_fences(f"```{language}\nx = 1\n")[1], ["line 1: block has no closing fence"]
                )

    def test_reports_a_fence_like_line_that_opens_nothing(self):
        for language in LANGUAGES:
            with self.subTest(language=language):
                self.assertEqual(
                    parse_fences(f"    ```{language}\nx = 1\n    ```\n")[1],
                    ["line 1: looks like a fence but does not open one"],
                )

    def test_a_backtick_in_a_backtick_info_string_opens_nothing(self):
        self.assertEqual(
            parse_fences("```python `x`\nx = 1\n")[1],
            ["line 1: looks like a fence but does not open one"],
        )

    def test_ignores_a_fence_inside_another_block(self):
        text = "````md\n```python\nx = 1\n```\n````\n"
        self.assertEqual(parse_fences(text), ([], []))

    def test_ignores_other_languages(self):
        text = "```sh\nuv run pytest\n```\n"
        self.assertEqual(parse_fences(text), ([], []))

    def test_reports_any_block_with_no_closer(self):
        for opener in ("```sh", "~~~", "```"):
            with self.subTest(opener=opener):
                self.assertEqual(
                    parse_fences(f"{opener}\nuv run\n")[1], ["line 1: block has no closing fence"]
                )

    def test_reports_a_quoted_opener_swallowed_by_an_unclosed_block(self):
        # The sh block never closes, so the python opener is its body and the python closer closes it.
        text = "```sh\nuv run\n\n" + self.LINK + "```python\nx = 1\n```\n"
        self.assertEqual(
            parse_fences(text),
            ([], ["line 6: looks like a fence but sits inside the block opened on line 1"]),
        )


if __name__ == "__main__":
    unittest.main()
