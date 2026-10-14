#!/usr/bin/env python3
"""Find every resolved version of a package in a repository and check it against a fix.

Usage:
  deps.py <repo dir> --ecosystem ECO --package NAME [--target VERSION ...] [--affected RANGE ...]

Standard library only. Python 3.9+.

Lists the repository's files and reads every lockfile for the ecosystem. In a git work tree it reads every
tracked or untracked, non-ignored file wherever it lives (git ls-files -co --exclude-standard; submodules and
nested repositories are walked); otherwise it walks the tree, skipping .git, node_modules, target, vendor,
dist, build, hidden and other generated directories. node_modules, .git and package-manager stores (.pnpm-store,
.yarn, .cargo, .venv, venv) are skipped in both modes. The report's "discovery" field says which mode ran.

  npm       package-lock.json, npm-shrinkwrap.json, pnpm-lock.yaml, yarn.lock
            (classic and berry; npm: aliases resolve to the real package), bun.lock (text), deno.lock (its npm
            packages). A binary bun.lockb cannot be read, so it makes the scan exit 2.
  rust      Cargo.lock
  go        go.mod (require lines; "// indirect" marks a transitive dependency;
            a replace to another version of the same module is applied, and
            a replace of the package to a fork or local path is unreadable;
            exclude and retract lines are ignored). go.work: its replace
            directives override the go.mod of every module it uses, and a used
            module outside the repository is unreadable.
  pip       poetry.lock, uv.lock, pdm.lock, Pipfile.lock, pylock.toml and pylock.<name>.toml,
            and requirements files: requirements*.txt, requirements*.lock (rye), constraints*.txt and any .txt in
            a requirements*/ directory (== pins). -r/--requirement and -c/--constraint includes are followed
            relative to the including file (cycles stop); an include that is missing, a URL or outside the
            repository is unreadable. A requirements file with requirements is a complete lock only when every
            requirement is == pinned and it shows it was compiled (a pip-compile or uv header, # via
            annotations, or --hash on every requirement); otherwise it lists only top-level packages, so a
            package it does not list exits 2. A constraints file never adds packages and is exempt.
            (aliases: python, pypi)
  composer  composer.lock (alias: php)

It also lists manifests that name the package directly: package.json
dependency fields, overrides and resolutions; pnpm-workspace.yaml catalogs;
Cargo.toml dependency tables; go.mod direct requires; pyproject.toml
([project] dependencies and optional-dependencies, [dependency-groups], uv, pdm
and poetry dependency tables); Pipfile package sections; composer.json require
and require-dev. A manifest that names the package with no lockfile for the
ecosystem in its directory or any ancestor up to the repository root makes the
scan exit 2: nothing read resolves it. Known residual: a manifest without a
lockfile that does not name the package may still resolve it transitively;
that is not detected.

A resolved version is vulnerable when it falls inside any --affected range
(comparators joined by commas, alternatives by ||, e.g. ">= 1.0.0, < 1.2.2";
any other syntax is rejected). Versions order by semver, with PEP 440 rc,
.post and .dev suffixes understood; a version it cannot order is an error. Without --affected,
it is vulnerable when a --target exists on its major line (0.x counts minor
as major) and it is lower, or when it is below every target line. With
neither, versions are listed and nothing is judged.

Prints JSON: package, ecosystem, lockfiles [{path, versions, vulnerable}],
manifests [{path, field, spec}], vulnerable [{path, version, needs}],
unsupported [{path, reason}] (what could not be read or judged, and why),
ok, unreadable, discovery ("git" or "walk").

Exit codes:
  0  every file that determines the package's resolved versions was found and
     read in full (lockfiles, followed includes, go.work) and no resolved
     version of the package is vulnerable (including when the package is
     absent). Only this proves the package is safe.
  1  a resolved version is vulnerable (even if something was also unreadable).
  2  bad usage or an unreadable repository, or the scan cannot prove safety:
     a lockfile or include could not be read, the package is locked without a
     version this script can judge, a file may resolve it without listing it,
     or a manifest names it with no lockfile (listed in unsupported; ok is
     false, unreadable true).

Reader contract: every entry a reader sees yields its real package name and
version, or the lockfile is unreadable. A file is unreadable when its text is
not recognizably that format (no expected header, invalid TOML or JSON, a
truncated last entry), or any entry has a name it cannot recover or that is
not valid for the ecosystem, or lacks a version where the format always
records one. Such an entry is never dropped, so it never reads as absence.
An entry with a known name whose format records no version (a bun github: or
tarball dependency, a Pipfile.lock git/file/path entry, a v1 package-lock git
version, an unpinned, URL or editable-VCS requirements line, a pylock vcs,
directory or archive package) does not block
other packages: it makes the scan exit 2 only when it is the package asked
about. A go.mod before go 1.17 (or with no go directive) lists only direct
requirements, so a package it does not list exits 2.

Entries skipped without a version, each because it is first-party (the
repository's own source, not a third-party install):
  package-lock   paths outside node_modules/ (root and workspace sources),
                 "link": true entries (symlinks to those), v1 file:/link:
                 versions (local directories)
  pnpm-lock      file:/link: entries resolved from a local directory
  yarn.lock      none; berry workspace:/link:/portal: entries carry
                 0.0.0-use.local and are read like any other
  bun.lock       workspace:, file: and link: refs
  uv.lock        source = { virtual } or { editable } members
  Pipfile.lock   editable path entries
  requirements   options (--index-url, ...; -r and -c are followed) and local paths, '-e .'
  pylock.toml    editable directory packages
An unreadable manifest is listed in unsupported and does not change the exit.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.parse
from pathlib import Path

try:  # Python 3.11+; older interpreters use the structural checks in read_toml_packages.
    import tomllib
except ImportError:  # pragma: no cover - exercised by patching deps.tomllib in tests
    tomllib = None

SKIP_DIRS = {".git", "node_modules", "target", "vendor", "dist", "build", ".next", ".turbo", ".pnpm-store",
             ".venv", "venv", "__pycache__", ".cargo", ".yarn"}  # walk fallback only (no git work tree)
# Installed packages and package-manager stores: never the repository's own dependency files, in either discovery mode.
ALWAYS_SKIP = {".git", "node_modules", ".pnpm-store", ".yarn", ".cargo", ".venv", "venv", "__pycache__"}
ALIASES = {"python": "pip", "pypi": "pip", "php": "composer", "cargo": "rust", "crates": "rust",
           "golang": "go", "node": "npm", "pnpm": "npm", "yarn": "npm"}
LOCKFILES = {
    "npm": ("package-lock.json", "npm-shrinkwrap.json", "pnpm-lock.yaml", "yarn.lock", "bun.lock", "deno.lock"),
    "rust": ("Cargo.lock",),
    "go": ("go.mod",),
    "pip": ("poetry.lock", "uv.lock", "Pipfile.lock", "pdm.lock"),
    "composer": ("composer.lock",),
}
UNSUPPORTED = {"npm": ("bun.lockb",)}
MANIFESTS = {"npm": ("package.json", "pnpm-workspace.yaml"), "rust": ("Cargo.toml",), "go": ("go.mod",),
             "pip": ("pyproject.toml", "Pipfile"), "composer": ("composer.json",)}
PYLOCK_NAME = re.compile(r"pylock(?:\.[^.]+)?\.toml")  # PEP 751: pylock.toml or pylock.<name>.toml
REQ_NAME = re.compile(r"(?:requirements[^/]*\.(?:txt|lock)|constraints[^/]*\.txt)", re.I)


# ---------------------------------------------------------------- versions

PY_SUFFIX = re.compile(
    r"^(?:[-_.]?(?P<pre>a|alpha|b|beta|c|rc|pre|preview)[-_.]?(?P<pre_n>\d*))?"
    r"(?:[-_.]?(?:post|rev|r)[-_.]?(?P<post>\d*))?"
    r"(?:[-_.]?(?P<dev>dev)[-_.]?(?P<dev_n>\d*))?$", re.I)
PY_PRE = {"a": "a", "alpha": "a", "b": "b", "beta": "b"}


def version_key(version: str) -> tuple:
    """Order semver (1.2.3-rc.1), Go pseudo-versions, and PEP 440 suffixes (rc1, .post1, .dev1).

    Raises ValueError for a version it cannot order, rather than guessing."""
    v = version.strip().lstrip("vV=").split("+", 1)[0]
    m = re.match(r"(\d+(?:\.\d+)*)(.*)$", v)
    if not m:
        raise ValueError(f"unsupported version: {version!r}")
    parts = [int(p) for p in m.group(1).split(".")]
    while len(parts) > 3 and parts[-1] == 0:
        parts.pop()
    while len(parts) < 3:
        parts.append(0)
    rest = m.group(2)
    py = PY_SUFFIX.match(rest) if rest else None
    if not rest:
        pre_key, post_key, dev_key = (1,), (-1,), (1,)
    elif py and (py["pre"] or py["post"] is not None or py["dev"]):
        if py["pre"]:
            label = PY_PRE.get(py["pre"].lower(), "rc")
            pre_key = (0, ((1, label), (0, int(py["pre_n"] or 0))))
        else:
            pre_key = (-1,) if py["dev"] and py["post"] is None else (1,)
        post_key = (int(py["post"] or 0),) if py["post"] is not None else (-1,)
        dev_key = (0, int(py["dev_n"] or 0)) if py["dev"] else (1,)
    elif rest.startswith("-") and len(rest) > 1:
        pre_key = (0, tuple((0, int(x)) if x.isdigit() else (1, x) for x in rest[1:].split(".")))
        post_key, dev_key = (-1,), (1,)
    else:
        raise ValueError(f"unsupported version: {version!r}")
    return (tuple(parts), pre_key, post_key, dev_key)


def major_line(version: str) -> str:
    parts = version_key(version)[0]
    return f"0.{parts[1]}" if parts[0] == 0 else str(parts[0])


OPS = {
    "<": lambda a, b: a < b, "<=": lambda a, b: a <= b, ">": lambda a, b: a > b,
    ">=": lambda a, b: a >= b, "=": lambda a, b: a == b, "==": lambda a, b: a == b,
}


COMPARATOR = re.compile(r"\s*(<=|>=|==|=|<|>)?\s*v?([0-9][^\s,|]*)\s*")


def parse_range(rng: str) -> list[list[tuple[str, str]]]:
    """'>= 1.0.0, < 1.2.2 || >= 2.0.0, < 2.0.5' -> alternatives of comparators. Rejects anything else."""
    alternatives = []
    for alt in rng.split("||"):
        comparators = []
        for part in alt.split(","):
            m = COMPARATOR.fullmatch(part)
            if not m:
                raise ValueError(f"unparseable range: {rng!r}")
            comparators.append((m.group(1) or "=", m.group(2)))
        alternatives.append(comparators)
    return alternatives


def in_range(version: str, rng: str) -> bool:
    """True when version satisfies every comparator of any alternative in rng, e.g. '>= 1.0.0, < 1.2.2'."""
    vk = version_key(version)
    return any(all(OPS[op](vk, version_key(bound)) for op, bound in alt) for alt in parse_range(rng))


def judge(version: str, targets: list[str], affected: list[str]) -> str | None:
    """Return the version needed when `version` is vulnerable, else None. '' means vulnerable, fix unknown."""
    if affected:
        if not any(in_range(version, r) for r in affected):
            return None
        above = sorted((t for t in targets if version_key(t) > version_key(version)), key=version_key)
        same = [t for t in above if major_line(t) == major_line(version)]
        return (same or above or [""])[0]
    if not targets:
        return None
    same = [t for t in targets if major_line(t) == major_line(version)]
    if same:
        need = max(same, key=version_key)
        return need if version_key(version) < version_key(need) else None
    above = sorted((t for t in targets if version_key(t) > version_key(version)), key=version_key)
    return above[0] if above else None


# ---------------------------------------------------------------- lockfile readers
#
# Reader contract: a reader returns one entry per package it sees, as (name, version) or (name, None, detail).
# version None means a third-party package whose format records no resolved version (a git, URL or unpinned
# dependency); scan() reports it as unreadable only when it is the package asked about. A reader raises
# ValueError for any entry whose real package name it cannot recover, and for a missing version where the format
# always records one. It skips only first-party entries, each named at its skip. check_entries() then rejects
# names outside the ecosystem's grammar and non-string or empty versions, so a garbled entry is never dropped.

INCOMPLETE = "<incomplete>"  # entry name: the file may resolve packages it does not list (old go.mod)
INCLUDE = "<include>"  # entry name: (INCLUDE, "r" or "c", path or URL) for a requirements -r/-c include

NAME_RE = {
    "npm": re.compile(r"(?:@[a-z0-9~][\w.~-]*/)?[a-z0-9~][\w.~-]*", re.I),
    "pip": re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?"),
    "rust": re.compile(r"[A-Za-z0-9_-]+"),
    "composer": re.compile(r"[a-z0-9](?:[_.-]?[a-z0-9]+)*/[a-z0-9](?:(?:[_.]|-{1,2})?[a-z0-9]+)*", re.I),
    "go": re.compile(r"[A-Za-z0-9][\w.~+-]*(?:/[\w.~+-]+)*"),
}


def norm(name: str, eco: str) -> str:
    name = name.strip().strip("'\"")
    return re.sub(r"[-_.]+", "-", name).lower() if eco == "pip" else name


def check_entries(entries, eco: str) -> list[tuple[str, str | None, str | None]]:
    """Validate reader output as (name, version or None, detail); raise ValueError on any entry that is not."""
    out = []
    for entry in entries:
        name, version, detail = (tuple(entry) + (None,))[:3]
        if name == INCOMPLETE:
            out.append((name, None, detail))
            continue
        if name == INCLUDE:
            out.append((name, version, detail))
            continue
        if not isinstance(name, str) or not NAME_RE[eco].fullmatch(name):
            raise ValueError(f"unrecognized package name {name!r}")
        if version is not None and (not isinstance(version, str) or not version.strip()):
            raise ValueError(f"package {name!r} has an unrecognized version {version!r}")
        out.append((name, version, detail))
    return out


def split_spec(spec: str) -> tuple[str, str | None]:
    """'name@ref' -> (name, ref), splitting at the first '@' after an optional '@scope/'; ref is None without one."""
    start = spec.find("/") + 1 if spec.startswith("@") else 0
    at = spec.find("@", start) if start or not spec.startswith("@") else -1
    return (spec, None) if at < 0 else (spec[:at], spec[at + 1:])


def is_semver_ref(ref: str | None) -> bool:
    return bool(ref) and ref[0].isdigit()


def read_toml_packages(text: str) -> list[tuple]:
    """[[package]] blocks with name/version keys: Cargo.lock, poetry.lock, uv.lock.

    Raises ValueError for text that is not such a lockfile, so a parse failure never reads as absence.
    A package without a version is skipped only for a uv virtual or editable member: a first-party project
    built from the workspace's own source."""
    if tomllib is not None:
        data = tomllib.loads(text)  # TOMLDecodeError is a ValueError
        if not any(k in data for k in ("package", "version", "metadata")):
            raise ValueError("unrecognized lockfile: no package, version or metadata key")
        packages = data.get("package", [])
        if not isinstance(packages, list):
            raise ValueError("unrecognized lockfile: package is not an array of tables")
        out = []
        for pkg in packages:
            if not isinstance(pkg, dict) or not isinstance(pkg.get("name"), str):
                raise ValueError(f"unrecognized lockfile: package entry without a name: {pkg!r}")
            if "version" in pkg:
                out.append((pkg["name"], pkg["version"]))
            elif not (isinstance(pkg.get("source"), dict) and {"virtual", "editable"} & set(pkg["source"])):
                raise ValueError(f"unrecognized lockfile: package {pkg['name']!r} has no version")
        return out
    if not re.search(r"^(?:\[\[package\]\]|package\s*=\s*\[|version\s*=|\[metadata\])", text, re.M):
        raise ValueError("unrecognized lockfile: no [[package]], version or [metadata]")
    out = []
    for block in re.split(r"^\[\[package\]\]\s*$", text, flags=re.M)[1:]:
        block = re.split(r"^\[", block, maxsplit=1, flags=re.M)[0]  # stop at the next table
        name = re.search(r'^name\s*=\s*"([^"]+)"', block, re.M)
        ver = re.search(r'^version\s*=\s*"([^"]+)"', block, re.M)
        if not name:
            raise ValueError("unrecognized lockfile: package entry without a name")
        if ver:
            out.append((name.group(1), ver.group(1)))
        elif not re.search(r"^source\s*=\s*\{[^}]*\b(?:virtual|editable)\s*=", block, re.M):
            raise ValueError(f"unrecognized lockfile: package {name.group(1)!r} has no version")
    return out


def read_package_lock(text: str) -> list[tuple]:
    """package-lock.json / npm-shrinkwrap.json, lockfile v1 (dependencies tree) and v2/v3 (packages map).

    Skipped as first-party: the root and workspace source entries (paths outside node_modules/), "link": true
    entries (a symlink to one of those), and v1 "file:"/"link:" versions (a local directory)."""
    data = json.loads(text)
    if not isinstance(data, dict) or "lockfileVersion" not in data:
        raise ValueError("unrecognized package-lock: no lockfileVersion")
    packages = data.get("packages")
    if packages is not None and not isinstance(packages, dict):
        raise ValueError("unrecognized package-lock: packages is not an object")
    out = []
    for path, meta in (packages or {}).items():
        if "node_modules/" not in path:
            continue
        if not isinstance(meta, dict):
            raise ValueError(f"unrecognized package-lock: entry {path!r} is not an object")
        if meta.get("link") is True:
            continue
        version = meta.get("version")
        if not isinstance(version, str) or not version:
            raise ValueError(f"unrecognized package-lock: entry {path!r} has no version")
        # An alias installs under its alias path; "name" holds the real package.
        out.append((meta.get("name") or path.rsplit("node_modules/", 1)[1], version))

    def walk(deps):
        if not isinstance(deps, dict):
            raise ValueError("unrecognized package-lock: dependencies is not an object")
        for name, meta in deps.items():
            version = meta.get("version") if isinstance(meta, dict) else None
            if not isinstance(version, str) or not version:
                raise ValueError(f"unrecognized package-lock: dependency {name!r} has no version")
            if version.startswith(("file:", "link:")):
                pass
            elif version.startswith("npm:"):
                real, ref = split_spec(version[4:])
                if not ref:
                    raise ValueError(f"unrecognized package-lock: alias {name!r} has no version: {version!r}")
                out.append((real, ref))
            elif is_semver_ref(version):
                out.append((name, version))
            else:
                out.append((name, None, version))  # git or URL dependency: no semver recorded
            walk(meta.get("dependencies") or {})
    if not packages:
        walk(data.get("dependencies") or {})
    return out


def pnpm_key(key: str) -> tuple[str, str | None]:
    """(name, ref) of a pnpm packages/snapshots key: v9 'name@ref', v6 '/name@ref', v5 '/name/ref'."""
    m = re.match(r"^/((?:@[^/]+/)?[^/@]+)/(\d.*)$", key)
    if m:
        return m.group(1), m.group(2)
    return split_spec(key[1:] if key.startswith("/") else key)


def read_pnpm_lock(text: str) -> list[tuple]:
    """pnpm-lock.yaml v5, v6 and v9: every key under packages and snapshots.

    A key's ref is its version when it starts with a digit (peer suffixes '(…)' and '_…' are dropped);
    otherwise (git, tarball, v6 host-path keys) the entry's own version: and name: fields are used.
    Skipped as first-party: a file:/link: entry resolved from a local directory, and a snapshot key whose
    packages entry was already read."""
    if not re.search(r"^lockfileVersion:", text, re.M):
        raise ValueError("unrecognized pnpm-lock.yaml: no lockfileVersion")
    entries, section = [], None  # (section, key, body fields)
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if not line[0].isspace():
            section = line.split(":", 1)[0].strip()
            continue
        if section not in ("packages", "snapshots"):
            continue
        m = re.match(r"^  (?! )(.+?):(?: (.*))?$", line)
        if m:
            entries.append((section, m.group(1).strip("'\""), {}))
            continue
        f = re.match(r"^    (\w+): (.*)$", line)
        if f and entries:
            entries[-1][2][f.group(1)] = f.group(2).strip().strip("'\"")
    package_keys = {k for s, k, _ in entries if s == "packages"}
    out = []
    for section, key, body in entries:
        name, ref = pnpm_key(key)
        if is_semver_ref(ref):
            out.append((name, re.match(r"[^(_\s]+", ref).group(0)))
        elif "version" in body:
            out.append((body.get("name", name), body["version"]))
        elif re.match(r"^(?:file|link):", ref or key) and ("directory" in body.get("resolution", "")
                                                           or (ref or key).startswith("link:") or section == "snapshots"):
            continue
        elif section == "snapshots" and key.split("(", 1)[0] in package_keys:
            continue
        else:
            raise ValueError(f"unrecognized pnpm-lock.yaml: entry {key!r} has no version")
    return out


def yarn_name(spec: str) -> str:
    """The real package of a yarn.lock descriptor, resolving npm: aliases and patch: wrappers."""
    name, rng = split_spec(spec)
    if not rng:
        raise ValueError(f"unrecognized yarn.lock descriptor {spec!r}")
    if rng.startswith("npm:"):
        real, real_rng = split_spec(rng[4:])
        if real_rng is not None:  # alias: "alias@npm:pkg@range"
            return real
    elif rng.startswith("patch:"):
        return yarn_name(urllib.parse.unquote(rng[6:]))
    return name


def read_yarn_lock(text: str) -> list[tuple]:
    """yarn.lock classic (v1) and berry (v2+). Every entry needs a name in each descriptor and a version line.

    Berry workspace:, link: and portal: entries are first-party but carry version 0.0.0-use.local, so they are
    read like any other entry."""
    if not re.search(r"^(?:# yarn lockfile v1\s*$|__metadata:)", text, re.M):
        raise ValueError("unrecognized yarn.lock: no '# yarn lockfile v1' or __metadata header")
    out, names = [], []
    for line in text.splitlines():
        if line and not line[0].isspace() and not line.startswith("#"):
            if names:
                raise ValueError(f"unrecognized yarn.lock: entry without a version before {line.strip()!r}")
            if line.rstrip() == "__metadata:":
                continue
            if not line.rstrip().endswith(":"):
                raise ValueError(f"unrecognized yarn.lock line {line!r}")
            names = [yarn_name(spec.strip().strip('"')) for spec in line.rstrip()[:-1].split(",")]
            continue
        m = re.match(r'^  version:? +"?([^"\s]+)"?\s*$', line)
        if m and names:
            out.extend((n, m.group(1)) for n in dict.fromkeys(names))
            names = []
    if names:
        raise ValueError("unrecognized yarn.lock: last entry has no version (truncated?)")
    return out


def read_bun_lock(text: str) -> list[tuple]:
    """bun.lock (text). Each packages value is a list led by 'name@ref'.

    Skipped as first-party: workspace:, file: and link: refs (the repository's own or local directories).
    A github:, git or tarball ref records no version, so it yields (name, None)."""
    data = json.loads(re.sub(r",(\s*[}\]])", r"\1", text))  # bun.lock is JSON with trailing commas
    if not isinstance(data, dict) or "lockfileVersion" not in data or not isinstance(data.get("packages", {}), dict):
        raise ValueError("unrecognized bun.lock: no lockfileVersion or packages object")
    out = []
    for key, value in (data.get("packages") or {}).items():
        if not isinstance(value, list) or not value or not isinstance(value[0], str):
            raise ValueError(f"unrecognized bun.lock: entry {key!r} is not a package list")
        name, ref = split_spec(value[0])
        if not ref:
            raise ValueError(f"unrecognized bun.lock: entry {key!r} has no version: {value[0]!r}")
        if ref.startswith(("workspace:", "file:", "link:")):
            continue
        out.append((name, ref) if is_semver_ref(ref) else (name, None, ref))
    return out


GO_DIRECTIVE_BLOCK = re.compile(r"^(\w+)\s*\(\s*(?://.*)?$")


def go_tokens(line: str) -> tuple[list[str], str]:
    """Tokens of a go.mod line (quotes removed) and its trailing comment ('// …' or '')."""
    code, sep, comment = line.partition("//")
    return [t.strip('"`') for t in re.findall(r'"[^"]*"|`[^`]*`|\S+', code)], sep + comment


def go_directives(text: str, verb: str) -> list[tuple[list[str], str]]:
    """(tokens, comment) for each line of a `verb` directive, single-line or in a block."""
    out, block = [], None
    for line in text.splitlines():
        s = line.strip()
        if block:
            if s.startswith(")"):
                block = None
            elif block == verb and s and not s.startswith("//"):
                out.append(go_tokens(s))
            continue
        d = GO_DIRECTIVE_BLOCK.match(s)
        if d:
            block = d.group(1)
        elif s.startswith(verb + " "):
            out.append(go_tokens(s[len(verb):]))
    return out


def go_requires(text: str) -> list[tuple[str, str, str]]:
    """(module, version, comment) for each require; raises ValueError on a require line it cannot parse."""
    out = []
    for toks, comment in go_directives(text, "require"):
        if len(toks) != 2 or not toks[1].startswith("v"):
            raise ValueError(f"unrecognized go.mod require: {' '.join(toks)!r}")
        out.append((toks[0], toks[1], comment))
    return out


def go_replaces(text: str) -> list[tuple[str, str | None, str, str | None]]:
    """(module, version or None, destination, destination version or None) for each replace directive."""
    out = []
    for toks, _ in go_directives(text, "replace"):
        if "=>" not in toks or toks.index("=>") not in (1, 2) or len(toks) - toks.index("=>") not in (2, 3):
            raise ValueError(f"unrecognized go.mod replace: {' '.join(toks)!r}")
        i = toks.index("=>")
        out.append((toks[0], toks[1] if i == 2 else None, toks[i + 1], toks[i + 2] if len(toks) > i + 2 else None))
    return out


def read_go_mod(text: str) -> list[tuple]:
    """Resolved module versions: each require, with any replace pointing at the same module applied.

    A replace that points at a different module or a local path cannot be judged here: its version is
    reported as "=> <destination>", which scan() lists as unreadable when it is the package asked about.
    Before go 1.17 (or with no go directive) go.mod lists only direct requirements, so it also yields an
    INCOMPLETE marker: a package it does not list may still be resolved."""
    if not re.search(r"^\s*module\s+\S", text, re.M):
        raise ValueError("unrecognized go.mod: no module directive")
    replaces = go_replaces(text)
    out = []
    for mod, ver, _ in go_requires(text):
        rule = next((r for r in replaces if r[0] == mod and r[1] == ver), None) \
            or next((r for r in replaces if r[0] == mod and r[1] is None), None)
        if rule is None:
            out.append((mod, ver))
        elif rule[2] == mod and rule[3]:
            out.append((mod, rule[3]))
        else:
            out.append((mod, f"=> {rule[2]} {rule[3] or ''}".strip()))
    go = re.search(r"^\s*go\s+(\d+)\.(\d+)", text, re.M)
    if not go or (int(go.group(1)), int(go.group(2))) < (1, 17):
        out.append((INCOMPLETE, None, "go directive missing or before 1.17: go.mod lists only direct requirements"))
    return out


def read_pipfile_lock(text: str) -> list[tuple]:
    """Pipfile.lock default and develop sections; each entry needs an == pin.

    Skipped as first-party: an editable path entry (the project's own source). A git, file or path entry
    records no version, so it yields (name, None)."""
    data = json.loads(text)
    if not isinstance(data, dict) or not {"_meta", "default", "develop"} & set(data):
        raise ValueError("unrecognized Pipfile.lock: no _meta, default or develop section")
    out = []
    for section in ("default", "develop"):
        entries = data.get(section) or {}
        if not isinstance(entries, dict):
            raise ValueError(f"unrecognized Pipfile.lock: {section} is not an object")
        for name, meta in entries.items():
            if not isinstance(meta, dict):
                raise ValueError(f"unrecognized Pipfile.lock: entry {name!r} is not an object")
            v = meta.get("version")
            pin = re.fullmatch(r"===?\s*(\S+)", v) if isinstance(v, str) else None
            if pin:
                out.append((name, pin.group(1)))
            elif v is None and meta.get("editable") and "path" in meta:
                continue
            elif v is None and {"git", "hg", "svn", "bzr", "file", "path"} & set(meta):
                out.append((name, None, next(str(meta[k]) for k in ("git", "hg", "svn", "bzr", "file", "path") if k in meta)))
            else:
                raise ValueError(f"unrecognized Pipfile.lock: entry {name!r} has no == version")
    return out


REQ_LINE = re.compile(r"^([A-Za-z0-9][\w.-]*)\s*(?:\[[^\]]*\])?\s*(.*)$")
REQ_SPECIFIERS = re.compile(r"(?:(?:~=|==|!=|<=|>=|<|>)\s*[\w.*+!-]+\s*,?\s*)+")
REQ_INCLUDE = re.compile(r"^(?:-([rc])\s*|--(requirement|constraint)(?:\s*=\s*|\s+))(\S.*?)\s*$")
REQ_COMPILED = re.compile(r"^#.*\b(?:pip-compile|uv pip compile|autogenerated by uv|uv export|generated by rye)\b"
                          r"|#\s*via\b", re.M | re.I)
REQ_INCOMPLETE = ("not a complete lock: a requirements file counts as one only when every requirement is == pinned and it"
                  " was compiled (a pip-compile or uv header, # via annotations, or --hash on every requirement)")


def read_requirements(text: str, constraints: bool = False) -> list[tuple]:
    """requirements files: 'name==version' pins; any other requirement of a named package yields (name, None).

    -r/--requirement and -c/--constraint includes yield (INCLUDE, "r" or "c", target) for scan() to follow.
    Skipped: other options (--index-url, --hash, …) and local paths, including '-e .' (first-party source).
    A file with requirements that is not compiled (see REQ_INCOMPLETE) lists only top-level packages, so it also
    yields an INCOMPLETE marker; a constraints file never adds packages, so it does not.
    A line that is none of these raises ValueError."""
    out = []
    named = pinned = hashed = local = 0
    for raw in re.sub(r"\\\r?\n", " ", text).splitlines():
        line = re.sub(r"(?:^|\s)#.*$", "", raw).strip()
        if not line:
            continue
        inc = REQ_INCLUDE.match(line)
        if inc:
            out.append((INCLUDE, "r" if (inc.group(1) or inc.group(2)[0]) == "r" else "c", inc.group(3)))
            continue
        if re.match(r"^(?:-e|--editable)(?:\s+|=)", line):
            target = re.split(r"(?:\s+|=)", line, maxsplit=1)[1].strip()
            egg = re.search(r"#(?:.*&)?egg=([A-Za-z0-9][\w.-]*)", target)
            if egg:
                named += 1
                out.append((egg.group(1), None, target))
            elif not re.match(r"^(?:\.|/|~|file:)", target):
                raise ValueError(f"unrecognized requirement line: {raw!r}")
            else:
                local += 1
            continue
        if line.startswith("-"):
            continue
        if re.match(r"^(?:\.|/|~|file:)", line):
            local += 1
            continue
        m = REQ_LINE.match(line)
        if not m:
            raise ValueError(f"unrecognized requirement line: {raw!r}")
        named += 1
        hashed += "--hash" in line
        name, rest = m.group(1), m.group(2).split(";", 1)[0]
        rest = re.split(r"\s--?[a-z]", " " + rest, maxsplit=1)[0].strip()  # drop per-line options (--hash=…)
        pin = re.fullmatch(r"===?\s*([^\s,]+)", rest)
        if pin:
            pinned += 1
            out.append((name, pin.group(1)))
        elif not rest or rest.startswith("@") or REQ_SPECIFIERS.fullmatch(rest):
            out.append((name, None, rest or "unpinned"))
        else:
            raise ValueError(f"unrecognized requirement line: {raw!r}")
    compiled = bool(REQ_COMPILED.search(text)) or (named > 0 and hashed == named)
    if not constraints and (named or local) and (pinned < named or not compiled):
        out.append((INCOMPLETE, None, REQ_INCOMPLETE))
    return out


def read_pylock(text: str) -> list[tuple]:
    """pylock.toml / pylock.<name>.toml (PEP 751): [[packages]] tables with name and version.

    A package without a version must come from a vcs, directory or archive source; it yields (name, None), except an
    editable directory, which is the project's own source and is skipped. Any other package without a version is
    unreadable."""
    if tomllib is not None:
        data = tomllib.loads(text)
        if "lock-version" not in data:
            raise ValueError("unrecognized pylock.toml: no lock-version")
        packages = data.get("packages", [])
        if not isinstance(packages, list):
            raise ValueError("unrecognized pylock.toml: packages is not an array of tables")
        blocks = []
        for pkg in packages:
            if not isinstance(pkg, dict) or not isinstance(pkg.get("name"), str):
                raise ValueError(f"unrecognized pylock.toml: package entry without a name: {pkg!r}")
            directory = pkg.get("directory")
            blocks.append((pkg["name"], pkg.get("version"), next((k for k in ("vcs", "directory", "archive") if k in pkg), None),
                           isinstance(directory, dict) and directory.get("editable") is True))
    else:
        if not re.search(r"^lock-version\s*=", text, re.M):
            raise ValueError("unrecognized pylock.toml: no lock-version")
        blocks = []
        for block in re.split(r"^\[\[packages\]\]\s*$", text, flags=re.M)[1:]:
            head, _, tables = block.partition("\n[")
            tables = "[" + tables
            name = re.search(r'^name\s*=\s*"([^"]+)"', head, re.M)
            ver = re.search(r'^version\s*=\s*"([^"]+)"', head, re.M)
            if not name:
                raise ValueError("unrecognized pylock.toml: package entry without a name")
            source = next((k for k in ("vcs", "directory", "archive")
                           if re.search(rf"^{k}\s*=", head, re.M) or re.search(rf"^\[packages\.{k}\]", tables, re.M)), None)
            editable = source == "directory" and bool(re.search(r"\beditable\s*=\s*true\b", block))
            blocks.append((name.group(1), ver.group(1) if ver else None, source, editable))
    out = []
    for name, version, source, editable in blocks:
        if version is not None:
            out.append((name, version))
        elif editable:
            continue
        elif source:
            out.append((name, None, f"{source} source"))
        else:
            raise ValueError(f"unrecognized pylock.toml: package {name!r} has no version")
    return out


def read_deno_lock(text: str) -> list[tuple]:
    """deno.lock v2-v5: its npm packages, keyed 'name@version' (peer suffixes after '_' dropped). jsr: and remote
    modules are other registries and are not read. A lock with no npm section has no npm packages."""
    data = json.loads(text)
    if not isinstance(data, dict) or not isinstance(data.get("version"), str):
        raise ValueError("unrecognized deno.lock: no version")
    major = data["version"].split(".", 1)[0]
    if major in ("4", "5"):
        npm = data.get("npm")
    elif major == "3":
        npm = (data.get("packages") or {}).get("npm")
    elif major == "2":
        npm = (data.get("npm") or {}).get("packages")
    else:
        raise ValueError(f"unrecognized deno.lock version {data['version']!r}")
    if not isinstance(npm or {}, dict):
        raise ValueError("unrecognized deno.lock: npm is not an object")
    out = []
    for key, meta in (npm or {}).items():
        name, ref = split_spec(key)
        if not is_semver_ref(ref) or not isinstance(meta, dict):
            raise ValueError(f"unrecognized deno.lock: npm entry {key!r} has no version")
        out.append((name, re.match(r"[^_(\s]+", ref).group(0)))
    return out


def read_composer_lock(text: str) -> list[tuple]:
    data = json.loads(text)
    if not isinstance(data, dict) or not {"content-hash", "packages"} & set(data):
        raise ValueError("unrecognized composer.lock: no content-hash or packages")
    out = []
    for section in ("packages", "packages-dev"):
        packages = data.get(section) or []
        if not isinstance(packages, list):
            raise ValueError(f"unrecognized composer.lock: {section} is not a list")
        for p in packages:
            if not isinstance(p, dict) or not isinstance(p.get("name"), str) or "version" not in p:
                raise ValueError(f"unrecognized composer.lock: entry without a name and version: {p!r}")
            out.append((p["name"], p["version"]))
    return out


READERS = {
    "package-lock.json": read_package_lock, "npm-shrinkwrap.json": read_package_lock,
    "pnpm-lock.yaml": read_pnpm_lock, "yarn.lock": read_yarn_lock, "bun.lock": read_bun_lock, "Cargo.lock": read_toml_packages,
    "poetry.lock": read_toml_packages, "uv.lock": read_toml_packages, "Pipfile.lock": read_pipfile_lock,
    "go.mod": read_go_mod, "composer.lock": read_composer_lock, "pdm.lock": read_toml_packages, "deno.lock": read_deno_lock,
}


# ---------------------------------------------------------------- manifests

TOML_STRING = re.compile(r'"((?:[^"\\]|\\.)*)"|\'([^\']*)\'')


def toml_tables(text: str) -> dict:
    """{table path tuple: {key: value}} of a TOML document. With tomllib every nested table is listed; without it,
    a line-based reading that keeps string and array-of-string values (enough for dependency tables)."""
    if tomllib is not None:
        out = {}

        def flat(d, path):
            out[path] = d
            for k, v in d.items():
                if isinstance(v, dict):
                    flat(v, path + (k,))
        flat(tomllib.loads(text), ())
        return out
    out, table, pending = {(): {}}, (), None
    for line in text.splitlines():
        if pending is not None:
            key, buf = pending
            buf += "\n" + line
        else:
            stripped = line.strip()
            header = re.match(r"^\[([^\[\]]+)\]\s*(?:#.*)?$", stripped)
            if header:
                table = tuple(p.strip().strip("'\"") for p in header.group(1).split("."))
                out.setdefault(table, {})
                continue
            if stripped.startswith("[["):
                table = None
                continue
            kv = re.match(r"""^(['"]?[\w.-]+['"]?)\s*=\s*(.*)$""", stripped)
            if not kv or table is None:
                continue
            key, buf = kv.group(1).strip("'\""), kv.group(2)
        if buf.startswith("["):
            depth, quote = 0, None
            for ch in buf:
                if quote:
                    quote = None if ch == quote else quote
                elif ch in "'\"":
                    quote = ch
                elif ch in "[{":
                    depth += 1
                elif ch in "]}":
                    depth -= 1
            if depth > 0:
                pending = (key, buf)
                continue
            value = [a or b for a, b in TOML_STRING.findall(buf)]
        else:
            m = TOML_STRING.match(buf)
            value = (m.group(1) or m.group(2)) if m else buf
        pending = None
        out[table][key] = value
    return out


def pep508_name(spec) -> str | None:
    m = re.match(r"\s*([A-Za-z0-9][A-Za-z0-9._-]*)", spec) if isinstance(spec, str) else None
    return m.group(1) if m else None


def python_manifest_deps(fname: str, text: str) -> list[tuple[str, str, str]]:
    """(field, name, spec) for each dependency a pyproject.toml or Pipfile names."""
    tables, out = toml_tables(text), []

    def strings(field, values):
        for v in values if isinstance(values, list) else []:
            if pep508_name(v):
                out.append((field, pep508_name(v), v))

    def keys(field, table):
        for k, v in (table or {}).items():
            out.append((field, k, v if isinstance(v, str) else json.dumps(v, sort_keys=True)))

    if fname == "Pipfile":
        for path, table in tables.items():
            if len(path) == 1 and path[0] not in ("source", "requires", "pipenv", "scripts"):
                keys(path[0], table)
        return out
    strings("project.dependencies", tables.get(("project",), {}).get("dependencies"))
    strings("tool.uv.dev-dependencies", tables.get(("tool", "uv"), {}).get("dev-dependencies"))
    for path, table in tables.items():
        if path in (("project", "optional-dependencies"), ("dependency-groups",), ("tool", "pdm", "dev-dependencies")):
            for group, values in table.items():
                strings(".".join(path + (group,)), values)
        elif path[:2] == ("tool", "poetry") and path[-1] in ("dependencies", "dev-dependencies") and \
                (len(path) == 3 or (len(path) == 5 and path[2] == "group")):
            keys(".".join(path), {k: v for k, v in table.items() if k != "python"})
    return out


def manifest_refs(path: Path, eco: str, package: str) -> list[dict]:
    text = path.read_text(encoding="utf-8", errors="replace")
    refs = []
    if path.name == "package.json":
        try:
            data = json.loads(text)
        except ValueError:
            return refs
        for field in ("dependencies", "devDependencies", "optionalDependencies", "peerDependencies",
                      "overrides", "resolutions"):
            spec = (data.get(field) or {}).get(package)
            if spec is not None:
                refs.append({"field": field, "spec": spec})
        pnpm_over = ((data.get("pnpm") or {}).get("overrides") or {})
        for key, spec in pnpm_over.items():
            if key == package or key.startswith(package + "@") or key.endswith(">" + package):
                refs.append({"field": f"pnpm.overrides[{key}]", "spec": spec})
    elif path.name == "pnpm-workspace.yaml":
        for m in re.finditer(rf"""^(\s+)['"]?{re.escape(package)}['"]?\s*:\s*(.+)$""", text, re.M):
            refs.append({"field": "catalog-or-overrides", "spec": m.group(2).strip().strip("'\"")})
    elif path.name == "Cargo.toml":
        section = ""
        for line in text.splitlines():
            s = re.match(r"^\s*\[([^\]]+)\]", line)
            if s:
                section = s.group(1)
                continue
            m = re.match(rf"""^\s*['"]?{re.escape(package)}['"]?\s*=\s*(.+)$""", line)
            if m and "dependencies" in section:
                refs.append({"field": section, "spec": m.group(1).strip()})
            elif section.endswith(f"dependencies.{package}") and line.strip().startswith("version"):
                refs.append({"field": section, "spec": line.split("=", 1)[1].strip()})
    elif path.name == "go.mod":
        for mod, ver, rest in go_requires(text):
            if mod == package and "// indirect" not in rest:
                refs.append({"field": "require", "spec": ver})
    elif path.name in ("pyproject.toml", "Pipfile"):
        want = norm(package, "pip")
        for field, name, spec in python_manifest_deps(path.name, text):
            if norm(name, "pip") == want:
                refs.append({"field": field, "spec": spec})
    elif path.name == "composer.json":
        data = json.loads(text)
        for field in ("require", "require-dev"):
            for name, spec in ((data.get(field) or {}) if isinstance(data, dict) else {}).items():
                if name.lower() == package.lower():
                    refs.append({"field": field, "spec": spec})
    return refs


# ---------------------------------------------------------------- discovery

def walk(root: Path):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".") or d == ".github")
        for f in sorted(filenames):
            yield Path(dirpath, f)


def list_files(root: Path) -> tuple[str, list[Path]]:
    """("git", files) in a git work tree: every tracked or untracked, non-ignored file, wherever it lives; a tracked
    submodule is walked. An untracked nested repository (another clone or worktree) is not this repository's content
    and is skipped. ("walk", files) otherwise, skipping SKIP_DIRS and hidden directories. ALWAYS_SKIP directories are
    excluded in both modes."""
    def git(*args):
        done = subprocess.run(["git", "-C", str(root), *args], capture_output=True, timeout=600)
        if done.returncode != 0:
            raise OSError(done.stderr.decode("utf-8", "replace").strip())
        return done.stdout.decode("utf-8", "surrogateescape")

    try:
        if git("rev-parse", "--is-inside-work-tree").strip() == "true":
            tracked = set(git("ls-files", "-z", "-c", "--", ".").split("\0")) - {""}
            untracked = set(git("ls-files", "-z", "-o", "--exclude-standard", "--", ".").split("\0")) - {""}
            files = []
            for rel in sorted(tracked | untracked):
                if ALWAYS_SKIP & set(Path(rel).parts[:-1]):
                    continue
                path = root / rel
                if path.is_dir() and not path.is_symlink():
                    if rel in tracked:  # a submodule
                        files.extend(p for p in walk(path) if not ALWAYS_SKIP & set(p.relative_to(root).parts[:-1]))
                elif os.path.lexists(path):
                    files.append(path)
            return "git", files
    except (OSError, subprocess.SubprocessError):
        pass
    return "walk", list(walk(root))


def lockfile_reader(eco: str, parts: tuple):
    """The reader for a file at relative path `parts` that resolves `eco` packages, or None."""
    name = parts[-1]
    if name in LOCKFILES[eco]:
        return READERS[name]
    if eco == "pip" and PYLOCK_NAME.fullmatch(name):
        return read_pylock
    if eco == "pip" and (REQ_NAME.fullmatch(name) or (name.lower().endswith(".txt") and len(parts) > 1
                                                      and parts[-2].lower().startswith("requirements"))):
        constraints = name.lower().startswith("constraints")
        return lambda text: read_requirements(text, constraints)
    return None


# ---------------------------------------------------------------- scan

def scan(root: Path, eco: str, package: str, targets: list[str], affected: list[str]) -> dict:
    eco = ALIASES.get(eco, eco)
    if eco not in LOCKFILES:
        raise ValueError(f"unsupported ecosystem {eco!r}; supported: {', '.join(sorted(LOCKFILES))}")
    want = norm(package, eco)
    lockfiles, manifests, vulnerable, unsupported = [], [], [], []
    state = {"unreadable": False}
    root_real = os.path.realpath(root)
    seen = set()

    def block(rel, reason):
        unsupported.append({"path": rel, "reason": reason})
        state["unreadable"] = True

    def within(p) -> bool:
        real = os.path.realpath(p)
        return real == root_real or real.startswith(root_real + os.sep)

    def record(rel, entries):
        matched = [(v, d) for n, v, d in entries if n not in (INCOMPLETE, INCLUDE) and norm(n, eco) == want]
        for detail in sorted({d or "" for v, d in matched if v is None}):
            block(rel, f"{package} is locked without a resolved version ({detail or 'no version recorded'}); check by hand")
        if not matched:
            for _, _, detail in (e for e in entries if e[0] == INCOMPLETE):
                block(rel, f"{package} not listed, but {detail}; check by hand")
        found = {v for v, _ in matched if v is not None}
        for v in sorted(v for v in found if v.startswith("=>")):
            block(rel, f"{package} is replaced {v}; check by hand")
        versions = sorted((v for v in found if not v.startswith("=>")), key=version_key)
        if versions:
            bad = []
            for v in versions:
                need = judge(v, targets, affected)
                if need is not None:
                    bad.append(v)
                    vulnerable.append({"path": rel, "version": v, "needs": need or None})
            lockfiles.append({"path": rel, "versions": versions, "vulnerable": bad})

    def read(path: Path, reader):
        real = os.path.realpath(path)
        if real in seen:
            return
        seen.add(real)
        rel = os.path.normpath(os.path.relpath(path, root))
        try:
            entries = check_entries(reader(path.read_text(encoding="utf-8", errors="replace")), eco)
        except (OSError, ValueError, AttributeError, TypeError, KeyError) as exc:
            # An unreadable lockfile can hide a vulnerable version, so the run cannot report ok.
            block(rel, f"unreadable: {type(exc).__name__}: {exc}")
            return
        record(rel, entries)
        for _, kind, target in (e for e in entries if e[0] == INCLUDE):
            # pip resolves an include relative to the file that names it; what it includes resolves packages too.
            what = "constraints" if kind == "c" else "requirements"
            inc = path.parent / target
            if re.match(r"^[A-Za-z][\w+.-]+:", target) or "$" in target:
                block(rel, f"includes {what} {target}, which cannot be read here; check by hand")
            elif not within(inc):
                block(rel, f"includes {what} {target}, outside the repository; check by hand")
            elif not inc.is_file():
                block(rel, f"includes {what} {target}, which does not exist; check by hand")
            else:
                read(inc, lambda text, c=(kind == "c"): read_requirements(text, c))

    method, files = list_files(root)
    lock_dirs = set()
    for path in files:
        parts = path.relative_to(root).parts
        if lockfile_reader(eco, parts) or parts[-1] in UNSUPPORTED.get(eco, ()):
            lock_dirs.add(parts[:-1])
    for path in files:
        parts = path.relative_to(root).parts
        rel, name = str(path.relative_to(root)), path.name
        reader = lockfile_reader(eco, parts)
        if reader:
            read(path, reader)
        if name in UNSUPPORTED.get(eco, ()):
            block(rel, "lockfile format not supported, so it cannot prove the package absent or fixed; check by hand")
        if eco == "go" and name == "go.work":
            go_work(path, rel, record, block, within, package)
        if name in MANIFESTS.get(eco, ()):
            try:
                refs = manifest_refs(path, eco, package)
            except (OSError, ValueError, AttributeError, TypeError, KeyError) as exc:
                unsupported.append({"path": rel, "reason": f"manifest unreadable: {type(exc).__name__}: {exc}"})
                continue
            manifests.extend({"path": rel, **ref} for ref in refs)
            # A manifest that names the package with no lockfile beside or above it: nothing read resolves it.
            if refs and eco != "go" and not any(parts[:i] in lock_dirs for i in range(len(parts))):
                block(rel, f"{package} is named here ({refs[0]['field']}), but no {eco} lockfile in this directory or"
                           f" above resolves it; check by hand")
    return {"package": package, "ecosystem": eco, "targets": targets, "affected": affected,
            "lockfiles": lockfiles, "manifests": manifests, "vulnerable": vulnerable,
            "unsupported": unsupported, "ok": not vulnerable and not state["unreadable"],
            "unreadable": state["unreadable"], "discovery": method}


def go_work(path: Path, rel: str, record, block, within, package: str) -> None:
    """Apply a go.work file: its replace directives override every used module's go.mod, and a used module outside
    the repository resolves versions this scan cannot read."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
        if not re.search(r"^\s*(?:go\s+\d|use\b)", text, re.M):
            raise ValueError("unrecognized go.work: no go or use directive")
        uses = go_directives(text, "use")
        if any(len(toks) != 1 for toks, _ in uses):
            raise ValueError("unrecognized go.work use directive")
        replaces = go_replaces(text)
    except (OSError, ValueError) as exc:
        block(rel, f"unreadable: {type(exc).__name__}: {exc}")
        return
    required = set()
    for (use,), _ in uses:
        module = path.parent / use
        if not within(module):
            block(rel, f"uses module {use}, outside the repository; check by hand")
            continue
        try:
            required |= {v for m, v, _ in go_requires((module / "go.mod").read_text(encoding="utf-8")) if m == package}
        except (OSError, ValueError) as exc:
            block(rel, f"uses module {use}, whose go.mod cannot be read: {type(exc).__name__}: {exc}")
    entries = []
    for ver in sorted(required):
        rule = next((r for r in replaces if r[0] == package and r[1] == ver), None) \
            or next((r for r in replaces if r[0] == package and r[1] is None), None)
        if rule and rule[2] == package and rule[3]:
            entries.append((package, rule[3], None))
        elif rule:
            entries.append((package, f"=> {rule[2]} {rule[3] or ''}".strip(), None))
    record(rel, entries)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("repo")
    parser.add_argument("--ecosystem", required=True)
    parser.add_argument("--package", required=True)
    parser.add_argument("--target", action="append", default=[])
    parser.add_argument("--affected", action="append", default=[])
    args = parser.parse_args(argv)
    root = Path(args.repo)
    if not root.is_dir():
        print(f"error: not a directory: {root}", file=sys.stderr)
        return 2
    try:
        for r in args.affected:
            in_range("0.0.0", r)
        result = scan(root, args.ecosystem.lower(), args.package, [t.lstrip(">= v") for t in args.target], args.affected)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    json.dump(result, sys.stdout, indent=2)
    print()
    if result["vulnerable"]:
        return 1
    if result["unreadable"]:
        print("error: a lockfile could not be read; see unsupported", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
