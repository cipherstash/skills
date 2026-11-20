# Tests for the golang-practices examples module and the references that quote it.
# Run: python3 -m unittest discover -s tests (from the skill directory).
#
# The Go checks need the go command on PATH. Without it they are skipped locally
# with a message, and they fail when the CI environment variable is set, so a CI
# job that forgot to install Go cannot pass silently.
import os
import re
import shutil
import subprocess
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
EXAMPLES = SKILL / "examples"
REFERENCES = SKILL / "references"

# A Go fence opener: up to three spaces of indent, three or more backticks or
# tildes, then go or golang in any case, optionally followed by more info. The
# closer uses the same indent and fence characters.
FENCE_RE = re.compile(
    r"(?ms)^(?P<indent> {0,3})(?P<fence>`{3,}|~{3,})[ \t]*(?i:go|golang)(?:[ \t][^\n]*)?\n"
    r"(?P<code>.*?)^(?P=indent)(?P=fence)[ \t]*$"
)
SOURCE_RE = re.compile(r"\]\(\.\./examples/([^)#]+\.go)\)")
GO_DIRECTIVE_RE = re.compile(r"(?m)^go (\d+\.\d+)(?:\.\d+)?\s*$")


def go_version():
    match = GO_DIRECTIVE_RE.search((EXAMPLES / "go.mod").read_text(encoding="utf-8"))
    if not match:
        raise AssertionError("examples/go.mod has no go directive")
    return match.group(1)


def quoted_blocks(text):
    """Yield (line number, source path or None, code) for each Go block in text."""
    for match in FENCE_RE.finditer(text):
        before = text[: match.start()].rstrip("\n").splitlines()
        lead = before[-1] if before else ""
        source = SOURCE_RE.search(lead)
        line = text.count("\n", 0, match.start()) + 1
        indent = match.group("indent")
        code = "".join(
            l[len(indent) :] if l.startswith(indent) else l
            for l in match.group("code").splitlines(keepends=True)
        )
        yield line, source.group(1) if source else None, code


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

    def test_vet(self):
        self.assertGoSucceeds("vet", "./...")

    def test_race(self):
        self.assertGoSucceeds("test", "-race", "-count=1", "./...")

    def test_gofmt(self):
        gofmt = shutil.which("gofmt") or str(Path(self.go).with_name("gofmt"))
        result = subprocess.run([gofmt, "-l", "."], cwd=EXAMPLES, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "", "files need gofmt:\n" + result.stdout)


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

    def test_ignores_other_languages(self):
        text = "```sh\ngo test ./...\n```\n"
        self.assertEqual(list(quoted_blocks(text)), [])


if __name__ == "__main__":
    unittest.main()
