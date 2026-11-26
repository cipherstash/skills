"""Shared helper for each language's check suite drift test.

A language's `checks.md` lists its suite's tools in a `## Pinned versions` table with the columns Tool, Version and
Package. Its drift test checks that the suite's CI job keeps each check in place. The rule, which issue #126 adds to
GLOSSARY.md as the term **In place**:

    A check is in place when it is a GitHub Actions step that runs on `pull_request`, blocks when it fails, covers
    every module except fixtures with planted defects, and pins its version. Nothing may ignore its exit status: no
    `continue-on-error`, no `|| true`, and no `continue-on-error` step that a later step enforces. [...] A version is
    pinned when it is exact, or fixed by a committed lockfile that CI installs frozen or locked.

This helper checks the trigger, the blocking and the pin. Coverage is each language's own test to check.
"""

from collections import namedtuple
import os
from pathlib import Path, PurePosixPath
import re

import yaml


REPO = Path(__file__).resolve().parents[2]

Pin =namedtuple("Pin", "version package")

ROW = re.compile(r"\| *`?([\w.@/-]+)`? *\| *`([^`]+)` *\| *(.*?) *\|")
SEPARATOR = re.compile(r"\|( *:?-+:? *\|)+")


def read_pins(checks_md):
    """Return {tool: Pin(version, package)} from the pinned versions table in the checks.md at checks_md.

    The package is the first code span in the Package column, or the whole column when it has none. Raises ValueError
    when the section has no table rows, or holds a table line that is neither a header, a separator nor a row it can
    read, since a skipped row would leave that tool's pin unchecked.
    """
    text = checks_md.read_text(encoding="utf-8")
    if "## Pinned versions" not in text:
        raise ValueError(f"{checks_md} has no ## Pinned versions section")
    section = text.split("## Pinned versions", 1)[1].split("\n## ", 1)[0]
    lines = [line.strip() for line in section.splitlines()]
    pins = {}
    for index, line in enumerate(lines):
        if not line.startswith("|") or SEPARATOR.fullmatch(line):
            continue
        if index + 1 < len(lines) and SEPARATOR.fullmatch(lines[index + 1]):
            continue  # The header row.
        row = ROW.fullmatch(line)
        if not row:
            raise ValueError(f"{checks_md} has a pinned versions table line it cannot read: {line}")
        tool, version, package = row.groups()
        span = re.search(r"`([^`]+)`", package)
        pins[tool] = Pin(version, span.group(1) if span else package)
    if not pins:
        raise ValueError(f"{checks_md} has no rows in its pinned versions table")
    return pins


def triggers(workflow):
    """Return the workflow's triggers as {event: filters}, from any of the forms `on` takes."""
    # PyYAML reads the bare key `on` as the boolean true.
    on = workflow.get("on", workflow.get(True)) or {}
    if isinstance(on, str):
        return {on: None}
    if isinstance(on, list):
        return dict.fromkeys(on)
    return on


def trigger_problems(workflow, job_name):
    """Return why some pull requests would skip the job named job_name, or [] when every one runs it."""
    problems = []
    on = triggers(workflow)
    if "pull_request" not in on:
        problems.append("the workflow does not run on pull_request")
    elif on["pull_request"]:
        # A branch or path filter would let some pull requests skip the suite.
        problems.append(f"the pull_request trigger has a filter: {on['pull_request']}")
    if "if" in workflow["jobs"][job_name]:
        problems.append(f"job {job_name} runs only if {workflow['jobs'][job_name]['if']}")
    return problems


def step_label(step):
    return step.get("name") or step.get("uses") or step.get("run")


def exit_problems(workflow, job_name):
    """Return each way a check in the job named job_name could fail without failing the job, or [] when none can."""
    job = workflow["jobs"][job_name]
    problems = []
    if "continue-on-error" in job:
        problems.append(f"job {job_name} sets continue-on-error")
    # A shell set without -e, such as `bash {0}`, would let a failing line pass if a later line passes.
    for owner, keys in (("the workflow", workflow), (f"job {job_name}", job)):
        if "shell" in keys.get("defaults", {}).get("run", {}):
            problems.append(f"{owner} sets a default shell")
    for step in job["steps"]:
        label = step_label(step)
        for key in ("continue-on-error", "if", "shell"):
            if key in step:
                problems.append(f"step {label!r} sets {key}")
        for line in shell_lines(step.get("run", "")):
            if ignores_exit_status(line):
                problems.append(f"step {label!r} ignores an exit status: {line}")
    return problems


def shell_lines(script):
    """Yield each command line of a run script, joining lines a trailing `\\`, `||` or `&&` continues."""
    script = re.sub(r"\\\n|(?<=\|\|)[ \t]*\n|(?<=&&)[ \t]*\n", " ", script)
    for line in script.splitlines():
        if line.strip():
            yield re.sub(r"\s+", " ", line).strip()


# The start of a command: the line's start, or after a separator such as `;`, `&&` or `(`.
COMMAND_START = r"(?:^|[;&|({]\s*|\b(?:then|else|do)\s+)"
# A command that fails: `exit` or `return` with no status, a non-zero one or the failed command's `$?`, or `false`.
FAILS = re.compile(r"(exit|return)(\s+(0*[1-9]\d*|\$\?))?|false")


def ignores_exit_status(line):
    """Report whether a shell line turns off errexit, negates a command, or follows `||` with a command that succeeds.

    Under `bash -e`, which GitHub Actions uses by default, a failing command fails the step unless something like
    these masks its exit status. Quoted text is blanked first, so a `||` or `!` inside a string is not read as syntax.
    """
    line = re.sub(r"'[^']*'|\"(?:[^\"\\]|\\.)*\"", "''", line)
    if re.search(COMMAND_START + r"set\s+(\+e\b|\+o\s+errexit\b)", line):
        return True
    if re.search(COMMAND_START + r"!\s", line):
        return True
    for fallback in re.split(r"\|\|", line)[1:]:
        fallback = fallback.strip()
        if fallback.startswith(("{", "(")):
            # A group fails when its last command does.
            close = "}" if fallback[0] == "{" else ")"
            body = fallback[1:].split(close, 1)[0]
            commands = [command.strip() for command in body.split(";") if command.strip()]
            last = commands[-1] if commands else ""
        else:
            last = re.split(r"\s*(?:;|&&|\|)\s*", fallback, maxsplit=1)[0]
        if not FAILS.fullmatch(last.strip()):
            return True
    return False


def strings_in(value):
    """Yield every string in a step, keys and values, as YAML loaded it."""
    if isinstance(value, dict):
        for key, item in value.items():
            yield str(key)
            yield from strings_in(item)
    elif isinstance(value, list):
        for item in value:
            yield from strings_in(item)
    elif value is not None:
        yield str(value)


def names_version(text, version):
    """Report whether text holds version whole, not as part of a longer version such as v1.10.0-rc.1."""
    return re.search(rf"(?<![\w.-]){re.escape(version)}(?![\w.-])", text) is not None


# An install that fails rather than change the lockfile, such as `uv sync --locked`, `cargo build --locked`,
# `pnpm install --frozen-lockfile`, `yarn install --immutable` or `npm ci`.
FROZEN_INSTALL = re.compile(r"(?<![\w-])--(frozen|frozen-lockfile|locked|immutable)(?![\w-])|(^|[;&|]\s*)npm ci(?![\w-])")


def run_lines(workflow, job_name):
    """Yield (working directory, line) for each command line of each run step of the job named job_name.

    A step's working directory is its own `working-directory`, else the job's default, else the workflow's, else `.`.
    """
    job = workflow["jobs"][job_name]
    default = "."
    for owner in (workflow, job):
        default = (owner.get("defaults") or {}).get("run", {}).get("working-directory", default)
    for step in job["steps"]:
        for line in shell_lines(step.get("run", "")):
            yield step.get("working-directory", default), line


def lock_entries(lines, package):
    """Yield the version each of package's own entries in a lockfile's lines records.

    An entry is a line that is all of `name = "<package>"`, as in Cargo.lock, uv.lock and poetry.lock; a key ending in
    `node_modules/<package>`, as in package-lock.json; or a key `<package>@<spec>`, as in pnpm-lock.yaml and yarn.lock.
    Its version is the first `version` key in the entry, or for a `<package>@<spec>` key with none, the spec. A line
    that only mentions the package, such as a requirement or a dependency list, is not an entry.
    """
    quoted = re.escape(package)
    toml = re.compile(rf"name = \"{quoted}\"")
    npm = re.compile(rf"\"(?:[^\"]*/)?node_modules/{quoted}\": \{{")
    at = re.compile(rf"['\"]?/?{quoted}@(?:npm:)?([^\s'\"(:,]+)[^:]*['\"]?:")
    version_key = re.compile(r"\"?version\"?\s*[:=]?\s*['\"]?([^\s'\",]+)['\"]?,?")
    for index, line in enumerate(lines):
        stripped = line.strip()
        indent = len(line) - len(line.lstrip())
        if toml.fullmatch(stripped):
            # A TOML table runs to the next blank line or table header.
            ends = lambda other: not other.strip() or other.lstrip().startswith("[")
        elif npm.fullmatch(stripped):
            ends = lambda other: other.strip().startswith("}") and len(other) - len(other.lstrip()) <= indent
        elif at.fullmatch(stripped):
            ends = lambda other: other.strip() and len(other) - len(other.lstrip()) <= indent
        else:
            continue
        found = None
        for other in lines[index + 1 :]:
            if ends(other):
                break
            match = version_key.fullmatch(other.strip())
            if match:
                found = match.group(1)
                break
        if found is None and at.fullmatch(stripped):
            found = at.fullmatch(stripped).group(1)
        if found is not None:
            yield found


def locks_version(lockfile, package, version):
    """Report whether lockfile fixes package at version, in the version of one of package's own entries."""
    lines = lockfile.read_text(encoding="utf-8").splitlines()
    return version in lock_entries(lines, package)


def lockfile_problems(workflow, job_name, tool, pin, root, lockfile):
    """Return why the lockfile at root/lockfile does not pin tool, or [] when it does."""
    path = root / lockfile
    if not path.is_file():
        return [f"{tool}'s lockfile {lockfile} is not in the repository"]
    problems = []
    if not locks_version(path, pin.package, pin.version):
        problems.append(f"{lockfile} does not fix {pin.package} at {pin.version}")
    directory = PurePosixPath(lockfile).parent
    if not any(
        PurePosixPath(os.path.normpath(cwd)) == directory and FROZEN_INSTALL.search(line)
        for cwd, line in run_lines(workflow, job_name)
    ):
        problems.append(f"no step in job {job_name} installs {lockfile} frozen or locked in {directory}")
    return problems


# The step keys that say what a step runs or installs. A step's `name` and `id` only label it.
INSTALLS = ("run", "uses", "with", "env")


def pin_problems(workflow, job_name, pins, root=None, lockfiles=None):
    """Return each tool in pins that the job named job_name does not pin at its version, or [] when all are.

    A step pins a tool when what it runs or installs, its `run`, `uses`, `with` and `env`, names the tool or its package
    and holds the tool's version whole; its `name` is a label and counts for neither. A tool in lockfiles,
    {tool: lockfile path relative to root}, is pinned instead when that lockfile fixes its package at its version and a
    step in the lockfile's directory installs it frozen or locked.
    """
    lockfiles = lockfiles or {}
    problems = []
    steps = [
        "\n".join(strings_in([step.get(key) for key in INSTALLS]))
        for step in workflow["jobs"][job_name]["steps"]
    ]
    for tool, pin in pins.items():
        if tool in lockfiles:
            problems += lockfile_problems(workflow, job_name, tool, pin, Path(root), lockfiles[tool])
        elif not any((tool in text or pin.package in text) and names_version(text, pin.version) for text in steps):
            problems.append(f"no step in job {job_name} pins {tool} at {pin.version}")
    return problems


class DriftTests:
    """Checks that a language's check suite job keeps each check in place, against its checks.md.

    Mix it into a unittest.TestCase and set CHECKS, the path of the language's checks.md, and JOB, the name of its suite
    job in WORKFLOW. Set LOCKFILES, {tool: lockfile path relative to ROOT}, for each tool pinned through a lockfile.
    """

    WORKFLOW = REPO / ".github/workflows/validate.yml"
    ROOT = REPO
    LOCKFILES = {}

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.workflow = yaml.safe_load(Path(cls.WORKFLOW).read_text(encoding="utf-8"))
        cls.pins = read_pins(Path(cls.CHECKS))

    def test_runs_on_every_pull_request(self):
        self.assertEqual(trigger_problems(self.workflow, self.JOB), [])

    def test_no_check_may_fail_without_failing_the_job(self):
        self.assertEqual(exit_problems(self.workflow, self.JOB), [])

    def test_pins_each_tool_at_its_pinned_version(self):
        self.assertEqual(
            pin_problems(self.workflow, self.JOB, self.pins, root=self.ROOT, lockfiles=self.LOCKFILES), []
        )
