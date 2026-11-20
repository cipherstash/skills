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

# The areas the skill must cover (cipherstash/skills#56). Each has one reference.
EXPECTED_REFERENCES = {
    "concurrency.md",
    "dependencies.md",
    "error-handling.md",
    "generics.md",
    "interfaces.md",
    "performance.md",
    "project-structure.md",
    "security.md",
    "testing.md",
}
# Build tags that guard files in the examples module. Each is vetted and tested
# too, so a file behind a tag cannot rot unseen.
BUILD_TAGS = ("integration",)

FENCE_RE = re.compile(r"(?ms)^```go\n(.*?)^```\s*$")
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
        yield line, source.group(1) if source else None, match.group(1)


class GoExamplesTest(unittest.TestCase):
    def setUp(self):
        self.go = shutil.which("go")
        if self.go is None:
            if os.environ.get("CI"):
                self.fail("go is not on PATH; CI must install the Go toolchain")
            self.skipTest("go is not on PATH; install Go to run the examples checks")

    def run_go(self, *args, env_extra=None):
        env = dict(os.environ, GOTOOLCHAIN="local", GOWORK="off", GOFLAGS="-mod=readonly")
        env.update(env_extra or {})
        return subprocess.run(
            [self.go, *args],
            cwd=EXAMPLES,
            env=env,
            capture_output=True,
            text=True,
            timeout=600,
        )

    def assertGoSucceeds(self, *args, env_extra=None):
        result = self.run_go(*args, env_extra=env_extra)
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

    def test_vet_and_test_with_build_tags(self):
        for tag in BUILD_TAGS:
            with self.subTest(tag=tag):
                self.assertGoSucceeds("vet", "-tags", tag, "./...")
                self.assertGoSucceeds("test", "-race", "-count=1", "-tags", tag, "./...")

    def test_vet_for_another_platform(self):
        # Files behind a platform build constraint, such as //go:build !unix,
        # compile only for that platform; vetting for Windows checks them.
        self.assertGoSucceeds("vet", "./...", env_extra={"GOOS": "windows", "GOARCH": "amd64"})

    def test_benchmarks_run(self):
        # go test runs no benchmarks by default; run each once so a quoted
        # benchmark cannot break unseen.
        self.assertGoSucceeds("test", "-run=^$", "-bench=.", "-benchtime=1x", "-count=1", "./...")

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
                    self.assertIn(
                        code,
                        target.read_text(encoding="utf-8"),
                        f"{where}: block is not a verbatim excerpt of examples/{source}",
                    )

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

    def test_ignores_other_languages(self):
        text = "```sh\ngo test ./...\n```\n"
        self.assertEqual(list(quoted_blocks(text)), [])


if __name__ == "__main__":
    unittest.main()
