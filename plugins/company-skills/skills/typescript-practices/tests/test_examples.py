# Tests for the typescript-practices examples package and the references that quote it.
# Run: python3 -m unittest discover -s tests (from the skill directory).
#
# The TypeScript check suite (references/checks.md) runs over the examples package in CI, in the validate workflow's
# typescript-check-suite job. These tests run none of the suite's checks, and need no Node. They check only that every
# quoted block matches its source, that every example is quoted, and that each reference states the minimum versions
# the examples package targets.
import json
import re
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
EXAMPLES = SKILL / "examples"
REFERENCES = SKILL / "references"

# The references this slice builds (cipherstash/skills#147). The rest of the areas come in #148.
EXPECTED_REFERENCES = {
    "checks.md",
    "error-handling.md",
    "type-safety.md",
}

# Fenced code blocks follow CommonMark: an opener is up to three spaces of indent, then three or more backticks or
# tildes, then an info string whose first word is the language. A backtick opener's info string has no backtick.
OPENER_RE = re.compile(r"^(?P<indent> {0,3})(?P<fence>`{3,}|~{3,})(?P<info>.*)$")
# The fence aliases of TypeScript and of the JavaScript files in a TypeScript repository.
LANGUAGES = {"ts", "typescript", "tsx", "js", "javascript", "mjs", "cjs"}
# Any line that looks like it opens a block in one of LANGUAGES, at any indent. Every such line outside another block
# must be a real opener, so no block is skipped.
LIKE_RE = re.compile(
    r"^\s*(?:`{3,}|~{3,})\s*(?:" + "|".join(sorted(LANGUAGES)) + r")(?:\s|$)", re.IGNORECASE
)
SOURCE_RE = re.compile(r"\]\(\.\./examples/([^)#]+\.(?:ts|tsx|mts|cts|js|mjs|cjs))\)")
# The source files that are examples: every module under src/ except the tests and the package entry point.
EXAMPLE_SOURCE = "src/**/*.ts"


def minimum_versions():
    """Return (TypeScript major.minor, Node major) that the examples package targets, from its package.json."""
    package = json.loads((EXAMPLES / "package.json").read_text(encoding="utf-8"))
    typescript = re.fullmatch(r"(\d+\.\d+)\.\d+", package["devDependencies"]["typescript"])
    node = re.fullmatch(r">=(\d+)", package["engines"]["node"])
    if not typescript or not node:
        raise AssertionError("examples/package.json needs an exact typescript and an engines.node of >=<major>")
    return typescript.group(1), node.group(1)


def closes(line, fence):
    """Report whether line closes a block opened with fence.

    A closer has up to three spaces of indent, whatever the opener's indent, then at least as many of the same fence
    character, then only whitespace.
    """
    stripped = line.lstrip(" ")
    if len(line) - len(stripped) > 3:
        return False
    run = len(stripped) - len(stripped.lstrip(fence[0]))
    return run >= len(fence) and not stripped[run:].strip()


def parse_fences(text):
    """Return (blocks, problems) for the TypeScript and JavaScript blocks in text.

    blocks is a list of (line number, source path or None, code). Each code line has up to the opener's indent
    removed. problems lists, by line, each line that looks like such a fence but is not a valid opener, and each such
    block with no closer.
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
                problems.append(f"line {i + 1}: looks like a TypeScript or JavaScript fence but does not open one")
            i += 1
            continue
        fence, indent = opener["fence"], len(opener["indent"])
        words = opener["info"].split()
        counted = bool(words) and words[0].lower() in LANGUAGES
        body, j = [], i + 1
        while j < len(lines) and not closes(lines[j].rstrip("\n"), fence):
            content = lines[j]
            body.append(content[min(indent, len(content) - len(content.lstrip(" "))) :])
            j += 1
        if counted:
            if j == len(lines):
                problems.append(f"line {i + 1}: block has no closing fence")
            else:
                lead = next((l for l in reversed(lines[:i]) if l.strip()), "")
                source = SOURCE_RE.search(lead)
                blocks.append((i + 1, source.group(1) if source else None, "".join(body)))
        i = j + 1
    return blocks, problems


def quoted_blocks(text):
    """Yield (line number, source path or None, code) for each TypeScript or JavaScript block in text."""
    yield from parse_fences(text)[0]


def excerpt_problem(code, source_text):
    """Return why code is not a whole-declaration excerpt of source_text, or None.

    A quoted block must be non-empty and must match a run of whole lines in the source that starts after a blank line
    (or the start of the file) and ends before a blank line (or the end of the file), so it cannot begin or end in the
    middle of a declaration or its comment.
    """
    if not code.strip():
        return "block is empty"
    block = code.splitlines()
    lines = source_text.splitlines()
    for start in range(len(lines) - len(block) + 1):
        if lines[start : start + len(block)] != block:
            continue
        end = start + len(block)
        if (start == 0 or not lines[start - 1].strip()) and (end == len(lines) or not lines[end].strip()):
            return None
    if code not in source_text:
        return "block is not a verbatim excerpt"
    return "block starts or ends inside a declaration or comment"


def references():
    return sorted(REFERENCES.glob("*.md"))


def example_modules():
    """Return the example modules, relative to examples/: every source module except tests and src/index.ts."""
    return sorted(
        path.relative_to(EXAMPLES).as_posix()
        for path in EXAMPLES.glob(EXAMPLE_SOURCE)
        if not path.name.endswith(".test.ts") and path.relative_to(EXAMPLES).as_posix() != "src/index.ts"
    )


class QuotedSnippetsTest(unittest.TestCase):
    def setUp(self):
        self.assertTrue(references(), "no references found")

    def test_every_block_is_quoted_from_the_examples_package(self):
        for path in references():
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
                    self.assertNotIn("node_modules", target.relative_to(EXAMPLES.resolve()).parts, where)
                    self.assertTrue(target.is_file(), f"{where}: {source} does not exist")
                    problem = excerpt_problem(code, target.read_text(encoding="utf-8"))
                    self.assertIsNone(problem, f"{where}: {problem} (examples/{source})")

    def test_no_block_is_skipped(self):
        for path in references():
            with self.subTest(reference=path.name):
                self.assertEqual(parse_fences(path.read_text(encoding="utf-8"))[1], [])

    def test_every_example_module_is_quoted(self):
        # An example no reference quotes is code beyond the spec's examples list.
        quoted = {
            source for path in references() for _, source, _ in quoted_blocks(path.read_text(encoding="utf-8"))
        }
        modules = example_modules()
        self.assertTrue(modules, "no example modules found")
        self.assertEqual([module for module in modules if module not in quoted], [])

    def test_each_reference_states_its_minimum_versions(self):
        typescript, node = minimum_versions()
        for path in references():
            with self.subTest(reference=path.name):
                text = path.read_text(encoding="utf-8")
                self.assertIn(f"TypeScript {typescript}", text)
                self.assertIn(f"Node {node}", text)

    def test_long_references_start_with_contents(self):
        for path in references():
            lines = path.read_text(encoding="utf-8").splitlines()
            if len(lines) > 100:
                with self.subTest(reference=path.name):
                    first_section = next((l for l in lines if l.startswith("## ")), "")
                    self.assertEqual(first_section, "## Contents")


class ReferenceIndexTest(unittest.TestCase):
    def test_every_area_of_this_slice_has_a_reference(self):
        self.assertEqual({path.name for path in references()}, EXPECTED_REFERENCES)

    def test_skill_md_links_every_reference(self):
        text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        for name in sorted(EXPECTED_REFERENCES):
            with self.subTest(reference=name):
                self.assertIn(f"](references/{name})", text)


class ExamplesPackageTest(unittest.TestCase):
    def test_targets_typescript_7_0_and_node_24(self):
        self.assertEqual(minimum_versions(), ("7.0", "24"))

    def test_ignores_build_output_and_dependencies(self):
        ignored = (EXAMPLES / ".gitignore").read_text(encoding="utf-8").split()
        for entry in ("node_modules/", "dist/", "coverage/"):
            with self.subTest(entry=entry):
                self.assertIn(entry, ignored)


class QuotedBlocksParserTest(unittest.TestCase):
    LINK = "From [`a.ts`](../examples/src/a.ts):\n\n"

    def test_reads_source_from_the_line_before_the_fence(self):
        text = self.LINK + "```ts\nexport const a = 1;\n```\n"
        self.assertEqual(list(quoted_blocks(text)), [(3, "src/a.ts", "export const a = 1;\n")])

    def test_block_without_a_source_link(self):
        text = "Some prose.\n\n```ts\nexport const a = 1;\n```\n"
        self.assertEqual(list(quoted_blocks(text)), [(3, None, "export const a = 1;\n")])

    def test_reads_a_link_to_each_kind_of_source_file(self):
        for extension in ("ts", "tsx", "mts", "cts", "js", "mjs", "cjs"):
            with self.subTest(extension=extension):
                text = f"From [`a`](../examples/src/a.{extension}):\n\n```ts\nx;\n```\n"
                self.assertEqual(list(quoted_blocks(text)), [(3, f"src/a.{extension}", "x;\n")])

    def test_rejects_an_empty_block(self):
        self.assertEqual(excerpt_problem("\n", "export const a = 1;\n"), "block is empty")

    def test_accepts_whole_declarations(self):
        source = "// A is a.\nexport const a = 1;\n\nexport const b = 2;\n"
        self.assertIsNone(excerpt_problem("// A is a.\nexport const a = 1;\n", source))
        self.assertIsNone(excerpt_problem("export const b = 2;\n", source))

    def test_rejects_a_partial_declaration(self):
        source = "// A does a.\nexport function a(): void {\n  return;\n}\n"
        cut = "block starts or ends inside a declaration or comment"
        self.assertEqual(excerpt_problem("export function a(): void {\n", source), cut)
        self.assertEqual(excerpt_problem("  return;\n}\n", source), cut)
        self.assertEqual(excerpt_problem("turn;\n", source), cut)

    def test_rejects_text_not_in_the_source(self):
        self.assertEqual(
            excerpt_problem("export const c = 3;\n", "export const a = 1;\n"),
            "block is not a verbatim excerpt",
        )

    def test_counts_every_alias(self):
        for alias in sorted(LANGUAGES) + ["TS", "TypeScript", "JS"]:
            with self.subTest(alias=alias):
                text = f"{self.LINK}```{alias}\nx;\n```\n"
                self.assertEqual(list(quoted_blocks(text)), [(3, "src/a.ts", "x;\n")])

    def test_reads_every_kind_of_fence(self):
        for opener, closer in (("~~~ts", "~~~"), ("```ts title", "```"), ("````ts", "````"), ("``` ts", "```")):
            with self.subTest(fence=opener):
                text = f"{self.LINK}{opener}\nx;\n{closer}\n"
                self.assertEqual(list(quoted_blocks(text)), [(3, "src/a.ts", "x;\n")])

    def test_reads_an_indented_fence(self):
        text = "1. From [`a.ts`](../examples/src/a.ts):\n\n   ```ts\n   x;\n   ```\n"
        self.assertEqual(list(quoted_blocks(text)), [(3, "src/a.ts", "x;\n")])

    def test_reads_an_indented_fence_closed_at_column_zero(self):
        text = self.LINK + "  ```ts\n  x;\n```\n"
        self.assertEqual(list(quoted_blocks(text)), [(3, "src/a.ts", "x;\n")])

    def test_reads_a_fence_closed_by_a_longer_fence(self):
        text = self.LINK + "~~~ts\nx;\n~~~~\n"
        self.assertEqual(list(quoted_blocks(text)), [(3, "src/a.ts", "x;\n")])

    def test_a_shorter_or_different_fence_does_not_close(self):
        text = "````ts\nx;\n```\n~~~~\n````\n"
        self.assertEqual(list(quoted_blocks(text)), [(1, None, "x;\n```\n~~~~\n")])

    def test_a_closer_needs_only_whitespace_after_it(self):
        text = "```ts\nx;\n``` y\n```  \n"
        self.assertEqual(list(quoted_blocks(text)), [(1, None, "x;\n``` y\n")])

    def test_reports_a_block_with_no_closer(self):
        for alias in sorted(LANGUAGES):
            with self.subTest(alias=alias):
                self.assertEqual(parse_fences(f"```{alias}\nx;\n")[1], ["line 1: block has no closing fence"])

    def test_reports_a_fence_like_line_that_opens_nothing(self):
        for alias in sorted(LANGUAGES):
            with self.subTest(alias=alias):
                self.assertEqual(
                    parse_fences(f"    ```{alias}\nx;\n    ```\n")[1],
                    ["line 1: looks like a TypeScript or JavaScript fence but does not open one"],
                )

    def test_a_backtick_in_the_info_string_opens_nothing(self):
        self.assertEqual(
            parse_fences("```ts `x`\ny;\n```\n")[1],
            ["line 1: looks like a TypeScript or JavaScript fence but does not open one"],
        )

    def test_ignores_a_fence_inside_another_block(self):
        text = "````md\n```ts\nx;\n```\n````\n"
        self.assertEqual(parse_fences(text), ([], []))

    def test_ignores_other_languages(self):
        for info in ("sh", "json", "jsonc", "tsv", "go", ""):
            with self.subTest(info=info):
                text = f"```{info}\npnpm exec tsc --noEmit\n```\n"
                self.assertEqual(parse_fences(text), ([], []))


if __name__ == "__main__":
    unittest.main()
