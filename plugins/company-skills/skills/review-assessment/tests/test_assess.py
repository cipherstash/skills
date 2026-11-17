"""Tests for scripts/assess.py, driven through its command line.

Run: python3 -m unittest discover -s <skill>/tests
"""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "assess.py"


def run(paths: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        input="".join(p + "\n" for p in paths),
        capture_output=True,
        text=True,
        check=False,
    )


def plan(paths: list[str]) -> dict:
    proc = run(paths)
    if proc.returncode != 0:
        raise AssertionError(f"exit {proc.returncode}: {proc.stderr}")
    return json.loads(proc.stdout)


def skills(result: dict) -> list[str]:
    return [row["skill"] for row in result["plan"]]


class AssessTest(unittest.TestCase):
    def test_go_change_selects_review_golang(self) -> None:
        result = plan(["cmd/server/main.go", "cmd/server/main_test.go"])
        self.assertEqual(skills(result), ["review-golang"])
        self.assertTrue(result["plan"][0]["reason"])

    def test_rust_change_selects_review_rust_and_rust_security(self) -> None:
        result = plan(["Cargo.toml", "src/lib.rs", "tests/lib_test.rs"])
        self.assertEqual(skills(result), ["review-rust", "rust-security"])

    def test_typescript_and_javascript_changes_select_review_typescript(self) -> None:
        for path in ["src/app.ts", "src/view.tsx", "lib/index.js", "lib/esm.mjs", "lib/cjs.cjs", "src/x.jsx"]:
            with self.subTest(path=path):
                result = plan([path, "test/app.test.ts"])
                self.assertEqual(skills(result), ["review-typescript"])


if __name__ == "__main__":
    unittest.main()
