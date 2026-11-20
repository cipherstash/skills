# Tests for golang-review's seeded-defect fixture and its areas table.
# Run: python3 -m unittest discover -s tests (from the skill directory).
#
# The fixture is a Go module before (base/) and after (head/) a sample change
# with one planted defect in each of the ten checklist areas.
# expected-findings.md lists what a correct review must report. These tests keep
# the fixture honest: every location in expected-findings.md is exactly the line
# it quotes, the base is clean, each planted defect comes from the change, and,
# where a tool or a short probe can show one, it does: the race detector, a
# panic on empty input, coverage, gofmt, go mod tidy -diff, missing doc
# comments, allocations, and the exported API removed between base and head.
# A fix to any planted defect makes a test here fail, so the fixture cannot
# drift away from its expected findings unnoticed.
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
PRACTICES = SKILL.parent / "golang-practices"
FIXTURE = SKILL / "tests" / "fixtures" / "seeded-change"
BASE = FIXTURE / "base"
HEAD = FIXTURE / "head"
EXPECTED = FIXTURE / "expected-findings.md"

# The ten checklist areas, in priority order, as SKILL.md's areas table names them.
AREAS = [
    "Error handling",
    "Correctness and edge cases",
    "Testing and coverage",
    "Concurrency safety",
    "Naming and style",
    "Security",
    "Performance",
    "Dependency management",
    "Documentation",
    "Breaking changes",
]

# One expected finding: "## G1 · major · error handling" and, below it,
# "- Location: `head/<path>:<line>`" (or `base/<path>:<line>` (deleted) for a
# line the change removed) and "- Line: `<text quoted from that line>`".
FINDING_RE = re.compile(r"(?m)^## (G\d+) · (critical|major|minor) · (.+)$")
LOCATION_RE = re.compile(r"(?m)^- Location: `(head|base)/([^`:]+):(\d+)`( \(deleted\))?")
LINE_RE = re.compile(r"(?m)^- Line: `(.+)`$")
GO_VERSION_RE = re.compile(r"go1\.(\d+)")

# The read-only settings from the table in checks.md, which every go command
# here runs with. SettingsTableTest keeps the two the same.
READ_ONLY_ENV = {"GOFLAGS": "-mod=readonly", "GOTOOLCHAIN": "local", "GOPROXY": "off", "GOSUMDB": "off"}


def expected_findings():
    """Return {area: dict(id, severity, side, path, line, deleted, quoted)} from expected-findings.md."""
    text = EXPECTED.read_text(encoding="utf-8")
    headings = list(FINDING_RE.finditer(text))
    findings = {}
    for index, heading in enumerate(headings):
        end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
        body = text[heading.end() : end]
        location = LOCATION_RE.search(body)
        quoted = LINE_RE.search(body)
        area = heading.group(3).strip()
        if area in findings:
            raise AssertionError(f"expected-findings.md lists {area} twice")
        findings[area] = {
            "id": heading.group(1),
            "severity": heading.group(2),
            "side": location.group(1) if location else None,
            "path": location.group(2) if location else None,
            "line": int(location.group(3)) if location else None,
            "deleted": bool(location and location.group(4)),
            "quoted": quoted.group(1) if quoted else None,
        }
    return findings


def finding(area):
    return expected_findings()[area.lower()]


# The exported API as checks.md compares it: every declaration go doc -all
# prints, including each name inside a grouped `const (` or `var (` block and
# each struct field and interface method, with runs of spaces collapsed (gofmt
# realigns a group when a longer name joins it) and parameter, result, and
# receiver names dropped, since renaming one changes no importer.

def _close(text, start):
    """Return the index of the bracket that closes the one at text[start]."""
    depth = 0
    for index in range(start, len(text)):
        if text[index] in "([{":
            depth += 1
        elif text[index] in ")]}":
            depth -= 1
            if depth == 0:
                return index
    raise ValueError(f"unbalanced brackets in {text!r}")


def _split_top(text):
    """Split text on the commas that are not inside brackets."""
    parts, depth, last = [], 0, 0
    for index, char in enumerate(text):
        if char in "([{":
            depth += 1
        elif char in ")]}":
            depth -= 1
        elif char == "," and depth == 0:
            parts.append(text[last:index])
            last = index + 1
    parts.append(text[last:])
    return [part.strip() for part in parts if part.strip()]


def _param_types(params):
    """Return the types of a parameter list, without its names."""
    parts = _split_top(params)
    named = [re.match(r"([A-Za-z_]\w*) (\S.*)$", part) for part in parts]
    if not any(m and m.group(1) not in ("chan", "func", "interface", "map", "struct") for m in named):
        return [_strip_func_types(part) for part in parts]
    types, waiting = [], 0
    for m in named:
        if m is None:
            waiting += 1  # `a` in `a, b int` takes the type that follows
        else:
            types += [_strip_func_types(m.group(2))] * (waiting + 1)
            waiting = 0
    return types


def _params(text, start):
    """Rewrite the parameter list at text[start] and any parenthesised results."""
    end = _close(text, start)
    out = "(" + ", ".join(_param_types(text[start + 1 : end])) + ")"
    if text.startswith(" (", end + 1):
        results_end = _close(text, end + 2)
        results = _param_types(text[end + 3 : results_end])
        out += " " + (results[0] if len(results) == 1 else "(" + ", ".join(results) + ")")
        end = results_end
    return out, end + 1


def _strip_func_types(text):
    """Drop the parameter names from every func type in text."""
    out, index = [], 0
    for m in re.finditer(r"\bfunc\(", text):
        if m.start() < index:
            continue
        rewritten, index_after = _params(text, m.end() - 1)
        out += [text[index : m.end() - 1], rewritten]
        index = index_after
    return "".join(out) + text[index:]


def _signature(line):
    """Drop the receiver, parameter, and result names from a func or method line."""
    head, index = "", 0
    if line.startswith("func ("):
        end = _close(line, 5)
        head, index = "func (" + ", ".join(_param_types(line[6:end])) + ")", end + 1
    name = re.compile(r"[^(\[]*").match(line, index).end()
    if name < len(line) and line[name] == "[":
        name = _close(line, name) + 1
    head += line[index:name]
    if name < len(line) and line[name] == "(":
        rewritten, index = _params(line, name)
        return head + rewritten + _strip_func_types(line[index:])
    return head + _strip_func_types(line[name:])


def api_declarations(doc):
    """Return the exported declarations in `go doc -all` output, normalised."""
    declarations, block = set(), None
    for raw in doc.splitlines():
        line = " ".join(raw.split())
        if block:
            if raw in (")", "}"):
                block = None
            elif raw.startswith("\t") and not line.startswith("//"):
                kind, owner = block
                member = _signature(line) if kind == "interface" else _strip_func_types(line)
                declarations.add(f"{owner} {member}")
            continue
        group = re.match(r"(const|var) \($", raw)
        compound = re.match(r"type (\w+)\S* (struct|interface) \{$", raw)
        if group:
            block = (group.group(1), group.group(1))
        elif compound:
            declarations.add(line.removesuffix(" {"))
            block = (compound.group(2), compound.group(1))
        elif raw.startswith("func "):
            declarations.add(_signature(line))
        elif re.match(r"(type|const|var) ", raw):
            declarations.add(_strip_func_types(line))
    return declarations


def changed_files():
    """Return the module-relative paths of files that differ between base/ and head/."""
    changed = []

    def files_under(path, prefix):
        if path.is_dir():
            for child in sorted(path.iterdir()):
                files_under(child, prefix + child.name + ("/" if child.is_dir() else ""))
        else:
            changed.append(prefix)

    def walk(cmp, left, right, prefix=""):
        for name in cmp.left_only:
            files_under(left / name, prefix + name + ("/" if (left / name).is_dir() else ""))
        for name in cmp.right_only:
            files_under(right / name, prefix + name + ("/" if (right / name).is_dir() else ""))
        changed.extend(prefix + name for name in cmp.diff_files)
        for name, sub in cmp.subdirs.items():
            walk(sub, left / name, right / name, prefix + name + "/")

    walk(filecmp.dircmp(BASE, HEAD), BASE, HEAD)
    return sorted(changed)


def areas_table():
    """Return SKILL.md's areas table rows as lists of cell text."""
    text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    section = text.split("\n## Areas\n", 1)[1].split("\n## ", 1)[0]
    rows = [line for line in section.splitlines() if re.match(r"^\| \d+ \|", line)]
    return [[cell.strip() for cell in row.strip("|").split("|")] for row in rows]


class AreasTableTest(unittest.TestCase):
    def test_lists_the_ten_areas_in_priority_order(self):
        self.assertEqual([row[1] for row in areas_table()], AREAS)
        self.assertEqual([row[0] for row in areas_table()], [str(n) for n in range(1, 11)])

    def test_every_area_has_a_step_reference_and_a_practices_reference(self):
        for order, area, _, step, practices in areas_table():
            with self.subTest(area=area):
                link = re.search(r"\]\((references/step-[a-z-]+\.md)\)", step)
                self.assertIsNotNone(link, f"{area}: no step reference in {step!r}")
                step_file = SKILL / link.group(1)
                self.assertTrue(step_file.is_file(), f"{area}: {link.group(1)} does not exist")
                names = re.findall(r"`(references/[a-z-]+\.md)`", practices)
                self.assertTrue(names, f"{area}: no golang-practices reference named")
                body = step_file.read_text(encoding="utf-8")
                self.assertIn(f"Area {order},", body, f"{link.group(1)} does not state its area number")
                for name in names:
                    self.assertTrue((PRACTICES / name).is_file(), f"{area}: golang-practices has no {name}")
                    self.assertIn(f"`{name}`", body, f"{link.group(1)} does not name {name}")


class SettingsTableTest(unittest.TestCase):
    def settings(self):
        text = (SKILL / "references" / "checks.md").read_text(encoding="utf-8")
        section = text.split("\n## Settings for every go command\n", 1)[1].split("\n## ", 1)[0]
        return dict(re.findall(r"(?m)^\| `([A-Z]+)=([^`]+)` \|", section))

    def test_tests_run_go_with_the_skill_settings(self):
        self.assertEqual(self.settings(), READ_ONLY_ENV)

    def test_checksum_database_is_off(self):
        # With GOPROXY=off, go mod tidy -diff still asks sum.golang.org for a
        # cached module that go.sum has no hash for.
        self.assertEqual(self.settings().get("GOSUMDB"), "off")


class ExpectedFindingsTest(unittest.TestCase):
    def test_lists_one_finding_per_area(self):
        self.assertEqual(sorted(expected_findings()), sorted(area.lower() for area in AREAS))

    def test_each_finding_quotes_the_line_it_names(self):
        for area, f in expected_findings().items():
            with self.subTest(area=area):
                self.assertIsNotNone(f["path"], f"{f['id']}: no '- Location: `head/<path>:<line>`'")
                self.assertIsNotNone(f["quoted"], f"{f['id']}: no '- Line: `<text>`'")
                self.assertEqual(f["side"] == "base", f["deleted"], f"{f['id']}: only a deleted line sits in base/")
                root = BASE if f["side"] == "base" else HEAD
                lines = (root / f["path"]).read_text(encoding="utf-8").splitlines()
                self.assertLessEqual(f["line"], len(lines), f"{f['id']}: {f['path']} has {len(lines)} lines")
                # The whole line, not a substring: a fix that keeps the call on the
                # same line (`errs[i] = json.Unmarshal(raw, &l)`) must fail here.
                self.assertEqual(
                    lines[f["line"] - 1].strip(),
                    f["quoted"],
                    f"{f['id']}: {f['path']}:{f['line']} is {lines[f['line'] - 1]!r}",
                )
                if f["deleted"]:
                    head_file = HEAD / f["path"]
                    head_lines = head_file.read_text(encoding="utf-8").splitlines() if head_file.exists() else []
                    self.assertNotIn(f["quoted"], [line.strip() for line in head_lines])

    def test_findings_point_at_changed_files(self):
        changed = changed_files()
        for area, f in expected_findings().items():
            with self.subTest(area=area):
                self.assertIn(f["path"], changed)

    def test_the_change_touches_only_the_planted_files(self):
        self.assertEqual(
            changed_files(),
            [
                "go.mod",
                "orders/orders.go",
                "orders/orders_test.go",
                "orders/query.go",
                "orders/report.go",
                "orders/report_test.go",
                "orders/units.go",
                "pricing/go.mod",
            ],
        )

    def test_one_exported_identifier_is_undocumented(self):
        # Documentation: the planted identifier is the only exported declaration
        # in the head's non-test files whose line above is not a comment.
        f = finding("Documentation")
        exported = re.compile(r"^(?:func (?:\([^)]*\) )?|type |const |var )([A-Z]\w*)")
        undocumented = []
        for path in sorted(HEAD.rglob("*.go")):
            if path.name.endswith("_test.go"):
                continue
            lines = path.read_text(encoding="utf-8").splitlines()
            for number, line in enumerate(lines, 1):
                if exported.match(line) and not (number > 1 and lines[number - 2].startswith("//")):
                    undocumented.append((path.relative_to(HEAD).as_posix(), number))
        self.assertEqual(undocumented, [(f["path"], f["line"])])

    def test_the_insecure_query_concatenates_its_argument(self):
        self.assertIn('+ sku +', finding("Security")["quoted"])


class GoFixtureTest(unittest.TestCase):
    def setUp(self):
        self.go = shutil.which("go")
        if self.go is None:
            if os.environ.get("CI"):
                self.fail("go is not on PATH; CI must install the Go toolchain")
            self.skipTest("go is not on PATH; install Go to run the fixture checks")

    def run_go(self, module, *args, cwd=None):
        # The skill's read-only settings (no toolchain download, no go.mod or
        # go.sum edits, no module download, no checksum database), plus
        # GOWORK=off: the fixture modules sit inside this repository, so a
        # go.work above them must not change how they build. The skill itself
        # leaves GOWORK as the repository has it.
        env = dict(os.environ, **READ_ONLY_ENV, GOWORK="off")
        return subprocess.run(
            [self.go, *args], cwd=cwd or module, env=env, capture_output=True, text=True, timeout=600
        )

    def assertGo(self, module, *args, ok=True):
        result = self.run_go(module, *args)
        output = result.stdout + result.stderr
        if ok:
            self.assertEqual(result.returncode, 0, f"go {' '.join(args)} in {module.name}/\n{output}")
        else:
            self.assertNotEqual(result.returncode, 0, f"go {' '.join(args)} in {module.name}/ passed\n{output}")
        return output

    def run_probe(self, module, source, name):
        # Run one probe test against a temporary copy of the module, so the
        # probe never lands in the fixture. Return the text after "PROBE ".
        with tempfile.TemporaryDirectory() as tmp:
            copy = Path(tmp) / module.name
            shutil.copytree(module, copy)
            (copy / "orders" / "probe_test.go").write_text(source, encoding="utf-8")
            result = self.run_go(copy, "test", "-count=1", "-run", f"^{name}$", "-v", "./orders")
        output = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, f"probe {name} in {module.name}/ did not run\n{output}")
        probe = re.search(r"PROBE (.*)", output)
        self.assertIsNotNone(probe, output)
        return probe.group(1).strip()

    def go_minor(self):
        version = self.run_go(HEAD, "env", "GOVERSION").stdout
        match = GO_VERSION_RE.search(version)
        self.assertIsNotNone(match, version)
        return int(match.group(1))

    # Error handling and concurrency safety.

    def test_base_vets_and_passes_with_the_race_detector(self):
        self.assertGo(BASE, "vet", "./...")
        self.assertGo(BASE, "test", "-race", "-count=1", "./...")

    def test_head_vets_clean(self):
        # go vet sees none of the planted defects; the review must still report them.
        self.assertGo(HEAD, "vet", "./...")

    def test_race_detector_reports_the_planted_race(self):
        output = self.assertGo(HEAD, "test", "-race", "-count=1", "./...", ok=False)
        self.assertIn("WARNING: DATA RACE", output)
        f = finding("Concurrency safety")
        self.assertIn(f"{Path(f['path']).name}:{f['line']}", output, "the race report does not name the finding's line")

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

    def test_base_rejects_a_bad_record(self):
        self.assertEqual(self.run_probe(BASE, self.BAD_RECORD_PROBE, "TestBadRecordProbe"), "err=error lines=0")

    def test_head_counts_a_bad_record_with_no_error(self):
        # Error handling's consequence, observed: the bad record becomes a line
        # and the error is nil.
        self.assertEqual(self.run_probe(HEAD, self.BAD_RECORD_PROBE, "TestBadRecordProbe"), "err=nil lines=1")

    # Correctness and edge cases.

    EMPTY_AVERAGE_PROBE = """package orders

import (
	"fmt"
	"testing"
)

func TestEmptyAverageProbe(t *testing.T) {
	defer func() { t.Logf("PROBE recovered=%v", fmt.Sprint(recover())) }()
	t.Logf("PROBE average=%d", Summary{}.AverageCents())
}
"""

    def test_average_of_an_empty_summary_panics(self):
        f = finding("Correctness and edge cases")
        self.assertIn("AverageCents", (HEAD / f["path"]).read_text(encoding="utf-8").splitlines()[f["line"] - 2])
        self.assertEqual(
            self.run_probe(HEAD, self.EMPTY_AVERAGE_PROBE, "TestEmptyAverageProbe"),
            "recovered=runtime error: integer divide by zero",
        )

    # Testing and coverage.

    def test_coverage_shows_one_untested_function(self):
        f = finding("Testing and coverage")
        with tempfile.TemporaryDirectory() as tmp:
            profile = Path(tmp) / "cover.out"
            # The race fails the run, but the profile is still written.
            self.run_go(HEAD, "test", "-race", "-count=1", f"-coverprofile={profile}", "./...")
            report = self.assertGo(HEAD, "tool", "cover", f"-func={profile}")
        functions = [line.split() for line in report.splitlines() if not line.startswith("total:")]
        untested = [entry[0] for entry in functions if entry[-1] == "0.0%"]
        self.assertEqual(untested, [f"example.com/seededchange/{f['path']}:{f['line']}:"], report)

    # Naming and style.

    def test_gofmt_lists_only_the_planted_file(self):
        gofmt = shutil.which("gofmt") or str(Path(self.go).with_name("gofmt"))
        f = finding("Naming and style")
        listed = subprocess.run([gofmt, "-l", "."], cwd=FIXTURE, capture_output=True, text=True)
        self.assertEqual(listed.returncode, 0, listed.stderr)
        self.assertEqual(listed.stdout.split(), [f"head/{f['path']}"])
        diff = subprocess.run([gofmt, "-d", f"head/{f['path']}"], cwd=FIXTURE, capture_output=True, text=True)
        self.assertIn("-" + f["quoted"], diff.stdout)
        self.assertIn("(this ", f["quoted"])

    # Security.

    INJECTION_PROBE = """package orders

import "testing"

func TestInjectionProbe(t *testing.T) {
	t.Logf("PROBE %s", LinesQuery(`x' OR '1'='1`))
}
"""

    def test_query_carries_injected_sql(self):
        self.assertTrue(
            self.run_probe(HEAD, self.INJECTION_PROBE, "TestInjectionProbe").endswith("WHERE sku = 'x' OR '1'='1'")
        )

    # Performance.

    ALLOCS_PROBE = """package orders

import "testing"

func TestAllocsProbe(t *testing.T) {
	lines := make([]Line, 100)
	t.Logf("PROBE allocs=%.0f", testing.AllocsPerRun(10, func() { SKUs(lines) }))
}
"""

    def test_skus_grows_its_slice_repeatedly(self):
        # With make([]string, 0, len(lines)) it would allocate once.
        allocs = self.run_probe(HEAD, self.ALLOCS_PROBE, "TestAllocsProbe")
        self.assertGreater(int(allocs.removeprefix("allocs=")), 1)

    # Dependency management.

    def test_go_mod_tidy_diff_removes_the_planted_requirement(self):
        if self.go_minor() < 23:
            self.skipTest("go mod tidy -diff needs Go 1.23")
        f = finding("Dependency management")
        self.assertGo(BASE, "mod", "tidy", "-diff")
        diff = self.assertGo(HEAD, "mod", "tidy", "-diff", ok=False)
        self.assertIn("-" + f["quoted"], diff)

    # Breaking changes.

    def exported_api(self, module, package="./orders"):
        return api_declarations(self.assertGo(module, "doc", "-all", package))

    API_GROUPS = """// Package api is a probe.
package api

import "errors"

// Kind is a kind.
type Kind int

// Kinds.
const (
	KindA Kind = iota
{kind})

// Errors.
var (
	ErrA = errors.New("a")
{err})

// Pair is a pair.
type Pair struct {{
	A int
{field}}}
"""

    API_NAMES = """// Package api is a probe.
package api

// T is a type.
type T struct{{}}

// M is a method.
func ({recv} T) M({a} int) ({n} int, {err} error) {{ return 0, nil }}

// F is a function.
func F({x}, {y} int, f func({v} int) bool) error {{ return nil }}

// Doer does.
type Doer interface {{
	Do({c} int) error
}}
"""

    def api_change(self, base_source, head_source):
        """Return (removed, added) exported declarations between two versions of a package."""
        apis = []
        with tempfile.TemporaryDirectory() as tmp:
            for name, source in (("base", base_source), ("head", head_source)):
                module = Path(tmp) / name
                (module / "api").mkdir(parents=True)
                (module / "go.mod").write_text("module example.com/api\n\ngo 1.22\n", encoding="utf-8")
                (module / "api" / "api.go").write_text(source, encoding="utf-8")
                apis.append(self.exported_api(module, "./api"))
        return apis[0] - apis[1], apis[1] - apis[0]

    def test_api_comparison_sees_names_removed_from_groups(self):
        base = self.API_GROUPS.format(kind="\tKindB\n", err='\tErrB = errors.New("b")\n', field="\tLonger string\n")
        head = self.API_GROUPS.format(kind="", err="", field="")
        removed, added = self.api_change(base, head)
        self.assertEqual(added, set())
        self.assertEqual(len(removed), 3, removed)
        for name in ("KindB", "ErrB", "Longer"):
            self.assertTrue(any(name in declaration for declaration in removed), f"{name} not in {removed}")

    def test_api_comparison_ignores_renamed_parameters_and_receivers(self):
        base = self.API_NAMES.format(recv="this", a="a", n="n", err="err", x="x", y="y", v="v", c="ctx")
        head = self.API_NAMES.format(recv="t", a="b", n="m", err="e", x="p", y="q", v="w", c="c")
        self.assertEqual(self.api_change(base, head), (set(), set()))

    def test_api_comparison_sees_a_retyped_parameter(self):
        base = self.API_NAMES.format(recv="t", a="a", n="n", err="err", x="x", y="y", v="v", c="c")
        head = base.replace("M(a int)", "M(a int64)")
        removed, added = self.api_change(base, head)
        self.assertEqual(len(removed), 1, removed)
        self.assertEqual(len(added), 1, added)

    def test_one_exported_declaration_is_removed(self):
        f = finding("Breaking changes")
        removed = self.exported_api(BASE) - self.exported_api(HEAD)
        self.assertEqual(removed, {_signature(f["quoted"].removesuffix(" {"))})


if __name__ == "__main__":
    unittest.main()
