"""Tests for the examples that project-structure.md and dependencies.md quote."""

import io
import re
import tomllib
from importlib.metadata import entry_points
from pathlib import Path

import pytest

from practices import about, count_lines

# The reference regular expression from PEP 723, for a script metadata block.
PEP_723 = re.compile(
    r"(?m)^# /// (?P<type>[a-zA-Z0-9-]+)$\s(?P<content>(^#(| .*)$\s)+)^# ///$"
)


def test_the_version_comes_from_the_installed_metadata() -> None:
    assert about.package_version() == "0.1.0"


def test_the_console_script_runs_main(capsys: pytest.CaptureFixture[str]) -> None:
    (script,) = entry_points(group="console_scripts", name="practices-version")
    script.load()()
    assert capsys.readouterr().out == "practices 0.1.0\n"


def test_the_script_header_is_pep_723_metadata() -> None:
    source = Path(count_lines.__file__).read_text(encoding="utf-8")
    (block,) = PEP_723.finditer(source)
    assert block["type"] == "script"
    content = "".join(
        line[2:] if line.startswith("# ") else line[1:]
        for line in block["content"].splitlines(keepends=True)
    )
    metadata = tomllib.loads(content)
    assert metadata == {"requires-python": ">=3.12", "dependencies": []}


def test_the_script_counts_lines() -> None:
    assert count_lines.count(io.StringIO("a\nb\nc\n")) == 3
