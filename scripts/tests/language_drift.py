"""Shared helper for each language's check suite drift test.

A language's `checks.md` lists its suite's tools in a `## Pinned versions` table with the columns Tool, Version and
Package. Its drift test checks that the suite's CI job keeps each check in place, as GLOSSARY.md's **In place** says.
"""

from collections import namedtuple
import os
from pathlib import Path, PurePosixPath
import re

import yaml


REPO = Path(__file__).resolve().parents[2]

Pin =namedtuple("Pin", "version package")

ROW = re.compile(r"^\| *`?([\w.@/-]+)`? *\| *`([^`]+)` *\| *(.*?) *\|$", re.MULTILINE)


def read_pins(checks_md):
    """Return {tool: Pin(version, package)} from the pinned versions table in the checks.md at checks_md.

    The package is the first code span in the Package column, or the whole column when it has none.
    """
    text = checks_md.read_text(encoding="utf-8")
    if "## Pinned versions" not in text:
        raise ValueError(f"{checks_md} has no ## Pinned versions section")
    section = text.split("## Pinned versions", 1)[1].split("\n## ", 1)[0]
    pins = {}
    for tool, version, package in ROW.findall(section):
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
        for line in step.get("run", "").splitlines():
            if re.search(r"\|\|\s*(true|:)(?![\w-])", line):
                problems.append(f"step {label!r} ignores an exit status: {line.strip()}")
    return problems


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
    """Yield (working directory, line) for each line of each run step of the job named job_name."""
    job = workflow["jobs"][job_name]
    default = job.get("defaults", {}).get("run", {}).get("working-directory", ".")
    for step in job["steps"]:
        for line in step.get("run", "").splitlines():
            if line.strip():
                yield step.get("working-directory", default), re.sub(r"\s+", " ", line).strip()


def locks_version(lockfile, package, version):
    """Report whether lockfile fixes package at version: on the line that names the package, or the line after it.

    That covers the common lockfile layouts, such as Cargo.lock's and uv.lock's `name` then `version` lines,
    package-lock.json's `"node_modules/<package>": {` then `"version"`, and pnpm-lock.yaml's `<package>@<version>`.
    """
    lines = lockfile.read_text(encoding="utf-8").splitlines()
    name = re.compile(rf"(?<![\w.-]){re.escape(package)}(?![\w.-])")
    return any(
        name.search(line) and names_version("\n".join(lines[index : index + 2]), version)
        for index, line in enumerate(lines)
    )


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


def pin_problems(workflow, job_name, pins, root=None, lockfiles=None):
    """Return each tool in pins that the job named job_name does not pin at its version, or [] when all are.

    A step pins a tool when it names the tool or its package, and holds the tool's version whole. A tool in lockfiles,
    {tool: lockfile path relative to root}, is pinned instead when that lockfile fixes its package at its version and a
    step in the lockfile's directory installs it frozen or locked.
    """
    lockfiles = lockfiles or {}
    problems = []
    steps = ["\n".join(strings_in(step)) for step in workflow["jobs"][job_name]["steps"]]
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
