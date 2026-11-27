# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Count the lines on standard input. Run it with: uv run count_lines.py < file."""

import sys
from typing import TextIO


def count(stream: TextIO) -> int:
    return sum(1 for _ in stream)


if __name__ == "__main__":
    print(count(sys.stdin))
