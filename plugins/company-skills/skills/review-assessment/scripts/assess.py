#!/usr/bin/env python3
"""Map changed file paths to the review skills a change needs.

Reads one changed path per line on stdin and prints a JSON review plan.
"""

from __future__ import annotations

import json
import sys
from fnmatch import fnmatchcase

# (skill, reason, patterns). Order is the plan's row order. A pattern with a
# "/" matches the whole path; any other pattern matches the file name.
RULES = [
    ("review-golang", "Go code or module files changed", ["*.go", "go.mod", "go.sum"]),
    ("review-rust", "Rust code or Cargo files changed", ["*.rs", "Cargo.toml", "Cargo.lock"]),
    (
        "rust-security",
        "Every Rust change gets a secret-handling and cryptography pass",
        ["*.rs", "Cargo.toml", "Cargo.lock"],
    ),
    (
        "review-typescript",
        "TypeScript or JavaScript code or package files changed",
        [
            "*.ts",
            "*.tsx",
            "*.mts",
            "*.cts",
            "*.js",
            "*.jsx",
            "*.mjs",
            "*.cjs",
            "package.json",
            "tsconfig*.json",
            "package-lock.json",
            "pnpm-lock.yaml",
            "yarn.lock",
        ],
    ),
    (
        "review-python",
        "Python code or packaging files changed",
        ["*.py", "*.pyi", "pyproject.toml", "setup.py", "setup.cfg", "requirements*.txt", "uv.lock", "poetry.lock"],
    ),
    (
        "review-infracode",
        "CI workflows, container builds, or Terraform changed",
        [
            ".github/workflows/*.yml",
            ".github/workflows/*.yaml",
            "Dockerfile",
            "Dockerfile.*",
            "*.dockerfile",
            "*.tf",
            "*.tfvars",
            ".terraform.lock.hcl",
        ],
    ),
]

CODE = ["*.go", "*.rs", "*.ts", "*.tsx", "*.mts", "*.cts", "*.js", "*.jsx", "*.mjs", "*.cjs", "*.py"]
TEST_NAMES = ["*_test.go", "test_*.py", "*_test.py", "conftest.py", "*.test.*", "*.spec.*", "*_test.rs"]
TEST_DIRS = {"test", "tests", "__tests__", "spec"}
TEST_GAPS_REASON = "Code changed with no test file changed"


def is_test(path: str) -> bool:
    return matches(path, TEST_NAMES) or bool(TEST_DIRS.intersection(path.split("/")[:-1]))


def matches(path: str, patterns: list[str]) -> bool:
    name = path.rsplit("/", 1)[-1]
    return any(fnmatchcase(path if "/" in pattern else name, pattern) for pattern in patterns)


def main() -> int:
    paths = sorted({line.strip() for line in sys.stdin if line.strip()})
    if not paths:
        sys.stderr.write("assess.py: no changed files on stdin; refusing to print an empty plan\n")
        return 2
    plan = []
    for skill, reason, patterns in RULES:
        if any(matches(p, patterns) for p in paths):
            plan.append({"skill": skill, "reason": reason})
    code = [p for p in paths if matches(p, CODE)]
    if code and not any(is_test(p) for p in code):
        plan.append({"skill": "review-test-gaps", "reason": TEST_GAPS_REASON})
    unmatched = [p for p in paths if not any(matches(p, patterns) for _, _, patterns in RULES)]
    sys.stdout.write(json.dumps({"plan": plan, "unmatched": unmatched}, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
