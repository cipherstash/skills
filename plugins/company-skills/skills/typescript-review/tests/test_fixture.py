# Tests for typescript-review's seeded-defect fixture and the skill text that host runs showed agents skipping.
# Run: python3 -m unittest discover -s tests (from the skill directory).
#
# The fixture is a TypeScript package before (base/) and after (head/) a sample change with one planted defect for
# each area this slice of the skill reviews: error handling and type safety. expected-findings.md lists what a correct
# review must report. These tests keep the fixture honest: the base is clean, each planted defect comes from the
# change, and every location in expected-findings.md is exactly the line it quotes. They also check that no fixture
# answer appears in the skill's text, so a review that finds the defects must have looked for them.
#
# FixtureToolsTest checks that the tools catch what expected-findings.md says they catch: it runs tsc, type-aware
# oxlint, and Vitest over temporary copies of base/ and head/, and a probe test for each defect no tool shows. It needs
# Node and pnpm, and installs the tools from typescript-practices' examples package and its lockfile. Without them it
# is skipped locally, and fails when the CI environment variable is set. CI's TypeScript check suite still runs over
# typescript-practices' examples package alone, never over this fixture.
import filecmp
import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
PRACTICES = SKILL.parent / "typescript-practices"
REPO = SKILL.parents[3]
FIXTURE = SKILL / "tests" / "fixtures" / "seeded-change"
BASE = FIXTURE / "base"
HEAD = FIXTURE / "head"
EXPECTED = FIXTURE / "expected-findings.md"
# The fixture's tools are installed from typescript-practices' examples package, whose committed lockfile pins them.
EXAMPLES = PRACTICES / "examples"
OXLINT_CONFIG = PRACTICES / "assets" / "oxlintrc.json"

# The areas this slice reviews, in the order of SKILL.md's areas table. #150 adds the other nine.
AREAS = ["Error handling", "Type safety"]

# One expected finding: "## T1 · major · error handling" and, below it,
# "- Location: `head/<path>:<line>`" and "- Line: `<text quoted from that line>`".
FINDING_RE = re.compile(r"(?m)^## (T\d+) · (critical|major|minor) · (.+)$")
LOCATION_RE = re.compile(r"(?m)^- Location: `(head|base)/([^`:]+):(\d+)`( \(deleted\))?")
# A line that holds a backtick is quoted in a double-backtick code span: ``throw `x`;``.
LINE_RE = re.compile(r"(?m)^- Line: (?:``(.+)``|`([^`]+)`)$")

SOURCE_SUFFIXES = {".ts", ".tsx", ".mts", ".cts", ".js", ".mjs", ".cjs"}

# The defects each area's step reports, as patterns over one line of source. The base must match none of them.
# A throw whose operand is not a `new` expression or a caught error's name throws a value the code built itself.
THROW_NON_ERROR = re.compile(r"\bthrow\s+(?!new\b)(?!error\b|err\b|e\b|cause\b)\S")
CAST_THROUGH = re.compile(r"\bas\s+(?:unknown|any)\s+as\b")
EXPLICIT_ANY = re.compile(r"(?::|<|,|\bas)\s*any\b")
NON_NULL = re.compile(r"[\w)\]]!(?:\.|\[|\)|;|,|\s*$)")
EMPTY_CATCH = re.compile(r"catch\s*(?:\([^)]*\))?\s*\{\s*\}")


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
            "quoted": (quoted.group(1) or quoted.group(2)) if quoted else None,
            "body": body,
        }
    return findings


def finding(area):
    """Return the one finding listed for area."""
    found = [f for f in expected_findings().values() if f["area"] == area.lower()]
    if len(found) != 1:
        raise AssertionError(f"expected-findings.md has {len(found)} {area.lower()} findings")
    return found[0]


def changed_files(base=BASE, head=HEAD):
    """Return the package-relative paths of files that differ between base and head."""
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
        # dircmp compares files by size and mtime only, so compare the common files' contents here.
        for name in cmp.common_files:
            if not filecmp.cmp(left / name, right / name, shallow=False):
                changed.append(prefix + name)
        for name, sub in cmp.subdirs.items():
            walk(sub, left / name, right / name, prefix + name + "/")

    walk(filecmp.dircmp(base, head), base, head)
    return sorted(changed)


def source_lines(root):
    """Yield (relative path, line number, line) for every TypeScript and JavaScript line under root."""
    for path in sorted(root.rglob("*")):
        if path.suffix in SOURCE_SUFFIXES:
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                code = line.split("//", 1)[0]
                yield path.relative_to(root).as_posix(), number, code


def matches(root, pattern):
    return [(path, number) for path, number, code in source_lines(root) if pattern.search(code)]


class ExpectedFindingsTest(unittest.TestCase):
    def test_lists_one_finding_for_each_area(self):
        self.assertEqual(sorted(f["area"] for f in expected_findings().values()), [a.lower() for a in AREAS])

    def test_each_finding_quotes_the_line_it_names(self):
        for key, f in expected_findings().items():
            with self.subTest(id=key):
                self.assertIsNotNone(f["path"], f"{key}: no '- Location: `head/<path>:<line>`'")
                self.assertIsNotNone(f["quoted"], f"{key}: no '- Line: `<text>`'")
                self.assertEqual(f["side"] == "base", f["deleted"], f"{key}: only a deleted line sits in base/")
                root = BASE if f["side"] == "base" else HEAD
                lines = (root / f["path"]).read_text(encoding="utf-8").splitlines()
                self.assertLessEqual(f["line"], len(lines), f"{key}: {f['path']} has {len(lines)} lines")
                # The whole line, not a substring, so a fix that keeps part of the line fails here.
                self.assertEqual(
                    lines[f["line"] - 1].strip(),
                    f["quoted"],
                    f"{key}: {f['path']}:{f['line']} is {lines[f['line'] - 1]!r}",
                )

    def test_each_defect_comes_from_the_change(self):
        changed = changed_files()
        for key, f in expected_findings().items():
            with self.subTest(id=key):
                self.assertIn(f["path"], changed)
                base_file = BASE / f["path"]
                base_lines = base_file.read_text(encoding="utf-8").splitlines() if base_file.exists() else []
                self.assertNotIn(f["quoted"], [line.strip() for line in base_lines], f"{key}: the base has the line")

    def test_the_change_touches_only_the_planted_files(self):
        self.assertEqual(
            changed_files(),
            ["src/labels.test.ts", "src/labels.ts", "src/manifest.test.ts", "src/manifest.ts"],
        )

    def test_the_error_handling_defect_throws_a_value_that_is_not_an_error(self):
        f = finding("Error handling")
        self.assertEqual(f["side"], "head")
        self.assertRegex(f["quoted"], THROW_NON_ERROR)
        self.assertEqual(matches(HEAD, THROW_NON_ERROR), [(f["path"], f["line"])])

    def test_the_type_safety_defect_casts_through_unknown(self):
        f = finding("Type safety")
        self.assertEqual(f["side"], "head")
        self.assertRegex(f["quoted"], CAST_THROUGH)
        self.assertEqual(matches(HEAD, CAST_THROUGH), [(f["path"], f["line"])])

    def test_the_head_has_no_other_planted_pattern(self):
        # Only the two planted defects: no explicit `any`, non-null assertion, or empty catch anywhere in the head.
        for name, pattern in (("any", EXPLICIT_ANY), ("non-null", NON_NULL), ("empty catch", EMPTY_CATCH)):
            with self.subTest(pattern=name):
                self.assertEqual(matches(HEAD, pattern), [])

    def test_the_base_is_clean(self):
        patterns = {
            "throw of a non-Error": THROW_NON_ERROR,
            "cast through unknown or any": CAST_THROUGH,
            "explicit any": EXPLICIT_ANY,
            "non-null assertion": NON_NULL,
            "empty catch": EMPTY_CATCH,
        }
        for name, pattern in patterns.items():
            with self.subTest(pattern=name):
                self.assertEqual(matches(BASE, pattern), [])
        # The base already returns its expected failures as a result union, so the change is what breaks the rule.
        manifest = (BASE / "src" / "manifest.ts").read_text(encoding="utf-8")
        self.assertIn("failure: {", manifest)
        self.assertNotRegex(manifest, r"\bthrow\b")

    def test_the_patterns_find_what_they_name(self):
        # The base-is-clean test is only as good as its patterns.
        self.assertRegex('throw "no such key";', THROW_NON_ERROR)
        self.assertRegex("throw { code: 1 };", THROW_NON_ERROR)
        self.assertNotRegex('throw new Error("x");', THROW_NON_ERROR)
        self.assertNotRegex("throw error;", THROW_NON_ERROR)
        self.assertRegex("const x = y as unknown as Z;", CAST_THROUGH)
        self.assertRegex("let v: any = 1;", EXPLICIT_ANY)
        self.assertRegex("const m = new Map<string, any>();", EXPLICIT_ANY)
        self.assertNotRegex("// many", EXPLICIT_ANY)
        self.assertRegex("return user!.name;", NON_NULL)
        self.assertRegex("const first = items[0]!;", NON_NULL)
        self.assertNotRegex("if (a !== b) {", NON_NULL)
        self.assertNotRegex("if (!ok) {", NON_NULL)
        self.assertRegex("} catch {}", EMPTY_CATCH)
        self.assertRegex("} catch (error) {  }", EMPTY_CATCH)

    def test_the_settings_a_review_reports_are_the_ones_step_3_records(self):
        # A review graded against the answer key must not miss a setting that step 3 never tells it to record.
        body = step(3, "Read the TypeScript version and compiler settings.")
        recorded = set(re.findall(r"`(\w+)`", body.split("and record", 1)[1].split("Read them at the head", 1)[0]))
        self.assertIn("strict", recorded)
        checks = EXPECTED.read_text(encoding="utf-8").split("## Checks a correct review reports\n", 1)[1]
        settings = re.search(r"(?m)^- The TypeScript version.*$", checks)
        self.assertIsNotNone(settings)
        options = set(json.loads((HEAD / "tsconfig.json").read_text(encoding="utf-8"))["compilerOptions"])
        named = set(re.findall(r"`(\w+)`", settings.group(0))) & (options | recorded)
        self.assertEqual(named - recorded, set(), "expected-findings.md asks for settings step 3 does not record")
        for name in sorted(recorded & options):
            with self.subTest(setting=name):
                self.assertIn(name, named, f"the fixture sets {name} and step 3 records it, so the key names it")

    def test_changed_files_compares_contents(self):
        # A same-size edit with a matching mtime, as after extracting an archive, must still count as a change.
        with tempfile.TemporaryDirectory() as tmp:
            base, head = Path(tmp) / "base", Path(tmp) / "head"
            for root, version in ((base, "1"), (head, "2")):
                root.mkdir()
                path = root / "a.ts"
                path.write_text(f"export const v = {version};\n", encoding="utf-8")
                os.utime(path, (1_700_000_000, 1_700_000_000))
            self.assertEqual(changed_files(base, head), ["a.ts"])

    def test_the_fixture_is_excluded_from_the_check_suite(self):
        # The fixture holds planted defects, so CI's TypeScript check suite must never run over it: the job works in
        # typescript-practices' examples package, and no step names this skill's directory.
        workflow = (REPO / ".github" / "workflows" / "validate.yml").read_text(encoding="utf-8")
        job = re.search(r"(?ms)^  typescript-check-suite:\n(.*?)(?=^  [\w-]+:\n|\Z)", workflow)
        self.assertIsNotNone(job, "validate.yml has no typescript-check-suite job")
        self.assertIn("working-directory: plugins/company-skills/skills/typescript-practices/examples", job.group(1))
        self.assertNotIn("typescript-review", job.group(1))
        self.assertNotIn("-r plugins", job.group(1))


# Words the fixture declares that are also ordinary English or TypeScript words, so they may appear in the skill text
# for their own sake.
COMMON_WORDS = {"data", "failure", "id", "message", "type", "value", "error", "items", "candidate"}

# Values from the fixture's code and expected results that are not declared names but would still give its answers
# away.
FIXTURE_LITERALS = ["P-1", "P-9", "zx81", "ZX81", "something went wrong", "parcel-manifest", "NotJson", "NotAParcelList"]


def fixture_terms():
    """Return the names, paths, and values that identify the fixture.

    Taken from its TypeScript files: every declared function, type, constant, variable, and object field, and each
    file's path in its package, plus FIXTURE_LITERALS, less COMMON_WORDS.
    """
    terms = set(FIXTURE_LITERALS)
    for root in (BASE, HEAD):
        for path in root.rglob("*.ts"):
            text = path.read_text(encoding="utf-8")
            terms.update(re.findall(r"(?m)^(?:export )?(?:async )?function (\w+)", text))
            terms.update(re.findall(r"(?m)^(?:export )?(?:type|interface|const|let|class) (\w+)", text))
            terms.update(re.findall(r"(?m)^\s+(\w+)\??: ", text))
            terms.update(re.findall(r"\{ (\w+): string \}", text))
            terms.add(path.relative_to(root).as_posix())
    return terms - COMMON_WORDS


def skill_pages():
    """Every page the skill reads during a review: SKILL.md and each reference."""
    return [SKILL / "SKILL.md", *sorted((SKILL / "references").glob("*.md"))]


def read(page):
    return (SKILL / page).read_text(encoding="utf-8")


def section(page, heading, level=2):
    text = read(page)
    marks = "#" * level
    match = re.search(rf"(?ms)^{marks} {re.escape(heading)}\n(.*?)(?=^#{{1,{level}}} |\Z)", text)
    if match is None:
        raise AssertionError(f"{page} has no '{marks} {heading}'")
    return match.group(1)


def step(number, title):
    """Return SKILL.md's numbered step with this bold title, up to the next step."""
    text = read("SKILL.md")
    match = re.search(rf"(?ms)^{number}\. \*\*{re.escape(title)}\*\*.*?(?=^\d+\. \*\*|^## |\Z)", text)
    if match is None:
        raise AssertionError(f"SKILL.md has no step {number}, {title}")
    return match.group(0)


def frontmatter():
    text = read("SKILL.md")
    match = re.match(r"(?s)^---\n(.*?)\n---\n", text)
    if match is None:
        raise AssertionError("SKILL.md has no frontmatter")
    return dict(re.findall(r"(?m)^(\w[\w-]*): (.*)$", match.group(1)))


def areas_table():
    """Return SKILL.md's areas table rows as lists of cell text."""
    rows = [line for line in section("SKILL.md", "Areas").splitlines() if re.match(r"^\| \d+ \|", line)]
    return [[cell.strip() for cell in row.strip("|").split("|")] for row in rows]


class AnswerKeyTest(unittest.TestCase):
    """The skill text must not contain the fixture's answers.

    A run of the skill against the fixture shows that the skill finds the planted defects only if nothing it reads
    names them. Examples in SKILL.md and references/ use a different domain.
    """

    def test_derives_the_fixture_terms(self):
        terms = fixture_terms()
        for term in ("weightOf", "labelText", "TrackedParcel", "trackingCode", "src/labels.ts", "Parcel"):
            self.assertIn(term, terms)
        self.assertNotIn("message", terms)

    def test_skill_text_does_not_name_the_fixture(self):
        pattern = re.compile(
            r"(?<![\w/-])(" + "|".join(re.escape(t) for t in sorted(fixture_terms(), key=len, reverse=True)) + r")(?![\w-])"
        )
        pages = skill_pages() + [PRACTICES / "SKILL.md", *sorted((PRACTICES / "references").glob("*.md"))]
        found = []
        for page in pages:
            for number, line in enumerate(page.read_text(encoding="utf-8").splitlines(), 1):
                found += [f"{page.relative_to(SKILL.parent)}:{number}: {m.group(1)}" for m in pattern.finditer(line)]
        self.assertEqual(found, [], "fixture terms in the skill text:\n" + "\n".join(found))


class DescriptionTest(unittest.TestCase):
    def test_says_what_it_reviews_and_names_area_only_requests(self):
        description = frontmatter()["description"]
        self.assertEqual(frontmatter()["name"], "typescript-review")
        self.assertLessEqual(len(description), 1024)
        self.assertIn("Reviews a TypeScript change", description)
        # Host runs of golang-review missed "just check the concurrency" until the description named such requests.
        self.assertIn('"just check the async code"', description)

    def test_names_its_limits(self):
        description = frontmatter()["description"]
        self.assertIn("Read-only", description)
        for limit in ("Does not write TypeScript (typescript-practices)", "fix findings (review-fix)",
                      "post to a pull request (review-post)"):
            with self.subTest(limit=limit):
                self.assertIn(limit, description)


class AreasTableTest(unittest.TestCase):
    def test_lists_the_areas_this_slice_reviews(self):
        self.assertEqual([row[1] for row in areas_table()], AREAS)
        self.assertEqual([row[0] for row in areas_table()], ["1", "3"])

    def test_every_area_has_a_step_reference_and_a_practices_reference(self):
        for order, area, _, step_cell, practices in areas_table():
            with self.subTest(area=area):
                link = re.search(r"\]\((references/step-[a-z-]+\.md)\)", step_cell)
                self.assertIsNotNone(link, f"{area}: no step reference in {step_cell!r}")
                step_file = SKILL / link.group(1)
                self.assertTrue(step_file.is_file(), f"{area}: {link.group(1)} does not exist")
                names = re.findall(r"`(references/[a-z-]+\.md)`", practices)
                self.assertTrue(names, f"{area}: no typescript-practices reference named")
                body = step_file.read_text(encoding="utf-8")
                self.assertIn(f"Area {order},", body, f"{link.group(1)} does not state its area number")
                for name in names:
                    self.assertTrue((PRACTICES / name).is_file(), f"{area}: typescript-practices has no {name}")
                    self.assertIn(f"`{name}`", body, f"{link.group(1)} does not name {name}")

    def test_every_step_reference_is_in_the_table(self):
        named = {re.search(r"\]\((references/step-[a-z-]+\.md)\)", row[3]).group(1) for row in areas_table()}
        on_disk = {f"references/{p.name}" for p in (SKILL / "references").glob("step-*.md")}
        self.assertEqual(on_disk, named)

    def test_the_other_areas_are_named_as_not_reviewed(self):
        # The spec's eleven areas: the nine this version has no step for are each listed, so the report can name them.
        others = ["Correctness and edge cases", "Testing and coverage", "Async and concurrency", "Naming and style",
                  "Security", "Performance", "Dependency management", "Documentation", "Breaking changes"]
        areas = section("SKILL.md", "Areas")
        coverage = section("references/output.md", "Coverage and limits")
        for area in others:
            with self.subTest(area=area):
                self.assertIn(area, areas)
                self.assertIn(area, coverage)
        self.assertIn("no step for this area yet", areas)
        self.assertIn("no step for this area yet", coverage)


class ReadingTheReferencesTest(unittest.TestCase):
    def test_loads_typescript_practices_by_name(self):
        body = step(4, "Load typescript-practices.")
        self.assertIn("Invoke the `typescript-practices` skill by name", body)
        self.assertIn("`company-skills:typescript-practices`", body)
        self.assertIn("`$typescript-practices`", body)
        self.assertIn("If it cannot be loaded", body)

    def test_review_step_makes_reading_the_references_mandatory(self):
        # Host runs loaded golang-practices but read none of its references, so the reads are ordered every time.
        body = step(6, "Review each area.")
        self.assertIn("Read its step reference now", body)
        self.assertIn("then each practices reference the table names for it", body)
        self.assertIn("every time", body)
        self.assertIn("An area whose step reference was not read is not reviewed", body)

    def test_report_lists_the_files_read_for_each_area(self):
        coverage = section("references/output.md", "Coverage and limits")
        rows = re.findall(r"(?m)^  (\d+)\. ([^:]+): read (.+)$", coverage)
        self.assertEqual([area for _, area, _ in rows], AREAS)
        read_files = {a: files for _, a, files in rows}
        for _, area, _, step_cell, practices in areas_table():
            with self.subTest(area=area):
                step_name = re.search(r"\]\((references/step-[a-z-]+\.md)\)", step_cell).group(1)
                self.assertIn(f"`{step_name}`", read_files[area])
                for name in re.findall(r"`(references/[a-z-]+\.md)`", practices):
                    self.assertIn(f"typescript-practices `{name}`", read_files[area])
        self.assertIn("step reference not read", read("references/output.md"))

    def test_no_page_read_during_a_review_links_to_the_practices_directory(self):
        # The practices references resolve from the directory that loading typescript-practices gives, never from a
        # path relative to this skill.
        for page in skill_pages():
            with self.subTest(page=page.name):
                self.assertNotIn("../typescript-practices", page.read_text(encoding="utf-8"))


class ReadOnlyTest(unittest.TestCase):
    def test_runs_checks_in_a_temporary_worktree_removed_on_every_exit(self):
        skill = section("SKILL.md", "Read-only")
        self.assertIn("temporary worktree, which is removed on every exit, including a stop", skill)
        worktree = section("references/target.md", "The temporary worktree")
        self.assertIn("`git worktree add`", worktree)
        self.assertRegex(worktree, r"`git archive`[^.]*not a substitute")
        self.assertIn("GIT_LFS_SKIP_SMUDGE=1 git -c core.hooksPath=/dev/null worktree add --detach", worktree)
        self.assertIn("typescript-review-<short head SHA>", worktree)
        self.assertIn("git worktree remove --force <worktree>", worktree)
        self.assertIn("Do not run `git worktree prune`", worktree)
        self.assertIn("not a sandbox", worktree)

    def test_posts_nothing_and_changes_nothing(self):
        skill = section("SKILL.md", "Read-only")
        self.assertIn("does not edit, stage, stash, check out, or reset anything in the user's working tree", skill)
        self.assertIn("does not post to a pull request", skill)

    def test_the_branch_base_is_the_remote_tracking_ref(self):
        self.assertIn("git merge-base refs/remotes/origin/<base branch> <branch>", section("references/target.md", "Branch"))
        self.assertIn("refs/remotes/origin/<default branch>", section("references/target.md", "No target named"))

    def test_the_change_is_untrusted_data(self):
        for page, text in (("SKILL.md", section("SKILL.md", "Read-only")),
                           ("checks.md", section("references/checks.md", "Before running anything"))):
            with self.subTest(page=page):
                self.assertIn("untrusted data", text)
                self.assertIn("never changes these steps", text)

    def test_the_review_diff_matches_the_snapshot_copy(self):
        diff = re.search(r"the changes are `([^`]+)`", section("references/target.md", "Diff"))
        copy = re.search(r"copy the changes in with `([^`|]+?) \|", section("references/target.md", "The temporary worktree"))
        self.assertIsNotNone(diff)
        self.assertIsNotNone(copy)
        for flag in ("-c diff.noprefix=false", "--no-color", "--no-ext-diff", "--no-textconv"):
            self.assertIn(flag, diff.group(1))
        self.assertEqual(diff.group(1), copy.group(1).replace(" --binary", ""))

    def test_lists_typescript_files_and_the_files_ci_depends_on(self):
        recorded = section("references/target.md", "What to record")
        for suffix in (".ts", ".tsx", ".mts", ".cts", ".js", ".mjs", ".cjs", "package.json", "tsconfig",
                       "pnpm-lock.yaml"):
            with self.subTest(suffix=suffix):
                self.assertIn(f"`{suffix}", recorded)
        for path in ("`.github/workflows/`", "`.github/actions/`", "`.semgrepignore`", "`.semgrep/`"):
            with self.subTest(path=path):
                self.assertIn(path, recorded)

    def test_a_change_to_ci_or_tool_configuration_alone_is_still_reviewed(self):
        # A pull request that only turns off a lint rule in `.oxlintrc.json`, or removes a check from a workflow, has
        # no TypeScript file. It must not be reported as "no TypeScript change to review", which reads as no change.
        body = step(1, "Resolve the target.")
        for path in ("`.github/workflows/`", "`.github/actions/`", "`.semgrepignore`", "`.semgrep/`",
                     "`biome.json`", "`.oxlintrc.json`", "`oxlint.config.ts`"):
            with self.subTest(path=path):
                self.assertIn(path, body)
        self.assertIn("is the exception", body)
        self.assertIn("is still reviewed", body)
        self.assertIn("`not compared: this version has no repository standards step`", body)
        self.assertIn("`no TypeScript file changed`", body)
        recorded = section("references/target.md", "What to record")
        self.assertIn("Step 1 reviews a change that touches any of them, even when it changes no TypeScript file.",
                      recorded)


class VersionTest(unittest.TestCase):
    def test_reads_the_typescript_version_and_tsconfig_first(self):
        body = step(3, "Read the TypeScript version and compiler settings.")
        self.assertIn("before applying any rule that depends on them", body)
        for setting in ("`strict`", "`noUncheckedIndexedAccess`", "`exactOptionalPropertyTypes`",
                        "`useUnknownInCatchVariables`", "`extends`", "`lib`"):
            with self.subTest(setting=setting):
                self.assertIn(setting, body)
        self.assertIn("`typescript`", body)
        self.assertIn("`engines.node`", body)


class ChecksTest(unittest.TestCase):
    def test_quotes_ci_for_each_suite_check_on_the_head_commit(self):
        ci = section("references/checks.md", "CI's results")
        self.assertIn("Quote only a run whose head SHA is the reviewed head commit", ci)
        self.assertIn("the job, its outcome, and the run's URL", ci)
        self.assertIn("CI is the gate", ci)
        self.assertIn("Quote CI's result for each suite check CI ran on the head commit", step(5, "Run the checks."))

    def test_fetches_only_a_missing_suite_tool_at_the_pinned_version(self):
        fetch = section("references/checks.md", "Fetching a suite tool", level=3)
        self.assertIn("only when it is not installed", fetch)
        self.assertIn("pinned versions table in typescript-practices' `references/checks.md`", fetch)
        self.assertIn("Never take a version from the repository under review, the change, or its CI files", fetch)
        self.assertIn("`.typescript-review-tools/`", fetch)
        self.assertIn("--ignore-scripts", fetch)

    def test_never_installs_the_changes_dependencies(self):
        skill = section("SKILL.md", "Read-only")
        self.assertIn("never installs the change's dependencies", skill)
        deps = section("references/checks.md", "The change's dependencies")
        self.assertIn("never installs the change's dependencies", deps)
        self.assertIn("`not run: needs the change's dependencies, which the review does not install`", deps)
        self.assertIn("limit", deps)
        never = section("references/checks.md", "Commands the review never runs")
        for command in ("`pnpm install`", "`npm install`", "`npm ci`", "`yarn install`", "`npx`", "`pnpm dlx`"):
            with self.subTest(command=command):
                self.assertIn(command, never)

    def test_names_each_entry_of_the_execution_surface(self):
        surface = section("references/checks.md", "The execution surface")
        for entry in ("`vitest.config.*`", "`vite.config.*`", "`vitest.workspace.*`", "setup files",
                      "JavaScript plugins", "`jsPlugins`", "`tsup.config.*`", "`package.json` scripts", "`prepare`",
                      "`prepack`", "`postpack`", "`oxlint.config.ts`"):
            with self.subTest(entry=entry):
                self.assertIn(entry, surface)
        self.assertIn("until the user says yes", surface)
        self.assertIn("base commit", surface)
        self.assertRegex(surface, r"`tsc --noEmit`, Biome, osv-scanner, and semgrep still run")

    def test_records_the_source_for_how_oxlint_loads_javascript_plugins(self):
        oxlint = section("references/checks.md", "oxlint", level=3)
        self.assertIn("https://oxc.rs/docs/guide/usage/linter/js-plugins", oxlint)
        self.assertIn("https://oxc.rs/docs/guide/usage/linter/nested-config", oxlint)
        self.assertIn("only when its configuration names them", oxlint)
        self.assertIn("--disable-nested-config", oxlint)
        self.assertIn("`extends`", oxlint)
        self.assertIn("`overrides`", oxlint)

    def test_the_configuration_guards_cover_the_whole_extends_chain(self):
        # A file deeper in the extends chain is read from the worktree, the head, when the tool runs. If the guard
        # covered only the files the base configuration names directly, a change could add jsPlugins to such a file and
        # oxlint would load the change's code with no yes.
        for tool in ("Biome", "oxlint"):
            with self.subTest(tool=tool):
                text = section("references/checks.md", tool, level=3)
                first = re.search(r"(?m)^1\. .*$", text)
                self.assertIsNotNone(first)
                self.assertIn("any file in the base configuration's `extends` chain, read at the base", first.group(0))
                self.assertNotIn("a file the base configuration names in `extends`", text)
        # Plugins are code whether they are packages or relative paths, such as `./plugin.js`.
        third = re.search(r"(?m)^3\. .*$", section("references/checks.md", "oxlint", level=3))
        self.assertIsNotNone(third)
        self.assertNotIn("they resolve from `node_modules`", third.group(0))
        self.assertIn("relative path", third.group(0))

    def test_the_execution_surface_is_the_one_typescript_practices_lists(self):
        # CONTRIBUTING.md: where both skills cover a topic, the practices skill states the rule, and the review skill's
        # copy is kept the same.
        review = section("references/checks.md", "The execution surface")
        practices = re.search(r"(?ms)^## The execution surface\n(.*?)(?=^## |\Z)",
                              (PRACTICES / "references" / "checks.md").read_text(encoding="utf-8"))
        self.assertIsNotNone(practices, "typescript-practices' checks.md has no execution surface")
        self.assertIn("as typescript-practices' `references/checks.md` lists them", review)
        for entry in ("`vitest.config.*`", "`vite.config.*`", "`vitest.workspace.*`", "`jsPlugins`",
                      "`oxlint.config.ts`", "`oxlint.config.mts`", "`tsup.config.*`", "`prepare`", "`prepack`",
                      "`postpack`"):
            with self.subTest(entry=entry):
                self.assertIn(entry, review)
                self.assertIn(entry, practices.group(1))

    def test_tools_run_only_with_the_base_commits_configuration(self):
        for tool in ("Biome", "oxlint"):
            with self.subTest(tool=tool):
                text = section("references/checks.md", tool, level=3)
                self.assertIn("base commit's configuration", text)
                self.assertIn("adds, edits, renames, or deletes", text)
        never = section("references/checks.md", "Commands the review never runs")
        for flag in ("`--fix`", "`--write`", "`--fix-dangerously`"):
            with self.subTest(flag=flag):
                self.assertIn(flag, never)

    def test_runs_the_changes_tests_only_when_the_user_says_yes(self):
        tests = section("references/checks.md", "Before running tests")
        self.assertIn("only when the user says yes", tests)
        self.assertIn("exact command", tests)
        self.assertIn("Read every changed file the tests will run", tests)
        self.assertIn("Ask once, before step 5", section("SKILL.md", "Read-only"))


class ErrorHandlingStepTest(unittest.TestCase):
    def test_reports_what_the_ticket_names(self):
        text = read("references/step-error-handling.md")
        for heading in ("Thrown values that are not errors", "Swallowed errors",
                        "Expected failures thrown instead of returned"):
            with self.subTest(heading=heading):
                self.assertIn(f"## {heading}", text)


class TypeSafetyStepTest(unittest.TestCase):
    def test_reports_what_the_ticket_names(self):
        text = read("references/step-type-safety.md")
        for heading in ("`any`", "Casts", "Non-null assertions"):
            with self.subTest(heading=heading):
                self.assertIn(f"## {heading}", text)
        self.assertIn("`as unknown as T`", text)
        self.assertIn("hide a real case", text)


GOLANG_REVIEW = SKILL.parent / "golang-review"
# The one Go-specific example in golang-review's severity meanings, and the words this skill uses in its place.
GO_EXAMPLE = "a goroutine leak that grows with use"
TS_EXAMPLE = "a leak of timers, listeners, or pending promises that grows with use"


class FindingContractTest(unittest.TestCase):
    def severities(self, path):
        text = path.read_text(encoding="utf-8")
        contract = text.split("\n## Finding contract\n", 1)[1].split("\n## ", 1)[0]
        return re.findall(r"(?m)^  - `(?:critical|major|minor)`: .*$", contract)

    def test_severities_are_copied_word_for_word_from_golang_review(self):
        go = self.severities(GOLANG_REVIEW / "SKILL.md")
        ts = self.severities(SKILL / "SKILL.md")
        self.assertEqual(len(go), 3)
        self.assertIn(GO_EXAMPLE, go[1])
        self.assertEqual(ts, [line.replace(GO_EXAMPLE, TS_EXAMPLE) for line in go])

    def test_the_report_ends_with_the_verdict(self):
        verdict = section("SKILL.md", "Verdict")
        self.assertIn("End the report with `APPROVE` or `REQUEST_CHANGES`", verdict)
        template = re.search(r"(?s)````markdown\n(.*?)````", read("references/output.md")).group(1)
        self.assertRegex(template.rstrip(), r"## Verdict\n\n(APPROVE|REQUEST_CHANGES): [^\n]+$")


class PromptsTest(unittest.TestCase):
    def test_has_the_behaviour_cases_the_ticket_names(self):
        text = read("tests/prompts.md")
        activate = text.split("\n## Should activate\n", 1)[1].split("\n## ", 1)[0]
        not_activate = text.split("\n## Should not activate\n", 1)[1].split("\n## ", 1)[0]
        for case in ("Direct:", "Indirect:", "Area only:", "No target:"):
            with self.subTest(case=case):
                self.assertIn(f"- {case} ", activate)
        self.assertRegex(not_activate, r"(?m)^- \"(Add|Write)[^\"]*\"[^\n]*typescript-practices")


class FetchSuiteToolTest(unittest.TestCase):
    """The change controls the worktree, so it can commit `.typescript-review-tools/`.

    A committed `node_modules/.bin/<tool>` would then be run, and a failed `mkdir` would send the install to the
    agent's working directory. These tests run the setup and install blocks from checks.md with a stand-in `npm` that
    only records its arguments.
    """

    def setUp(self):
        for tool in ("bash", "git"):
            if shutil.which(tool) is None:
                self.skipTest(f"{tool} is not on PATH")
        self.section = section("references/checks.md", "Fetching a suite tool", level=3)
        blocks = re.findall(r"```sh\n(.*?)```", self.section, re.S)
        self.assertEqual(len(blocks), 2, "Fetching a suite tool has a setup block and an install block")
        self.setup_block, self.install_block = blocks
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)

    def fetch(self, planted=None, untracked=None, tools=("example-tool@1.0.0",)):
        user = self.tmp / "user"
        worktree = self.tmp / "review" / "wt"
        git = ["git", "-c", "user.email=r@example.com", "-c", "user.name=r", "-c", "core.hooksPath=/dev/null",
               "-c", "commit.gpgsign=false"]
        user.mkdir()
        subprocess.run([*git, "init", "-q"], cwd=user, check=True)
        (user / "package.json").write_text('{"name": "example"}\n', encoding="utf-8")
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
        record = self.tmp / "npm-called"
        (fake / "npm").write_text(f'#!/bin/sh\nprintf "%s\\n" "$*" >> {record}\n', encoding="utf-8")
        (fake / "npm").chmod(0o755)
        env = dict(os.environ, PATH=f"{fake}{os.pathsep}{os.environ['PATH']}")

        def run(block):
            script = block.replace("<worktree>", str(worktree))
            return subprocess.run(["bash", "-c", script], cwd=user, env=env, capture_output=True).returncode

        code = run(self.setup_block)
        for tool in tools:
            if code != 0:
                break
            code = run(self.install_block.replace("<package>@<version>", tool))
        called = record.read_text(encoding="utf-8").splitlines() if record.exists() else None
        listing = sorted(p.name for p in user.iterdir())
        return code, called, listing, worktree

    def test_fetches_into_the_worktree_with_install_scripts_off(self):
        code, called, listing, worktree = self.fetch()
        self.assertEqual(code, 0)
        self.assertEqual(len(called), 1)
        args = called[0].split()
        self.assertEqual(args[0], "install")
        self.assertIn("--ignore-scripts", args)
        self.assertIn(f"--prefix={worktree / '.typescript-review-tools'}", args)
        self.assertIn("--registry=https://registry.npmjs.org/", args)
        self.assertEqual(args[-1], "example-tool@1.0.0")
        self.assertEqual(listing, [".git", "package.json"])

    def test_fetches_a_second_tool_into_the_same_directory(self):
        code, called, _, worktree = self.fetch(tools=("@biomejs/biome@2.6.9", "oxlint@1.95.0"))
        self.assertEqual(code, 0)
        self.assertEqual([c.split()[-1] for c in called], ["@biomejs/biome@2.6.9", "oxlint@1.95.0"])

    def test_refuses_a_tools_directory_the_change_commits(self):
        code, called, listing, _ = self.fetch(planted=".typescript-review-tools/node_modules/.bin/biome")
        self.assertNotEqual(code, 0)
        self.assertIsNone(called, "npm install ran")
        self.assertEqual(listing, [".git", ".typescript-review-tools", "package.json"])

    def test_refuses_a_tools_directory_already_on_disk(self):
        code, called, _, _ = self.fetch(untracked=".typescript-review-tools/node_modules")
        self.assertNotEqual(code, 0)
        self.assertIsNone(called, "npm install ran")

    def test_the_block_uses_absolute_paths_and_never_changes_directory(self):
        blocks = self.setup_block + self.install_block
        self.assertNotIn("$PWD", blocks)
        self.assertNotRegex(blocks, r"(?m)(^|&&|;)\s*cd ")
        self.assertNotIn("mkdir -p", blocks)
        self.assertIn("not run: ", self.section)


class SnapshotCopyTest(unittest.TestCase):
    """Step 4 of "The temporary worktree" copies uncommitted changes, whatever the user's diff config."""

    def setUp(self):
        for tool in ("bash", "git"):
            if shutil.which(tool) is None:
                self.skipTest(f"{tool} is not on PATH")
        found = re.search(r"(?m)^4\. For uncommitted changes.*$", section("references/target.md", "The temporary worktree"))
        self.assertIsNotNone(found)
        command = re.search(r"copy the changes in with `([^`]+)`", found.group(0))
        self.assertIsNotNone(command)
        self.command = command.group(1)
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)

    def test_copies_the_changes_whatever_the_users_diff_config(self):
        user = self.tmp / "user"
        worktree = self.tmp / "review" / "wt"
        git = ["git", "-c", "user.email=r@example.com", "-c", "user.name=r", "-c", "core.hooksPath=/dev/null",
               "-c", "commit.gpgsign=false"]
        user.mkdir()
        subprocess.run([*git, "init", "-q"], cwd=user, check=True)
        (user / "package.json").write_text('{"name": "a"}\n', encoding="utf-8")
        subprocess.run([*git, "add", "-A"], cwd=user, check=True)
        subprocess.run([*git, "commit", "-qm", "head"], cwd=user, check=True)
        subprocess.run([*git, "worktree", "add", "-q", "--detach", str(worktree), "HEAD"], cwd=user, check=True)
        subprocess.run(["git", "config", "diff.noprefix", "true"], cwd=user, check=True)
        subprocess.run(["git", "config", "color.diff", "always"], cwd=user, check=True)
        (user / "src").mkdir()
        (user / "src" / "new.ts").write_text("export const a = 1;\n", encoding="utf-8")
        subprocess.run(["git", "add", "src/new.ts"], cwd=user, check=True)
        (user / "package.json").write_text('{"name": "b"}\n', encoding="utf-8")

        script = self.command.replace("<worktree>", str(worktree))
        result = subprocess.run(["bash", "-c", script], cwd=user, capture_output=True, text=True)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((worktree / "src" / "new.ts").is_file())
        self.assertFalse((worktree / "new.ts").exists())
        self.assertIn('"b"', (worktree / "package.json").read_text(encoding="utf-8"))


class FixtureToolsSetupTest(unittest.TestCase):
    """What FixtureToolsTest relies on, checked without Node."""

    def test_the_fixture_uses_the_versions_the_install_pins(self):
        installed = json.loads((EXAMPLES / "package.json").read_text(encoding="utf-8"))["devDependencies"]
        for root in (BASE, HEAD):
            wanted = json.loads((root / "package.json").read_text(encoding="utf-8"))["devDependencies"]
            for name, version in wanted.items():
                with self.subTest(side=root.name, package=name):
                    self.assertEqual(installed.get(name), version)

    def test_the_skill_test_job_installs_node_and_pnpm(self):
        # These tests fail in CI without them, so the job that runs skill script tests must set them up.
        workflow = (REPO / ".github" / "workflows" / "validate.yml").read_text(encoding="utf-8")
        job = re.search(r"(?ms)^  validate:\n(.*?)(?=^  [\w-]+:\n|\Z)", workflow)
        self.assertIsNotNone(job, "validate.yml has no validate job")
        steps = job.group(1).split("- name: Run skill script tests", 1)[0]
        self.assertIn("uses: actions/setup-node@", steps)
        self.assertIn("uses: pnpm/action-setup@", steps)
        self.assertIn("package_json_file: plugins/company-skills/skills/typescript-practices/examples/package.json",
                      steps)


class FixtureToolsTest(unittest.TestCase):
    """The tools catch what expected-findings.md says they catch, and the probes show what no tool shows.

    The tools are installed once, with install scripts off, from typescript-practices' examples package and its
    committed lockfile, into a temporary directory that also holds copies of base/ and head/. The fixture stays
    unchanged. Without Node and pnpm these tests are skipped locally, and fail when the CI environment variable is set,
    so a CI job that forgot to install them cannot pass silently.
    """

    @classmethod
    def setUpClass(cls):
        missing = [tool for tool in ("node", "pnpm") if shutil.which(tool) is None]
        if missing:
            message = f"{' and '.join(missing)} not on PATH"
            if os.environ.get("CI"):
                raise AssertionError(f"{message}: the skill-test job must install Node and pnpm")
            raise unittest.SkipTest(message)
        cls.tmp = Path(tempfile.mkdtemp())
        try:
            for name in ("package.json", "pnpm-lock.yaml"):
                shutil.copy(EXAMPLES / name, cls.tmp / name)
            install = subprocess.run(["pnpm", "install", "--frozen-lockfile", "--ignore-scripts"], cwd=cls.tmp,
                                     capture_output=True, text=True)
            if install.returncode != 0:
                raise AssertionError(f"pnpm install failed:\n{install.stdout}\n{install.stderr}")
            for side, root in (("base", BASE), ("head", HEAD), ("probe", HEAD)):
                shutil.copytree(root, cls.tmp / side)
        except BaseException:
            shutil.rmtree(cls.tmp, ignore_errors=True)
            raise

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def tool(self, side, name, *args):
        return subprocess.run([str(self.tmp / "node_modules" / ".bin" / name), *args], cwd=self.tmp / side,
                              capture_output=True, text=True)

    def vitest(self, side):
        """Run the side's tests and return the exit code and Vitest's JSON report."""
        report = self.tmp / f"vitest-{side}.json"
        result = self.tool(side, "vitest", "run", "--reporter=json", f"--outputFile={report}")
        self.assertTrue(report.exists(), f"vitest wrote no report:\n{result.stdout}\n{result.stderr}")
        return result.returncode, json.loads(report.read_text(encoding="utf-8"))

    def oxlint(self, side):
        return self.tool(side, "oxlint", "--type-aware", "-c", str(OXLINT_CONFIG), "--format=unix", "src")

    def test_tsc_passes_at_the_base_and_the_head(self):
        for side in ("base", "head"):
            with self.subTest(side=side):
                result = self.tool(side, "tsc", "--noEmit", "-p", "tsconfig.json")
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_type_aware_oxlint_reports_only_the_thrown_string(self):
        base = self.oxlint("base")
        self.assertEqual(base.returncode, 0, base.stdout + base.stderr)
        head = self.oxlint("head")
        self.assertNotEqual(head.returncode, 0, head.stdout + head.stderr)
        diagnostics = [line for line in head.stdout.splitlines() if re.match(r"^src/[^:]+:\d+:\d+:", line)]
        self.assertEqual(len(diagnostics), 1, head.stdout)
        t1 = finding("Error handling")
        self.assertTrue(diagnostics[0].startswith(f"{t1['path']}:{t1['line']}:"), diagnostics[0])
        self.assertIn("only-throw-error", diagnostics[0])

    def test_the_tests_pass_at_the_head_and_show_neither_defect(self):
        code, report = self.vitest("head")
        self.assertEqual(code, 0, report)
        self.assertEqual((report["numPassedTests"], report["numTotalTests"]), (7, 7))

    def test_probes_show_what_no_tool_shows(self):
        # T1: the caller loses the reason for a missing id. T2: an untracked parcel crashes the label.
        probe = self.tmp / "probe" / "src" / "probe.test.ts"
        probe.write_text(
            'import { expect, test } from "vitest";\n'
            'import { labelText } from "./labels.js";\n'
            'import { weightLine } from "./manifest.js";\n'
            "\n"
            'test("a missing id loses its reason", () => {\n'
            '  expect(weightLine([{ id: "P-1", weightGrams: 750 }], "P-9")).toBe("P-9: something went wrong");\n'
            "});\n"
            "\n"
            'test("an untracked parcel throws a TypeError", () => {\n'
            '  const label = () => labelText({ id: "P-1", weightGrams: 750 });\n'
            "  expect(label).toThrow(TypeError);\n"
            "  expect(label).toThrow(\"Cannot read properties of undefined (reading 'toUpperCase')\");\n"
            "});\n",
            encoding="utf-8",
        )
        code, report = self.vitest("probe")
        self.assertEqual(code, 0, json.dumps(report, indent=1)[:4000])
        probes = [t for f in report["testResults"] if f["name"].endswith("probe.test.ts") for t in f["assertionResults"]]
        self.assertEqual([t["status"] for t in probes], ["passed", "passed"])
