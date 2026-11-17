#!/usr/bin/env python3
"""Map changed file paths to the review skills a change needs.

Reads one changed path per line on stdin and prints a JSON review plan.
"""

from __future__ import annotations

import json
import sys
from fnmatch import fnmatchcase

# (skill, reason, basename patterns). Order is the plan's row order.
RULES = [
    ("review-golang", "Go code or module files changed", ["*.go", "go.mod", "go.sum"]),
    ("review-rust", "Rust code or Cargo files changed", ["*.rs", "Cargo.toml", "Cargo.lock"]),
    (
        "rust-security",
        "Every Rust change gets a secret-handling and cryptography pass",
        ["*.rs", "Cargo.toml", "Cargo.lock"],
    ),
]


def matches(path: str, patterns: list[str]) -> bool:
    name = path.rsplit("/", 1)[-1]
    return any(fnmatchcase(name, pattern) for pattern in patterns)


def main() -> int:
    paths = [line.strip() for line in sys.stdin if line.strip()]
    plan = []
    for skill, reason, patterns in RULES:
        if any(matches(p, patterns) for p in paths):
            plan.append({"skill": skill, "reason": reason})
    json.dump({"plan": plan}, sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
