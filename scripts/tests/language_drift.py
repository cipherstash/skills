"""Shared helper for each language's check suite drift test.

A language's `checks.md` lists its suite's tools in a `## Pinned versions` table with the columns Tool, Version and
Package. Its drift test checks that the suite's CI job keeps each check in place. The rule is the GLOSSARY.md term
**In place**, which issue #126 asks for and pull request #133 adds. It is not on main until #133 merges, so here it is
as #133 words it:

    A check is in place when it is a GitHub Actions step that runs on `pull_request`, blocks when it fails, covers
    every module except fixtures with planted defects, and pins its version. Nothing may ignore its exit status: no
    `continue-on-error`, even when a later step enforces its result; no `|| true`; and no other way, such as a shell
    without `-e` or a pipe without `pipefail`. A path-filtered trigger counts only alongside a changes job that fails
    closed. A version is pinned when it is exact, or fixed by a committed lockfile that CI installs frozen or locked.
    The language runtime floats.

This helper checks the trigger, the blocking and the pin. Coverage is each language's own test to check. The helper is
stricter than the rule on triggers: it cannot tell whether a changes job fails closed, so it fails any filtered
`pull_request` trigger, and any suite job that `needs` another job. It is stricter on lockfiles too: it cannot tell
which of a package's versions the suite runs, so it fails a lockfile that holds the package at more than one.
"""

from collections import namedtuple
import os
from pathlib import Path, PurePosixPath
import re
import shlex

import yaml


REPO = Path(__file__).resolve().parents[2]

Pin = namedtuple("Pin", "version package")

ROW = re.compile(r"\| *`?([\w.@/-]+)`? *\| *`([^`]+)` *\| *(.*?) *\|")
SEPARATOR = re.compile(r"\|( *:?-+:? *\|)+")


def read_pins(checks_md):
    """Return {tool: Pin(version, package)} from the pinned versions table in the checks.md at checks_md.

    The package is the first code span in the Package column, or the whole column when it has none. Raises ValueError
    when the section has no table rows, holds a table line that is neither a header, a separator nor a row it can
    read, gives a tool no package, or lists a tool twice, since each would leave a tool's pin unchecked.
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
        package = span.group(1) if span else package
        if not package:
            # An empty package would match every step.
            raise ValueError(f"{checks_md} gives {tool} no package")
        if tool in pins:
            raise ValueError(f"{checks_md} lists {tool} twice")
        pins[tool] = Pin(version, package)
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
        # A branch or path filter would let some pull requests skip the suite. In place allows a path filter beside a
        # changes job that fails closed, which this helper cannot check, so it fails every filter.
        problems.append(f"the pull_request trigger has a filter: {on['pull_request']}")
    job = workflow["jobs"][job_name]
    if "if" in job:
        problems.append(f"job {job_name} runs only if {job['if']}")
    if job.get("needs"):
        # A job is skipped when a job it needs is skipped or fails, and GitHub reports a skipped required job as
        # passing. Whether each needed job runs and passes on every pull request is more than this helper can check.
        problems.append(f"job {job_name} needs {job['needs']}, so it is skipped when that job is skipped or fails")
    return problems


def step_label(step):
    return step.get("name") or step.get("uses") or step.get("run")


def run_defaults(owner):
    """Return the `defaults.run` of a workflow or job, {} when it sets none or YAML left it empty."""
    return (owner.get("defaults") or {}).get("run") or {}


def exit_problems(workflow, job_name):
    """Return each way this helper finds that a check in the job named job_name could fail without failing the job.

    Returns [] when it finds none. A step's script runs under `bash -e`, GitHub Actions' default shell when a step sets
    none; ignores_exit_status lists what it looks for in each line.
    """
    job = workflow["jobs"][job_name]
    problems = []
    if "continue-on-error" in job:
        problems.append(f"job {job_name} sets continue-on-error")
    # A shell set without -e, such as `bash {0}`, would let a failing line pass if a later line passes.
    for owner, keys in (("the workflow", workflow), (f"job {job_name}", job)):
        if "shell" in run_defaults(keys):
            problems.append(f"{owner} sets a default shell")
    for step in job["steps"]:
        label = step_label(step)
        for key in ("continue-on-error", "if", "shell"):
            if key in step:
                problems.append(f"step {label!r} sets {key}")
        lines = list(shell_lines(step.get("run") or ""))
        pipefail = False
        for index, line in enumerate(lines):
            pipefail = sets_pipefail(line, pipefail)
            if ignores_exit_status(line, last=index == len(lines) - 1, pipefail=pipefail):
                problems.append(f"step {label!r} ignores an exit status: {line}")
    return problems


QUOTED = re.compile(r"'[^']*'|\"(?:[^\"\\]|\\.)*\"")
# A `#` that starts a word starts a comment, unless it is quoted.
COMMENT = re.compile(r"'[^']*'|\"(?:[^\"\\]|\\.)*\"|(?:^|(?<=[\s;&|()]))#.*")


def blank_quotes(line):
    """Return line with each quoted string emptied, so that its text is not read as shell syntax."""
    return QUOTED.sub("''", line)


def strip_comment(line):
    return COMMENT.sub(lambda match: "" if match.group(0).startswith("#") else match.group(0), line)


def continues(text):
    """Report whether shell text goes on to the next line: it ends in an operator, or leaves a group or block open."""
    text = blank_quotes(text)
    if re.search(r"(\|\|?|&&)\s*$", text):
        return True
    depth = text.count("{") + text.count("(") - text.count("}") - text.count(")")
    words = re.findall(r"(?<![\w./$-])(if|fi|do|done|case|esac)(?![\w./-])", text)
    pairs = (("if", "fi"), ("do", "done"), ("case", "esac"))
    blocks = sum(words.count(start) - words.count(end) for start, end in pairs)
    return depth > 0 or blocks > 0


def shell_lines(script):
    """Yield each command line of a run script, with comments removed and continued lines joined.

    A line goes on to the next when it ends in `\\`, `|`, `||` or `&&`, or leaves a `{` or `(` group, an `if`, a loop
    or a `case` open. Joined lines are separated by `; `, as a newline separates commands, except after an operator,
    an opening brace or parenthesis, `then`, `else` or `do`.
    """
    script = re.sub(r"\\\n", " ", script)
    joined = ""
    for raw in script.splitlines():
        line = strip_comment(raw).strip()
        if not line:
            continue
        if not joined:
            joined = line
        elif re.search(r"(\|\|?|&&|[{(]|\b(?:then|else|do))$", joined):
            joined += " " + line
        else:
            joined += "; " + line
        if not continues(joined):
            yield re.sub(r"\s+", " ", joined).strip()
            joined = ""
    if joined:
        yield re.sub(r"\s+", " ", joined).strip()


# The start of a command: the line's start, or after a separator such as `;`, `&&` or `(`.
COMMAND_START = r"(?:^|[;&|({]\s*|\b(?:then|else|do)\s+)"
# A command that fails: `exit` or `return` with no status, a non-zero one or the failed command's `$?`, or `false`.
FAILS = re.compile(r"(exit|return)(\s+(0*[1-9]\d*|\$\?))?|false")
# A command whose failure is a result rather than an error: a test, `read`, `true`, `false` or `:`.
TEST = re.compile(r"(?:!\s*)?(?:\[\[?|test|read|true|false|:)(?:\s|$)")
CONDITION = re.compile(COMMAND_START + r"(if|elif|while|until)\s+(.*?)\s*;\s*(?:then|do)\b")


def sets_pipefail(line, pipefail):
    """Return whether pipefail is on after line, given whether it was on before."""
    for command in re.finditer(COMMAND_START + r"set\s+([^;&|]*)", blank_quotes(line)):
        for flag in re.finditer(r"([-+])[a-zA-Z]*o\s+pipefail\b", command.group(1)):
            pipefail = flag.group(1) == "-"
    return pipefail


def turns_off_errexit(line):
    """Report whether line runs a `set` that turns errexit off: `+e` alone or among other options, or `+o errexit`."""
    for command in re.finditer(COMMAND_START + r"set\s+([^;&|]*)", line):
        words = command.group(1).split()
        index = 0
        while index < len(words):
            option = re.fullmatch(r"([-+])([a-zA-Z]+)", words[index])
            if not option:
                break  # `--`, or the positional arguments that follow the options.
            sign, letters = option.groups()
            if sign == "+" and "e" in letters:
                return True
            if "o" in letters:
                index += 1  # The option's operand, such as errexit or pipefail.
                if sign == "+" and index < len(words) and words[index] == "errexit":
                    return True
            index += 1
    return False


def is_test(command):
    return TEST.match(command.strip()) is not None


def last_command(body):
    return re.split(r"\s*;\s*", body.strip())[-1].strip()


def masks_condition(line):
    """Report whether line runs a command other than a test as an `if`, `while` or `until` condition.

    A failing condition takes the other branch or ends the loop, so it fails nothing, unless the branch its failure
    takes fails: `if ! check; then exit 1; fi`, or `if check; then ...; else exit 1; fi`.
    """
    for match in CONDITION.finditer(line):
        keyword, condition = match.groups()
        if all(is_test(command) for command in re.split(r"\s*(?:&&|\|\||\|)\s*", condition)):
            continue
        if keyword not in ("if", "elif"):
            return True
        branches = re.match(r"\s*(.*?)\s*;\s*(elif|else|fi)\b(.*)", line[match.end() :])
        if not branches:
            return True
        then, after, rest = branches.groups()
        if condition.startswith("!"):
            failing = then
        elif after == "else":
            other = re.match(r"\s*(.*?)\s*;\s*fi\b", rest)
            failing = other.group(1) if other else ""
        else:
            return True
        if not FAILS.fullmatch(last_command(failing)):
            return True
    return False


def masks_and_list(line, last):
    """Report whether line runs a command other than a test before the final `&&` of a list.

    The shell ignores such a command's failure. Only a list that ends the step (last) passes it on, as the step's
    exit status.
    """
    statements = [statement.strip() for statement in line.split(";") if statement.strip()]
    for index, statement in enumerate(statements):
        if last and index == len(statements) - 1:
            continue
        statement = re.sub(r"^(?:(?:then|else|do)\s+|[{(]\s*)+", "", statement)
        if re.match(r"(?:if|elif|while|until)\s", statement):
            continue  # A condition, which masks_condition reads.
        if any(not is_test(part) for part in re.split(r"\s*&&\s*", statement)[:-1]):
            return True
    return False


def ignores_exit_status(line, last=False, pipefail=False):
    """Report whether a shell line can let a failing command pass under `bash -e`.

    Under `bash -e`, which GitHub Actions uses by default, a failing command fails the step unless the shell reads its
    status as a result. A line lets a failure pass when it:

    - turns errexit off with `set +e`, `+e` among other options such as `set +ex`, or `set +o errexit`;
    - negates a command with `!`, outside an `if` condition whose branch fails;
    - follows `||` with a command that succeeds;
    - pipes a command into another with `|` while pipefail is off (pipefail says whether it is on for this line);
    - runs a command in the background with `&`;
    - runs a command other than a test as an `if`, `while` or `until` condition (see masks_condition);
    - runs a command other than a test before the final `&&` of a list, unless the list ends the step (last).

    Quoted text is blanked first, so a `||` or `!` inside a string is not read as syntax. Nested `if` blocks are read
    approximately, and may be reported when they are safe.
    """
    line = blank_quotes(line)
    if turns_off_errexit(line):
        return True
    if re.search(COMMAND_START + r"!\s", line):
        return True
    if not pipefail and re.search(r"(?<!\|)\|(?!\|)", line):
        return True
    # A lone `&`, not part of `&&`, `|&` or a redirection such as `2>&1` or `&>file`.
    if re.search(r"(?<![&<>|])&(?![&>])", line):
        return True
    if masks_condition(line) or masks_and_list(line, last):
        return True
    for fallback in re.split(r"\|\|", line)[1:]:
        fallback = fallback.strip()
        if fallback.startswith(("{", "(")):
            # A group fails when its last command does.
            close = "}" if fallback[0] == "{" else ")"
            body = fallback[1:].split(close, 1)[0]
            commands = [command.strip() for command in body.split(";") if command.strip()]
            last_in_group = commands[-1] if commands else ""
        else:
            last_in_group = re.split(r"\s*(?:;|&&|\|)\s*", fallback, maxsplit=1)[0]
        if not FAILS.fullmatch(last_in_group.strip()):
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


# Each piece of a shell line between separators, with quoted text kept whole.
SEGMENT = re.compile(r"(?:'[^']*'|\"(?:[^\"\\]|\\.)*\"|[^;&|'\"])+")


def simple_commands(line):
    """Yield each simple command of a shell line, without the keywords, `!`, braces and `VAR=value` that lead it."""
    for segment in SEGMENT.findall(line):
        command = re.sub(r"^(?:(?:if|elif|while|until|then|else|do|!)\s+|[{(]\s*)*", "", segment.strip())
        command = re.sub(r"^(?:\w+=\S*\s+)*", "", command)
        if command:
            yield command


# Each lockfile's own install that fails rather than change the lockfile, by the lockfile's name.
FROZEN_INSTALLS = {
    "Cargo.lock": re.compile(r"cargo\s.*(?<!\S)--(?:locked|frozen)(?!\S)"),
    "uv.lock": re.compile(r"uv\s.*(?<!\S)--(?:locked|frozen)(?!\S)"),
    "package-lock.json": re.compile(r"npm\s+(?:ci|clean-install)(?!\S)"),
    "pnpm-lock.yaml": re.compile(r"pnpm\s+(?:install|i)\s.*(?<!\S)--frozen-lockfile(?!\S)"),
    "yarn.lock": re.compile(r"yarn(?:\s.*)?(?<!\S)--(?:immutable|frozen-lockfile)(?!\S)"),
}


def frozen_install(lockfile, line):
    """Report whether a shell line runs the install of the lockfile at path lockfile, frozen or locked."""
    pattern = FROZEN_INSTALLS.get(PurePosixPath(lockfile).name)
    return pattern is not None and any(pattern.match(command) for command in simple_commands(line))


def run_lines(workflow, job_name):
    """Yield (working directory, line) for each command line of each run step of the job named job_name.

    A step's working directory is its own `working-directory`, else the job's default, else the workflow's, else `.`.
    """
    job = workflow["jobs"][job_name]
    default = "."
    for owner in (workflow, job):
        default = run_defaults(owner).get("working-directory", default)
    for step in job["steps"]:
        for line in shell_lines(step.get("run") or ""):
            yield step.get("working-directory", default), line


def lock_entries(lines, package):
    """Yield the version each of package's own entries in a lockfile's lines records.

    An entry is a line that is all of `name = "<package>"`, as in Cargo.lock, uv.lock and poetry.lock; a top-level key
    `node_modules/<package>`, as in package-lock.json, where a nested copy belongs to another package; or a key
    `<package>@<spec>`, as in pnpm-lock.yaml and yarn.lock. Its version is the first `version` key in the entry, or for
    a `<package>@<spec>` key with none, the spec. A line that only mentions the package, such as a requirement or a
    dependency list, is not an entry.
    """
    quoted = re.escape(package)
    toml = re.compile(rf"name = \"{quoted}\"")
    npm = re.compile(rf"\"node_modules/{quoted}\": \{{")
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


def locked_versions(lockfile, package):
    """Return the set of versions that package's own entries in the lockfile at path lockfile record."""
    return set(lock_entries(lockfile.read_text(encoding="utf-8").splitlines(), package))


def locks_version(lockfile, package, version):
    """Report whether lockfile fixes package at version: every one of package's own entries records that version.

    A package at several versions, such as a transitive copy beside the project's own, is fixed at none of them, since
    this helper cannot tell which one the suite runs.
    """
    return locked_versions(lockfile, package) == {version}


def lockfile_problems(workflow, job_name, tool, pin, root, lockfile):
    """Return why the lockfile at root/lockfile does not pin tool, or [] when it does."""
    path = root / lockfile
    if not path.is_file():
        return [f"{tool}'s lockfile {lockfile} is not in the repository"]
    problems = []
    versions = locked_versions(path, pin.package)
    if len(versions) > 1:
        problems.append(f"{lockfile} holds {pin.package} at several versions: {', '.join(sorted(versions))}")
    elif versions != {pin.version}:
        problems.append(f"{lockfile} does not fix {pin.package} at {pin.version}")
    directory = PurePosixPath(lockfile).parent
    if PurePosixPath(lockfile).name not in FROZEN_INSTALLS:
        problems.append(f"language_drift knows no frozen install for {lockfile}; it knows {', '.join(FROZEN_INSTALLS)}")
    elif not any(
        PurePosixPath(os.path.normpath(cwd)) == directory and frozen_install(lockfile, line)
        for cwd, line in run_lines(workflow, job_name)
    ):
        problems.append(f"no step in job {job_name} installs {lockfile} frozen or locked in {directory}")
    return problems


# A command that installs or fetches the packages it names, such as `pip install` or `go run`.
INSTALLER = re.compile(
    r"(?:python3?\s+-m\s+)?(?:pip3?\s+install|pipx\s+(?:install|run)|uv\s+(?:pip\s+install|tool\s+(?:install|run)|add)"
    r"|uvx|go\s+(?:install|run|get)|cargo\s+(?:install|binstall)|npm\s+(?:install|i|add)|pnpm\s+(?:add|install|i)"
    r"|yarn\s+(?:global\s+)?add|gem\s+install|brew\s+install)(?=\s|$)"
)
# A version spec written onto a package name: `@` or `==` pins it, and the others leave it free to move.
SPEC = r"(@|===|==|~=|>=|<=|!=|<|>)([^\s'\";,)]+)"
# Extras written onto a Python package name, as in `semgrep[all]`.
EXTRAS = r"(?:\[[^\]\s]*\])?"


def words_of(command):
    try:
        return shlex.split(command)
    except ValueError:
        return command.split()


def version_flag(words):
    """Return the value of a `--version` option among words, as `cargo install` takes it, or None."""
    for index, word in enumerate(words):
        if word == "--version" and index + 1 < len(words):
            return words[index + 1]
        if word.startswith("--version="):
            return word.split("=", 1)[1]
    return None


def step_pins(step, tool, pin):
    """Return (whether step pins tool at pin.version, how step installs tool at another version or none).

    A step pins the tool when what it runs or sets, its `run`, `with` and `env`, writes the tool or its package
    followed straight by `@<version>` or `==<version>`, with or without extras such as `[all]` between them (a `$VAR`
    in the step's env counts as its value), when it
    installs the tool with `--version <version>`, or when it uses the tool's own action, such as
    `golangci/golangci-lint-action`, with the version as an input. Its `name` is a label and counts for neither.
    """
    names = {tool, pin.package}
    env = step.get("env") or {}
    pinned = False
    text = "\n".join(strings_in([step.get(key) for key in ("run", "with", "env")]))
    # By where each spec ends, so that the tool and its package, both written in `example.com/tool@latest`, count once.
    specs = {}
    for name in names:
        for match in re.finditer(rf"(?<![\w.@-]){re.escape(name)}{EXTRAS}{SPEC}", text):
            if match.end() not in specs or len(match.group(0)) > len(specs[match.end()].group(0)):
                specs[match.end()] = match
    wrong = []
    for match in specs.values():
        written = match.group(0)
        op, spec = match.groups()
        variable = re.fullmatch(r"\$\{?(\w+)\}?", spec)
        version = str(env[variable.group(1)]) if variable and variable.group(1) in env else spec
        if op in ("@", "==", "===") and version == pin.version:
            pinned = True
        else:
            wrong.append(f"installs {written}")
    for line in shell_lines(step.get("run") or ""):
        for command in simple_commands(line):
            installer = INSTALLER.match(command)
            if not installer:
                continue
            words = words_of(command[installer.end() :])
            flag = version_flag(words)
            for word in words:
                # The package name, without the extras and version spec written onto it.
                package = re.split(r"[\[<>=!~;@]", word)[0]
                if package not in names or re.fullmatch(rf"{EXTRAS}{SPEC}", word[len(package) :]):
                    continue  # Another package, or a spec that the loop over specs above has read.
                if flag == pin.version:
                    pinned = True
                elif flag is None:
                    wrong.append(f"installs {word} with no version")
                else:
                    wrong.append(f"installs {word} --version {flag}")
    uses = step.get("uses") or ""
    repository = uses.split("@", 1)[0].rsplit("/", 1)[-1]
    inputs = step.get("with") or {}
    if repository and any(
        re.fullmatch(rf"(?:setup-)?{re.escape(PurePosixPath(name).name)}(?:-action)?", repository) for name in names
    ):
        if pin.version in (str(value) for value in inputs.values()):
            pinned = True
        else:
            wrong.append(f"uses {uses} without the input {pin.version}")
    return pinned, list(dict.fromkeys(wrong))


def pin_problems(workflow, job_name, pins, root=None, lockfiles=None):
    """Return each tool in pins that the job named job_name does not pin at its version, or [] when all are.

    Each tool needs a step that pins it (see step_pins), and no step may install it at another version or none. A tool
    in lockfiles, {tool: lockfile path relative to root}, is pinned instead when that lockfile fixes its package at its
    version and a step in the lockfile's directory runs that lockfile's own install frozen or locked (see
    FROZEN_INSTALLS); no other step may install it either.
    """
    lockfiles = lockfiles or {}
    problems = []
    steps = workflow["jobs"][job_name]["steps"]
    for tool, pin in pins.items():
        reasons = []
        pinned = False
        for step in steps:
            step_pinned, wrong = step_pins(step, tool, pin)
            pinned = pinned or step_pinned
            reasons += [f"step {step_label(step)!r} {how}" for how in wrong]
        if tool in lockfiles:
            problems += lockfile_problems(workflow, job_name, tool, pin, Path(root), lockfiles[tool])
        elif not pinned:
            reasons.insert(0, "no step pins it")
        if reasons:
            problems.append(f"job {job_name} does not pin {tool} at {pin.version}: {'; '.join(reasons)}")
    return problems


class DriftTests:
    """Checks that a language's check suite job keeps each check in place, against its checks.md.

    Mix it into a unittest.TestCase and set CHECKS, the path of the language's checks.md, and JOB, the name of its suite
    job in WORKFLOW. Set LOCKFILES, {tool: lockfile path relative to ROOT}, for each tool pinned through a lockfile; the
    lockfile's name must be one FROZEN_INSTALLS knows.
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
