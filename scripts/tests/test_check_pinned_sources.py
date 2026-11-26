"""Offline tests for the pinned and vendored plugin source check."""

import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest


REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))
spec = importlib.util.spec_from_file_location("check_pinned_sources", REPO / "scripts/check_pinned_sources.py")
check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check)


def write(root, files):
    for name, text in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)


class VendoredDifferencesTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.local = Path(temp.name) / "local"
        self.upstream = Path(temp.name) / "upstream"
        write(self.upstream, {
            ".claude-plugin/plugin.json": "{}",
            "skills/a/SKILL.md": "a",
            "tests/fixtures/x/.claude-plugin/plugin.json": "{}",
            "evals/case.yaml": "e",
        })
        write(self.local, {".claude-plugin/plugin.json": "{}", "skills/a/SKILL.md": "a", "UPSTREAM.md": "u"})

    def differences(self):
        return check.vendored_differences(self.local, self.upstream, ("tests", "evals"), ("UPSTREAM.md",))

    def test_matching_copy_passes(self):
        self.assertEqual(self.differences(), [])

    def test_changed_missing_and_extra_files_are_reported(self):
        (self.local / "skills/a/SKILL.md").write_text("changed")
        write(self.local, {"extra.md": "x"})
        write(self.upstream, {"skills/b/SKILL.md": "b"})
        self.assertEqual(
            self.differences(),
            ["extra.md is not upstream", "skills/b/SKILL.md is missing", "skills/a/SKILL.md differs"],
        )

    def test_left_out_folder_only_matches_at_the_top(self):
        write(self.upstream, {"skills/a/tests/case.md": "t"})
        self.assertEqual(self.differences(), ["skills/a/tests/case.md is missing"])


class VendoredRecordTests(unittest.TestCase):
    def test_upstream_md_names_the_recorded_commit(self):
        for folder, (_, _, sha, _, added) in check.VENDORED.items():
            with self.subTest(folder=folder):
                self.assertIn("UPSTREAM.md", added)
                self.assertIn(sha, (REPO / folder / "UPSTREAM.md").read_text())

    def test_vendored_copy_holds_no_nested_manifest(self):
        for folder in check.VENDORED:
            with self.subTest(folder=folder):
                self.assertEqual(check.nested_manifests(REPO / folder), [])


if __name__ == "__main__":
    unittest.main()
