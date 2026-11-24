# Tests for golang-review's seeded-defect fixture and its areas table.
# Run: python3 -m unittest discover -s tests (from the skill directory).
#
# The fixture is a Go module before (base/) and after (head/) a sample change
# with at least one planted defect in each of the ten checklist areas.
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
    """Return {id: dict(area, severity, side, path, line, deleted, quoted, body)} from expected-findings.md."""
    text = EXPECTED.read_text(encoding="utf-8")
    headings = list(FINDING_RE.finditer(text))
    findings = {}
    for index, heading in enumerate(headings):
        end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
        body = text[heading.end() : end]
        location = LOCATION_RE.search(body)
        quoted = LINE_RE.search(body)
        if heading.group(1) in findings:
            raise AssertionError(f"expected-findings.md lists {heading.group(1)} twice")
        findings[heading.group(1)] = {
            "area": heading.group(3).strip(),
            "severity": heading.group(2),
            "side": location.group(1) if location else None,
            "path": location.group(2) if location else None,
            "line": int(location.group(3)) if location else None,
            "deleted": bool(location and location.group(4)),
            "quoted": quoted.group(1) if quoted else None,
            "body": body,
        }
    return findings


def finding(area):
    """Return the one finding listed for area; an area with several is chosen by id instead."""
    found = [f for f in expected_findings().values() if f["area"] == area.lower()]
    if len(found) != 1:
        raise AssertionError(f"expected-findings.md has {len(found)} {area.lower()} findings; select one by id")
    return found[0]


def fuzz_finding():
    """Return the testing finding for a new decoder with no Fuzz target."""
    found = [
        f for f in expected_findings().values() if f["area"] == "testing and coverage" and "Fuzz target" in f["body"]
    ]
    if len(found) != 1:
        raise AssertionError(f"expected-findings.md has {len(found)} testing findings about a Fuzz target, not 1")
    return found[0]


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
        compound = re.match(r"type (\w+)(?:\[.*\])? (struct|interface) \{$", raw)
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


def changed_files(base=BASE, head=HEAD):
    """Return the module-relative paths of files that differ between base and head."""
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
        # dircmp compares files by size and mtime only, so compare the common
        # files' contents here.
        for name in cmp.common_files:
            if not filecmp.cmp(left / name, right / name, shallow=False):
                changed.append(prefix + name)
        for name, sub in cmp.subdirs.items():
            walk(sub, left / name, right / name, prefix + name + "/")

    walk(filecmp.dircmp(base, head), base, head)
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

    def test_every_step_reference_is_in_the_table(self):
        named = {re.search(r"\]\((references/step-[a-z-]+\.md)\)", row[3]).group(1) for row in areas_table()}
        on_disk = {f"references/{p.name}" for p in (SKILL / "references").glob("step-*.md")}
        self.assertEqual(on_disk, named)

    def test_review_step_makes_reading_the_references_mandatory(self):
        # Reviews loaded golang-practices but read none of the reference files,
        # so the review step must order the reads, and an area whose step
        # reference was not read must count as not reviewed.
        text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        step = re.search(r"(?ms)^6\. \*\*Review each area\.\*\*.*?(?=^7\. )", text)
        self.assertIsNotNone(step, "SKILL.md has no step 6, Review each area")
        body = step.group(0)
        self.assertIn("Read its step reference now", body)
        self.assertIn("then each practices reference the table names for it", body)
        self.assertIn("An area whose step reference was not read is not reviewed", body)

    def test_report_lists_the_files_read_for_each_area(self):
        # output.md's example lists, per area, the step reference and the
        # golang-practices references read, matching the areas table.
        text = (SKILL / "references" / "output.md").read_text(encoding="utf-8")
        section = text.split("\n## Coverage and limits\n", 1)[1].split("\n## ", 1)[0]
        rows = re.findall(r"(?m)^  (\d+)\. ([^:]+): read (.+)$", section)
        self.assertEqual([area for _, area, _ in rows], AREAS)
        for order, area, _, step, practices in areas_table():
            read = dict((a, files) for _, a, files in rows)[area]
            with self.subTest(area=area):
                step_name = re.search(r"\]\((references/step-[a-z-]+\.md)\)", step).group(1)
                self.assertIn(f"`{step_name}`", read)
                for name in re.findall(r"`(references/[a-z-]+\.md)`", practices):
                    self.assertIn(f"golang-practices `{name}`", read)
        self.assertIn("step reference not read", text)


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
    def test_lists_a_finding_for_every_area(self):
        self.assertEqual({f["area"] for f in expected_findings().values()}, {area.lower() for area in AREAS})

    def test_each_finding_quotes_the_line_it_names(self):
        for id, f in expected_findings().items():
            with self.subTest(id=id):
                self.assertIsNotNone(f["path"], f"{id}: no '- Location: `head/<path>:<line>`'")
                self.assertIsNotNone(f["quoted"], f"{id}: no '- Line: `<text>`'")
                self.assertEqual(f["side"] == "base", f["deleted"], f"{id}: only a deleted line sits in base/")
                root = BASE if f["side"] == "base" else HEAD
                lines = (root / f["path"]).read_text(encoding="utf-8").splitlines()
                self.assertLessEqual(f["line"], len(lines), f"{id}: {f['path']} has {len(lines)} lines")
                # The whole line, not a substring: a fix that keeps the call on the
                # same line (`errs[i] = json.Unmarshal(raw, &l)`) must fail here.
                self.assertEqual(
                    lines[f["line"] - 1].strip(),
                    f["quoted"],
                    f"{id}: {f['path']}:{f['line']} is {lines[f['line'] - 1]!r}",
                )
                if f["deleted"]:
                    head_file = HEAD / f["path"]
                    head_lines = head_file.read_text(encoding="utf-8").splitlines() if head_file.exists() else []
                    self.assertNotIn(f["quoted"], [line.strip() for line in head_lines])

    def test_findings_point_at_changed_files(self):
        changed = changed_files()
        for id, f in expected_findings().items():
            with self.subTest(id=id):
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
                "orders/upload.go",
                "orders/upload_test.go",
                "pricing/go.mod",
            ],
        )

    def test_a_new_decoder_has_no_fuzz_target(self):
        # Testing and coverage, second finding: the change adds a function
        # that decodes untrusted input, and no Fuzz target for it.
        f = fuzz_finding()
        self.assertEqual((f["severity"], f["side"]), ("minor", "head"))
        name = re.match(r"func (\w+)\(", f["quoted"])
        self.assertIsNotNone(name, f"{f['quoted']!r} does not declare a function")
        for path in BASE.rglob("*.go"):
            self.assertNotIn(f"func {name.group(1)}(", path.read_text(encoding="utf-8"), "the base already has it")
        for path in HEAD.rglob("*_test.go"):
            self.assertNotRegex(path.read_text(encoding="utf-8"), r"(?m)^func Fuzz", f"{path.name} has a Fuzz target")

    def test_names_each_missing_ci_check(self):
        # The fixture has no CI, so every check of the suite that CI can show
        # is a missing line. The Fuzz target rule is enforced by the review,
        # not CI, so it is not one of them. Read the suite from golang-practices.
        suite = (PRACTICES / "references" / "checks.md").read_text(encoding="utf-8")
        listed = suite.split("\n## The checks\n", 1)[1].split("\n## ", 1)[0]
        checks = re.findall(r"(?m)^- \*\*([^*]+)\*\*", listed)
        self.assertIn("Fuzz targets", checks)
        self.assertIn("CI cannot tell that a Fuzz target is missing", listed)
        text = EXPECTED.read_text(encoding="utf-8")
        line = re.search(r"(?m)^- The repository has no CI\. .*$", text)
        self.assertIsNotNone(line)
        prompts = (SKILL / "tests" / "prompts.md").read_text(encoding="utf-8")
        case = re.search(r"(?m)^- The fixture has no CI\. .*$", prompts)
        self.assertIsNotNone(case)
        for page, found in (("expected-findings.md", line.group(0)), ("prompts.md", case.group(0))):
            for check in checks:
                with self.subTest(page=page, check=check):
                    if check == "Fuzz targets":
                        self.assertRegex(found, r"Fuzz target[^.]*not a (missing|line)")
                    elif " " in check:
                        self.assertIn("race-enabled tests with coverage", found)
                    else:
                        self.assertIn(f"`{check}`", found)

    def test_changed_files_compares_contents(self):
        # A same-size edit with a matching mtime, as after extracting an archive,
        # must still count as a change.
        with tempfile.TemporaryDirectory() as tmp:
            base, head = Path(tmp) / "base", Path(tmp) / "head"
            for module, version in ((base, "1.21"), (head, "1.22")):
                module.mkdir()
                go_mod = module / "go.mod"
                go_mod.write_text(f"module example\n\ngo {version}\n", encoding="utf-8")
                os.utime(go_mod, (1_700_000_000, 1_700_000_000))
            self.assertEqual(changed_files(base, head), ["go.mod"])

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


# Words the fixture declares that are also ordinary English or Go words, so
# they may appear in the skill text for their own sake.
COMMON_WORDS = {"Empty", "Line", "Lines", "Merge", "Quantity", "SKU", "Units", "add", "orders"}

# Values from the fixture's code and expected results that are not declared
# names but would still give its answers away.
FIXTURE_LITERALS = ["B2", "AUD", "price_cents", "order_lines", "1299", "2400", "433", "97.1%"]


def fixture_terms():
    """Return the names, paths, and values that identify the fixture.

    Taken from its Go files: every declared function, method, type, constant,
    variable, and exported struct field, each module path, and each file's path
    in its module, plus FIXTURE_LITERALS, less COMMON_WORDS.
    """
    terms = set(FIXTURE_LITERALS)
    for root in (BASE, HEAD):
        for path in root.rglob("*.go"):
            text = path.read_text(encoding="utf-8")
            terms.update(re.findall(r"(?m)^func (?:\([^)]*\) )?(\w+)", text))
            terms.update(re.findall(r"(?m)^(?:type|const|var) (\w+)", text))
            terms.update(re.findall(r"(?m)^\t([A-Z]\w*) +\S", text))
            terms.add(path.relative_to(root).as_posix())
            terms.add("./" + path.parent.relative_to(root).as_posix())
        for path in root.rglob("go.mod"):
            terms.update(re.findall(r"(?m)^module (\S+)", path.read_text(encoding="utf-8")))
            if path.parent != root:
                terms.add("./" + path.parent.relative_to(root).as_posix())
    return terms - COMMON_WORDS


class AnswerKeyTest(unittest.TestCase):
    """The skill text must not contain the fixture's answers.

    A run of the skill against the fixture shows that the skill finds the
    planted defects only if nothing it reads names them. Examples in SKILL.md
    and references/ use a different domain.
    """

    def test_derives_the_fixture_terms(self):
        terms = fixture_terms()
        for term in ("Summarise", "LinesQuery", "TotalCents", "orders/query.go", "./orders", "example.com/pricing"):
            self.assertIn(term, terms)
        self.assertNotIn("Merge", terms)

    def test_skill_text_does_not_name_the_fixture(self):
        pattern = re.compile(
            r"(?<![\w/-])(" + "|".join(re.escape(t) for t in sorted(fixture_terms(), key=len, reverse=True)) + r")(?![\w-])"
        )
        pages = [SKILL / "SKILL.md", *sorted((SKILL / "references").glob("*.md"))]
        pages += [PRACTICES / "SKILL.md", *sorted((PRACTICES / "references").glob("*.md"))]
        found = []
        for page in pages:
            for number, line in enumerate(page.read_text(encoding="utf-8").splitlines(), 1):
                found += [f"{page.relative_to(SKILL.parent)}:{number}: {m.group(1)}" for m in pattern.finditer(line)]
        self.assertEqual(found, [], "fixture terms in the skill text:\n" + "\n".join(found))


class SkillTextTest(unittest.TestCase):
    """Instructions that host runs showed agents skipping stay explicit."""

    def section(self, page, heading):
        text = (SKILL / page).read_text(encoding="utf-8")
        match = re.search(rf"(?ms)^## {re.escape(heading)}\n(.*?)(?=^## |\Z)", text)
        self.assertIsNotNone(match, f"{page} has no '## {heading}'")
        return match.group(1)

    def test_an_archive_is_not_the_worktree(self):
        worktree = self.section("references/target.md", "The temporary worktree")
        self.assertIn("`git worktree add`", worktree)
        self.assertRegex(worktree, r"`git archive`[^.]*not a substitute")

    def test_the_branch_base_is_the_remote_tracking_ref(self):
        branch = self.section("references/target.md", "Branch")
        self.assertIn("git merge-base refs/remotes/origin/<base branch> <branch>", branch)
        no_target = self.section("references/target.md", "No target named")
        self.assertIn("refs/remotes/origin/<default branch>", no_target)

    def test_a_change_made_to_show_a_test_cannot_fail_is_put_back(self):
        # step-testing.md lets the review break the code to show a test cannot
        # fail; checks.md must allow that and restore the file before the later
        # areas run their checks on it.
        self.assertIn("as `checks.md` describes", self.section("references/step-testing.md", "Evidence"))
        checks = self.section("references/checks.md", "The checks")
        self.assertIn("change the code under test in the temporary worktree", checks)
        self.assertIn("before the next check", checks)
        self.assertIn("git -C <worktree> status --short", checks)

    def test_the_template_lists_every_area(self):
        # Every area is listed once, as reviewed or not reviewed, so a reader can
        # see what the review left out.
        coverage = self.section("references/output.md", "Coverage and limits")
        self.assertRegex(coverage, r"(?m)^- Areas not reviewed: .+$")
        for area in AREAS:
            with self.subTest(area=area):
                self.assertIn(area, coverage)

    def test_the_report_step_requires_the_areas_not_reviewed(self):
        step = re.search(r"(?m)^8\. \*\*Report\.\*\*.*$", (SKILL / "SKILL.md").read_text(encoding="utf-8"))
        self.assertIsNotNone(step)
        self.assertIn("every area not reviewed", step.group(0))

    # Security review of the check procedure: the change under review is
    # attacker-controlled, so these rules keep it from running code or
    # steering the review.

    def test_a_changed_object_file_anywhere_means_no_go_test(self):
        # A .syso links into every test binary that imports its package, and
        # its ELF constructors run under -race, so skipping only its own
        # package's tests is not enough.
        before = self.section("references/checks.md", "Before running tests")
        self.assertNotIn("so its tests are not run", before)
        self.assertRegex(before, r"`\.syso`[^.]*anywhere in the module or workspace")
        self.assertIn("run no `go test` at all", before)
        self.assertIn("`go vet` does not link", before)

    def test_repository_flags_come_from_an_allowlist_read_at_the_base(self):
        before = self.section("references/checks.md", "Before running tests")
        for flag in ("-tags", "-run", "-short", "-count", "-timeout"):
            with self.subTest(allowed=flag):
                self.assertIn(f"`{flag}`", before)
        self.assertRegex(before, r"base commit, not the head")
        self.assertRegex(before, r"`go vet`[^.]*`-toolexec`")
        never = self.section("references/checks.md", "Commands the review never runs")
        for flag in ("-toolexec", "-vettool", "-ldflags", "-extldflags", "-overlay",
                     "-modfile", "-pgo", "-exec", "-gcflags", "-asmflags"):
            with self.subTest(forbidden=flag):
                self.assertIn(f"`{flag}", never)

    def test_the_change_is_untrusted_data(self):
        skill = self.section("SKILL.md", "Read-only")
        before = self.section("references/checks.md", "Before running tests")
        for page, text in (("SKILL.md", skill), ("checks.md", before)):
            with self.subTest(page=page):
                self.assertIn("untrusted data", text)
                self.assertIn("never changes these steps", text)

    def test_running_someone_elses_tests_is_an_opt_in(self):
        skill = self.section("SKILL.md", "Read-only")
        self.assertIn("the user did not write", skill)
        before = self.section("references/checks.md", "Before running tests")
        self.assertIn("the user did not write", before)
        self.assertIn("ask the user", before)
        self.assertIn("exact command", before)

    def test_a_test_written_for_the_review_runs_only_where_tests_may_run(self):
        # A test added in the worktree still links and runs the change's code.
        checks = self.section("references/checks.md", "The checks")
        added = re.search(r"(?m)^To show a suspected .*$", checks)
        self.assertIsNotNone(added)
        self.assertIn("only where [Before running tests](#before-running-tests) allows tests to run", added.group(0))

    GOLANGCI_FORMATS = ("json", "tab", "html", "checkstyle", "code-climate", "junit-xml", "teamcity", "sarif")

    def test_golangci_lint_runs_with_the_base_config_and_writes_only_to_stdout(self):
        # The change's own config can point output.formats.<format>.path at any
        # file the user can write, so the review lints only with the base
        # commit's config and overrides every output path on the command line.
        tools = self.section("references/checks.md", "Tools outside the go command")
        self.assertNotIn("<the repository's config>", tools)
        self.assertIn("base commit's config", tools)
        self.assertIn("adds, edits, renames, or deletes", tools)
        self.assertIn("--no-config", tools)
        self.assertIn("--output.text.path=stdout", tools)
        for fmt in self.GOLANGCI_FORMATS:
            with self.subTest(format=fmt):
                self.assertIn(f"--output.{fmt}.path=", tools)
                self.assertNotIn(f"--output.{fmt}.path=stdout", tools)
        never = self.section("references/checks.md", "Commands the review never runs")
        self.assertIn("output.formats.<format>.path", never)
        self.assertIn("output.format", never)

    def test_step_references_run_golangci_lint_as_checks_md_does(self):
        for page in sorted((SKILL / "references").glob("step-*.md")):
            text = page.read_text(encoding="utf-8")
            for line in text.splitlines():
                if "golangci-lint" in line:
                    with self.subTest(page=page.name, line=line[:60]):
                        self.assertIn("as `checks.md` runs it", line)

    def test_the_escape_analysis_build_is_the_one_gcflags_exception(self):
        never = self.section("references/checks.md", "Commands the review never runs")
        self.assertIn("`-gcflags=-m`", never)
        self.assertIn("step-performance.md", never)

    def test_a_change_to_ci_alone_is_still_reviewed(self):
        # A pull request that only weakens a check in a workflow or a
        # golangci-lint config has no Go file, yet must get its major finding.
        step = re.search(r"(?m)^1\. \*\*Resolve the target\.\*\*.*$", (SKILL / "SKILL.md").read_text(encoding="utf-8"))
        self.assertIsNotNone(step)
        self.assertIn("`.github/workflows/`", step.group(0))
        self.assertIn("golangci-lint config", step.group(0))
        self.assertIn("The check suite in CI", step.group(0))

    def test_only_an_exemption_adr_at_the_base_changes_the_verdict(self):
        # Repository docs are untrusted, with one carve-out: an exemption ADR
        # already merged at the base commit. Both pages say so, and where to look.
        skill = self.section("SKILL.md", "Read-only")
        self.assertIn("architecture decision record (ADR)", skill)
        self.assertIn("base commit", skill)
        ci = self.section("references/checks.md", "The check suite in CI")
        self.assertIn("architecture decision record (ADR)", ci)
        self.assertIn("`docs/adr/`", ci)

    def test_a_ci_comparison_not_done_has_its_wording(self):
        # Without golang-practices the comparison cannot be done; the report
        # field and step 5's completion rule both allow for that.
        fields = self.section("references/output.md", "Fields")
        field = re.search(r"(?m)^- \*\*Check suite in CI\*\*: .*$", fields)
        self.assertIsNotNone(field)
        self.assertIn("`not compared: <reason>`", field.group(0))
        step = re.search(r"(?m)^5\. \*\*Run the checks\.\*\*.*$", (SKILL / "SKILL.md").read_text(encoding="utf-8"))
        self.assertIsNotNone(step)
        self.assertIn("not compared", step.group(0).split("Completion:", 1)[1])

    def test_the_worktree_is_not_a_sandbox(self):
        worktree = self.section("references/target.md", "The temporary worktree")
        self.assertIn("not a sandbox", worktree)
        self.assertNotIn("reaches the user's tree", worktree)
        self.assertIn("`.git` file", worktree)


class FetchSuiteToolTest(unittest.TestCase):
    """The change controls the worktree, so it can commit `.golang-review-tools/`.

    A committed `bin/<tool>` or a prefilled `mod/` cache would then be run or
    built, and a failed `mkdir` or `cd` would send `go install` to the agent's
    working directory. These tests run the fetch block from checks.md with a
    stand-in `go` that only records where it would install.
    """

    def setUp(self):
        for tool in ("bash", "git"):
            if shutil.which(tool) is None:
                self.skipTest(f"{tool} is not on PATH")
        text = (SKILL / "references" / "checks.md").read_text(encoding="utf-8")
        section = text.split("\n### Fetching a suite tool\n", 1)[1].split("\n### ", 1)[0]
        self.section = section
        self.block = re.search(r"```sh\n(.*?)```", section, re.S).group(1)
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)

    def fetch(self, planted=None, untracked=None):
        """Run the fetch block from cwd=user repo; return (exit, recorded GOBIN, cwd listing)."""
        user = self.tmp / "user"
        worktree = self.tmp / "review" / "wt"
        git = ["git", "-c", "user.email=r@example.com", "-c", "user.name=r", "-c", "core.hooksPath=/dev/null"]
        user.mkdir()
        subprocess.run([*git, "init", "-q"], cwd=user, check=True)
        (user / "go.mod").write_text("module example.com/m\n\ngo 1.22\n", encoding="utf-8")
        if planted:
            path = user / planted
            path.parent.mkdir(parents=True)
            path.write_text("#!/bin/sh\necho planted\n", encoding="utf-8")
        subprocess.run([*git, "add", "-A", "-f"], cwd=user, check=True)
        subprocess.run([*git, "commit", "-qm", "head"], cwd=user, check=True)
        subprocess.run([*git, "worktree", "add", "-q", "--detach", str(worktree), "HEAD"], cwd=user, check=True)
        if untracked:
            (worktree / untracked).mkdir(parents=True)
        fake = self.tmp / "fakebin"
        fake.mkdir()
        record = self.tmp / "go-install-called"
        (fake / "go").write_text(f'#!/bin/sh\nprintf %s "$GOBIN" > {record}\n', encoding="utf-8")
        (fake / "go").chmod(0o755)
        script = self.block.replace("<worktree>", str(worktree)).replace(
            "<package>@<version>", "example.com/tool@v1.0.0"
        )
        env = dict(os.environ, PATH=f"{fake}{os.pathsep}{os.environ['PATH']}")
        result = subprocess.run(["bash", "-c", script], cwd=user, env=env, capture_output=True, text=True)
        called = record.read_text(encoding="utf-8") if record.exists() else None
        listing = sorted(p.name for p in user.iterdir())
        return result.returncode, called, listing, worktree

    def test_fetches_into_the_worktree_when_the_directory_is_absent(self):
        code, called, listing, worktree = self.fetch()
        self.assertEqual(code, 0)
        self.assertEqual(called, str(worktree / ".golang-review-tools" / "bin"))
        self.assertEqual(listing, [".git", "go.mod"])

    def test_refuses_a_tools_directory_the_change_commits(self):
        for planted in (".golang-review-tools/bin/golangci-lint", ".golang-review-tools/mod/cache/x"):
            with self.subTest(planted=planted):
                self.reset_tmp()
                code, called, listing, _ = self.fetch(planted=planted)
                self.assertNotEqual(code, 0)
                self.assertIsNone(called, "go install ran")
                self.assertEqual(listing, [".git", ".golang-review-tools", "go.mod"])

    def test_refuses_a_tools_directory_already_on_disk(self):
        # Uncommitted changes are copied into a worktree made at HEAD, so the
        # head tree alone does not show everything on disk.
        code, called, listing, _ = self.fetch(untracked=".golang-review-tools/mod")
        self.assertNotEqual(code, 0)
        self.assertIsNone(called, "go install ran")
        self.assertEqual(listing, [".git", "go.mod"])

    def reset_tmp(self):
        for child in self.tmp.iterdir():
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()

    def test_the_block_uses_absolute_paths_and_never_changes_directory(self):
        self.assertNotIn("$PWD", self.block)
        self.assertNotRegex(self.block, r"(?m)(^|&&|;)\s*cd ")
        self.assertNotIn("mkdir -p", self.block)
        self.assertIn("git -C <worktree> ls-tree HEAD .golang-review-tools", self.section)
        self.assertIn("not run: ", self.section)


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
        f = expected_findings()["G3"]
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

    API_GENERICS = """// Package api is a probe.
package api

// Box holds a value.
type Box[T any] struct {{
	Value T
{field}}}

// Bytes holds byte-like data.
type Bytes[T ~[]byte] struct {{
	Data T
{data}}}

// Getter gets.
type Getter[K comparable, V any] interface {{
	Get(key K) (V, bool)
{method}}}
"""

    def test_api_comparison_sees_members_removed_from_generic_types(self):
        base = self.API_GENERICS.format(field="\tLabel string\n", data="\tSize int\n", method="\tLen() int\n")
        head = self.API_GENERICS.format(field="", data="", method="")
        removed, added = self.api_change(base, head)
        self.assertEqual(added, set())
        self.assertEqual(removed, {"Box Label string", "Bytes Size int", "Getter Len() int"})

    def test_one_exported_declaration_is_removed(self):
        f = finding("Breaking changes")
        removed = self.exported_api(BASE) - self.exported_api(HEAD)
        self.assertEqual(removed, {_signature(f["quoted"].removesuffix(" {"))})


if __name__ == "__main__":
    unittest.main()
