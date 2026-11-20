# Tests for golang-review's seeded-defect fixture.
# Run: python3 -m unittest discover -s tests (from the skill directory).
#
# The fixture is a Go module before (base/) and after (head/) a sample change
# with a planted error-handling defect and a planted data race.
# expected-findings.md lists what a correct review must report. These tests keep
# the fixture honest: the base is clean, the defects come from the change,
# go vet passes on the head while go test -race catches the race, the head
# counts a bad record with no error while the base rejects it, and every
# location in expected-findings.md is exactly the line it quotes.
#
# The Go checks need the go command on PATH. Without it they are skipped locally
# with a message, and they fail when the CI environment variable is set, so a CI
# job that forgot to install Go cannot pass silently.
import filecmp
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
FIXTURE = SKILL / "tests" / "fixtures" / "seeded-change"
BASE = FIXTURE / "base"
HEAD = FIXTURE / "head"
EXPECTED = FIXTURE / "expected-findings.md"

# Added to a temporary copy of a fixture module by GoFixtureTest: it prints
# whether Summarise returned an error for G1's bad record, and how many lines
# it counted.
BAD_RECORD_PROBE = """package orders

import "testing"

func TestBadRecordProbe(t *testing.T) {
	got, err := Summarise([][]byte{[]byte(`{"sku":"B2","quantity":"one"}`)})
	result := "nil"
	if err != nil {
		result = "error"
	}
	t.Logf("PROBE err=%s lines=%d", result, got.Lines)
}
"""

# One expected finding: "## G1 · major · error handling" and, below it,
# "- Location: `head/<path>:<line>`" and "- Line: `<text quoted from that line>`".
FINDING_RE = re.compile(r"(?m)^## (G\d+) · (critical|major|minor) · (.+)$")
LOCATION_RE = re.compile(r"(?m)^- Location: `head/([^`:]+):(\d+)`")
LINE_RE = re.compile(r"(?m)^- Line: `(.+)`$")


def expected_findings():
    """Return [(id, severity, area, path, line, quoted text)] from expected-findings.md."""
    text = EXPECTED.read_text(encoding="utf-8")
    headings = list(FINDING_RE.finditer(text))
    findings = []
    for index, heading in enumerate(headings):
        end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
        body = text[heading.end() : end]
        location = LOCATION_RE.search(body)
        quoted = LINE_RE.search(body)
        findings.append(
            (
                heading.group(1),
                heading.group(2),
                heading.group(3).strip(),
                location.group(1) if location else None,
                int(location.group(2)) if location else None,
                quoted.group(1) if quoted else None,
            )
        )
    return findings


def changed_files():
    """Return the module-relative paths that differ between base/ and head/."""
    changed = []

    def walk(cmp, prefix=""):
        for name in cmp.left_only + cmp.right_only + cmp.diff_files:
            changed.append(prefix + name)
        for name, sub in cmp.subdirs.items():
            walk(sub, prefix + name + "/")

    walk(filecmp.dircmp(BASE, HEAD))
    return sorted(changed)


class ExpectedFindingsTest(unittest.TestCase):
    def test_lists_one_finding_per_planted_area(self):
        areas = sorted(area for _, _, area, *_ in expected_findings())
        self.assertEqual(areas, ["concurrency", "error handling"])

    def test_each_finding_quotes_the_line_it_names(self):
        findings = expected_findings()
        self.assertTrue(findings, "expected-findings.md lists no findings")
        for finding_id, _, _, path, line, quoted in findings:
            with self.subTest(finding=finding_id):
                self.assertIsNotNone(path, f"{finding_id}: no '- Location: `head/<path>:<line>`'")
                self.assertIsNotNone(quoted, f"{finding_id}: no '- Line: `<text>`'")
                lines = (HEAD / path).read_text(encoding="utf-8").splitlines()
                self.assertLessEqual(line, len(lines), f"{finding_id}: {path} has {len(lines)} lines")
                # The whole line, not a substring: a fix that keeps the call on the
                # same line (`errs[i] = json.Unmarshal(raw, &l)`) must fail here.
                self.assertEqual(
                    lines[line - 1].strip(), quoted, f"{finding_id}: {path}:{line} is {lines[line - 1]!r}"
                )

    def test_findings_point_at_changed_files(self):
        changed = changed_files()
        for finding_id, _, _, path, *_ in expected_findings():
            with self.subTest(finding=finding_id):
                self.assertIn(path, changed)

    def test_the_change_touches_only_the_package(self):
        self.assertEqual(changed_files(), ["orders/orders.go", "orders/orders_test.go"])


class GoFixtureTest(unittest.TestCase):
    def setUp(self):
        self.go = shutil.which("go")
        if self.go is None:
            if os.environ.get("CI"):
                self.fail("go is not on PATH; CI must install the Go toolchain")
            self.skipTest("go is not on PATH; install Go to run the fixture checks")

    def run_go(self, module, *args):
        # The skill's read-only settings (no toolchain download, no go.mod or
        # go.sum edits, no module download), plus GOWORK=off: the fixture
        # modules sit inside this repository, so a go.work above them must not
        # change how they build. The skill itself leaves GOWORK as the repository
        # has it.
        env = dict(os.environ, GOTOOLCHAIN="local", GOWORK="off", GOFLAGS="-mod=readonly", GOPROXY="off")
        return subprocess.run(
            [self.go, *args], cwd=module, env=env, capture_output=True, text=True, timeout=600
        )

    def assertGo(self, module, *args, ok=True):
        result = self.run_go(module, *args)
        output = result.stdout + result.stderr
        if ok:
            self.assertEqual(result.returncode, 0, f"go {' '.join(args)} in {module.name}/\n{output}")
        else:
            self.assertNotEqual(result.returncode, 0, f"go {' '.join(args)} in {module.name}/ passed\n{output}")
        return output

    def test_base_vets_and_passes_with_the_race_detector(self):
        self.assertGo(BASE, "vet", "./...")
        self.assertGo(BASE, "test", "-race", "-count=1", "./...")

    def test_head_vets_clean(self):
        # go vet does not see either planted defect; the review must still report them.
        self.assertGo(HEAD, "vet", "./...")

    def test_race_detector_reports_the_planted_race(self):
        output = self.assertGo(HEAD, "test", "-race", "-count=1", "./...", ok=False)
        self.assertIn("WARNING: DATA RACE", output)
        race = [f for f in expected_findings() if f[2] == "concurrency"]
        self.assertEqual(len(race), 1)
        _, _, _, path, line, _ = race[0]
        self.assertIn(f"{Path(path).name}:{line}", output, "the race report does not name the finding's line")

    def run_bad_record_probe(self, module):
        # Run a probe test against a temporary copy of the module: Summarise on a
        # record whose quantity is a string. The copy keeps the probe out of the
        # fixture.
        with tempfile.TemporaryDirectory() as tmp:
            copy = Path(tmp) / module.name
            shutil.copytree(module, copy)
            (copy / "orders" / "probe_test.go").write_text(BAD_RECORD_PROBE, encoding="utf-8")
            result = self.run_go(copy, "test", "-count=1", "-run", "^TestBadRecordProbe$", "-v", "./orders")
        output = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, f"probe in {module.name}/ did not run\n{output}")
        probe = re.search(r"PROBE err=(\w+) lines=(\d+)", output)
        self.assertIsNotNone(probe, output)
        return probe.group(1), int(probe.group(2))

    def test_base_rejects_a_bad_record(self):
        self.assertEqual(self.run_bad_record_probe(BASE), ("error", 0))

    def test_head_counts_a_bad_record_with_no_error(self):
        # G1's consequence, observed: the bad record becomes a line and the
        # error is nil. A change that fixes G1 fails this test, so the fixture
        # cannot drift away from its expected findings unnoticed.
        self.assertEqual(self.run_bad_record_probe(HEAD), ("nil", 1))

    def test_gofmt(self):
        gofmt = shutil.which("gofmt") or str(Path(self.go).with_name("gofmt"))
        result = subprocess.run([gofmt, "-l", "."], cwd=FIXTURE, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "", "files need gofmt:\n" + result.stdout)


if __name__ == "__main__":
    unittest.main()
