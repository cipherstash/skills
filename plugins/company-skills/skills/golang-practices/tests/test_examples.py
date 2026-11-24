# Tests for the golang-practices examples module and the references that quote it.
# Run: python3 -m unittest discover -s tests (from the skill directory).
#
# The Go check suite (references/checks.md) runs over the examples module in CI,
# in the validate workflow's go-check-suite job. These tests check only that
# every quoted block matches its source, and that every benchmark runs.
#
# The benchmark run needs the go command on PATH. Without it, it is skipped
# locally with a message, and it fails when the CI environment variable is set,
# so a CI job that forgot to install Go cannot pass silently.
import os
import re
import shutil
import subprocess
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
EXAMPLES = SKILL / "examples"
REFERENCES = SKILL / "references"

# The areas the skill must cover (cipherstash/skills#56), wazero, and the Go check
# suite (cipherstash/skills#87). Each has one reference.
EXPECTED_REFERENCES = {
    "checks.md",
    "concurrency.md",
    "dependencies.md",
    "error-handling.md",
    "generics.md",
    "interfaces.md",
    "performance.md",
    "project-structure.md",
    "security.md",
    "testing.md",
    "wazero.md",
}

# Fenced code blocks follow CommonMark: an opener is up to three spaces of
# indent, then three or more backticks or tildes, then an info string whose
# first word is the language. A backtick opener's info string has no backtick.
OPENER_RE = re.compile(r"^(?P<indent> {0,3})(?P<fence>`{3,}|~{3,})(?P<info>.*)$")
# Any line that looks like it opens a Go block, at any indent. Every such line
# outside another block must be a real opener, so no Go block is skipped.
GO_LIKE_RE = re.compile(r"^\s*(?:`{3,}|~{3,})\s*(?:go|golang)(?:\s|$)", re.IGNORECASE)
GO_LANGUAGES = {"go", "golang"}
SOURCE_RE = re.compile(r"\]\(\.\./examples/([^)#]+\.go)\)")
GO_DIRECTIVE_RE = re.compile(r"(?m)^go (\d+\.\d+)(?:\.\d+)?\s*$")


def go_version():
    match = GO_DIRECTIVE_RE.search((EXAMPLES / "go.mod").read_text(encoding="utf-8"))
    if not match:
        raise AssertionError("examples/go.mod has no go directive")
    return match.group(1)


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


def parse_fences(text):
    """Return (blocks, problems) for the Go blocks in text.

    blocks is a list of (line number, source path or None, code). Each code
    line has up to the opener's indent removed. problems lists, by line, each
    Go-like line that is not a valid opener and each Go block with no closer.
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
            if GO_LIKE_RE.match(line):
                problems.append(f"line {i + 1}: looks like a Go fence but does not open one")
            i += 1
            continue
        fence, indent = opener["fence"], len(opener["indent"])
        words = opener["info"].split()
        is_go = bool(words) and words[0].lower() in GO_LANGUAGES
        body, j = [], i + 1
        while j < len(lines) and not closes(lines[j].rstrip("\n"), fence):
            content = lines[j]
            body.append(content[min(indent, len(content) - len(content.lstrip(" "))) :])
            j += 1
        if is_go:
            if j == len(lines):
                problems.append(f"line {i + 1}: Go block has no closing fence")
            else:
                lead = next((l for l in reversed(lines[:i]) if l.strip()), "")
                source = SOURCE_RE.search(lead)
                blocks.append((i + 1, source.group(1) if source else None, "".join(body)))
        i = j + 1
    return blocks, problems


def quoted_blocks(text):
    """Yield (line number, source path or None, code) for each Go block in text."""
    yield from parse_fences(text)[0]


def excerpt_problem(code, source_text):
    """Return why code is not a whole-declaration excerpt of source_text, or None.

    A quoted block must be non-empty and must match a run of whole lines in the
    source that starts after a blank line (or the start of the file) and ends
    before a blank line (or the end of the file), so it cannot begin or end in
    the middle of a declaration or its doc comment.
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
    return "block starts or ends inside a declaration or doc comment"


class GoExamplesTest(unittest.TestCase):
    def setUp(self):
        self.go = shutil.which("go")
        if self.go is None:
            if os.environ.get("CI"):
                self.fail("go is not on PATH; CI must install the Go toolchain")
            self.skipTest("go is not on PATH; install Go to run the examples checks")

    def run_go(self, *args):
        env = dict(os.environ, GOTOOLCHAIN="local", GOWORK="off", GOFLAGS="-mod=readonly")
        return subprocess.run(
            [self.go, *args],
            cwd=EXAMPLES,
            env=env,
            capture_output=True,
            text=True,
            timeout=600,
        )

    def assertGoSucceeds(self, *args):
        result = self.run_go(*args)
        self.assertEqual(
            result.returncode,
            0,
            f"go {' '.join(args)} exited {result.returncode}\n{result.stdout}\n{result.stderr}",
        )
        return result

    def test_benchmarks_run(self):
        # go test runs no benchmarks by default; run each once so a quoted
        # benchmark cannot break unseen.
        self.assertGoSucceeds("test", "-run=^$", "-bench=.", "-benchtime=1x", "-count=1", "./...")


class QuotedSnippetsTest(unittest.TestCase):
    def references(self):
        paths = sorted(REFERENCES.glob("*.md"))
        self.assertTrue(paths, "no references found")
        return paths

    def test_every_go_block_is_quoted_from_the_module(self):
        for path in self.references():
            text = path.read_text(encoding="utf-8")
            for line, source, code in quoted_blocks(text):
                where = f"{path.name}:{line}"
                with self.subTest(block=where):
                    self.assertIsNotNone(
                        source,
                        f"{where}: put a link to ../examples/<file>.go on the line before the block",
                    )
                    target = (EXAMPLES / source).resolve()
                    self.assertTrue(target.is_relative_to(EXAMPLES.resolve()), where)
                    self.assertTrue(target.is_file(), f"{where}: {source} does not exist")
                    problem = excerpt_problem(code, target.read_text(encoding="utf-8"))
                    self.assertIsNone(problem, f"{where}: {problem} (examples/{source})")

    def test_no_go_block_is_skipped(self):
        for path in self.references():
            with self.subTest(reference=path.name):
                self.assertEqual(parse_fences(path.read_text(encoding="utf-8"))[1], [])

    def test_each_reference_states_the_go_version(self):
        version = go_version()
        for path in self.references():
            with self.subTest(reference=path.name):
                self.assertIn(f"Go {version}", path.read_text(encoding="utf-8"))

    def test_long_references_start_with_contents(self):
        for path in self.references():
            lines = path.read_text(encoding="utf-8").splitlines()
            if len(lines) > 100:
                with self.subTest(reference=path.name):
                    first_section = next((l for l in lines if l.startswith("## ")), "")
                    self.assertEqual(first_section, "## Contents")


class SuiteToolVersionTest(unittest.TestCase):
    # checks.md pins each suite tool's version, so no other file may fetch one
    # at @latest (cipherstash/skills#89).
    SUITE_TOOL_AT_LATEST_RE = re.compile(
        r"\S*(?:golangci-lint|gosec|staticcheck|govulncheck|gofumpt|semgrep)\S*@latest"
    )

    def test_no_suite_tool_is_fetched_at_latest(self):
        for path in [SKILL / "SKILL.md", *sorted(REFERENCES.glob("*.md"))]:
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                with self.subTest(line=f"{path.name}:{number}"):
                    self.assertIsNone(
                        self.SUITE_TOOL_AT_LATEST_RE.search(line),
                        "link to references/checks.md for the pinned version instead",
                    )


class ReferenceIndexTest(unittest.TestCase):
    def test_every_area_has_a_reference(self):
        found = {path.name for path in REFERENCES.glob("*.md")}
        self.assertEqual(found, EXPECTED_REFERENCES)

    def test_skill_md_links_every_reference(self):
        text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        for name in sorted(EXPECTED_REFERENCES):
            with self.subTest(reference=name):
                self.assertIn(f"](references/{name})", text)


class QuotedBlocksParserTest(unittest.TestCase):
    def test_reads_source_from_the_line_before_the_fence(self):
        text = "From [`a.go`](../examples/pkg/a.go):\n\n```go\nfunc A() {}\n```\n"
        self.assertEqual(list(quoted_blocks(text)), [(3, "pkg/a.go", "func A() {}\n")])

    def test_block_without_a_source_link(self):
        text = "Some prose.\n\n```go\nfunc A() {}\n```\n"
        self.assertEqual(list(quoted_blocks(text)), [(3, None, "func A() {}\n")])

    def test_rejects_an_empty_block(self):
        self.assertEqual(excerpt_problem("\n", "func A() {}\n"), "block is empty")

    def test_accepts_whole_declarations(self):
        source = "package p\n\n// A does a.\nfunc A() {}\n\nfunc B() {}\n"
        self.assertIsNone(excerpt_problem("// A does a.\nfunc A() {}\n", source))
        self.assertIsNone(excerpt_problem("func B() {}\n", source))

    def test_rejects_a_partial_declaration(self):
        source = "// A does a.\nfunc A() {\n\treturn\n}\n"
        cut = "block starts or ends inside a declaration or doc comment"
        self.assertEqual(excerpt_problem("func A() {\n", source), cut)
        self.assertEqual(excerpt_problem("\treturn\n}\n", source), cut)
        self.assertEqual(excerpt_problem("turn\n", source), cut)

    def test_rejects_text_not_in_the_source(self):
        self.assertEqual(
            excerpt_problem("func C() {}\n", "func A() {}\n"),
            "block is not a verbatim excerpt",
        )

    def test_reads_every_kind_of_go_fence(self):
        link = "From [`a.go`](../examples/pkg/a.go):\n\n"
        for fence in ("```go", "```golang", "```Go", "~~~go", "```go title", "````go"):
            close = fence.split("go")[0].split("Go")[0].rstrip(" ")
            with self.subTest(fence=fence):
                text = f"{link}{fence}\nfunc A() {{}}\n{close}\n"
                self.assertEqual(list(quoted_blocks(text)), [(3, "pkg/a.go", "func A() {}\n")])

    def test_reads_an_indented_fence(self):
        text = "1. From [`a.go`](../examples/pkg/a.go):\n\n   ```go\n   func A() {}\n   ```\n"
        self.assertEqual(list(quoted_blocks(text)), [(3, "pkg/a.go", "func A() {}\n")])

    def test_reads_an_indented_fence_closed_at_column_zero(self):
        text = "From [`a.go`](../examples/pkg/a.go):\n\n  ```go\n  func A() {}\n```\n"
        self.assertEqual(list(quoted_blocks(text)), [(3, "pkg/a.go", "func A() {}\n")])

    def test_reads_a_fence_closed_by_a_longer_fence(self):
        text = "From [`a.go`](../examples/pkg/a.go):\n\n~~~go\nfunc A() {}\n~~~~\n"
        self.assertEqual(list(quoted_blocks(text)), [(3, "pkg/a.go", "func A() {}\n")])

    def test_a_shorter_or_different_fence_does_not_close(self):
        text = "````go\nfunc A() {}\n```\n~~~~\n````\n"
        self.assertEqual(list(quoted_blocks(text)), [(1, None, "func A() {}\n```\n~~~~\n")])

    def test_a_closer_needs_only_whitespace_after_it(self):
        text = "```go\nfunc A() {}\n``` x\n```  \n"
        self.assertEqual(list(quoted_blocks(text)), [(1, None, "func A() {}\n``` x\n")])

    def test_reports_a_go_block_with_no_closer(self):
        self.assertEqual(
            parse_fences("```go\nfunc A() {}\n")[1], ["line 1: Go block has no closing fence"]
        )

    def test_reports_a_go_like_line_that_opens_nothing(self):
        self.assertEqual(
            parse_fences("    ```go\nfunc A() {}\n    ```\n")[1],
            ["line 1: looks like a Go fence but does not open one"],
        )

    def test_ignores_a_go_fence_inside_another_block(self):
        text = "````md\n```go\nfunc A() {}\n```\n````\n"
        self.assertEqual(parse_fences(text), ([], []))

    def test_ignores_other_languages(self):
        text = "```sh\ngo test ./...\n```\n"
        self.assertEqual(list(quoted_blocks(text)), [])


if __name__ == "__main__":
    unittest.main()
