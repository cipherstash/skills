#!/usr/bin/env python3
"""Map changed file paths to the review skills a change needs.

Reads one changed path per line on stdin and prints a JSON review plan.
"""

from __future__ import annotations

import json
import sys


def main() -> int:
    paths = [line.strip() for line in sys.stdin if line.strip()]
    plan = []
    if any(p.endswith(".go") for p in paths):
        plan.append({"skill": "review-golang", "reason": "Go files changed"})
    json.dump({"plan": plan}, sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
