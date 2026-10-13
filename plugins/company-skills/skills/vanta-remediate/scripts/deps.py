#!/usr/bin/env python3
"""Find every resolved version of a package in a repository and check it against a fix.

Usage:
  deps.py <repo dir> --ecosystem ECO --package NAME [--target VERSION ...] [--affected RANGE ...]

Standard library only. Python 3.9+.

Walks the repository (skipping .git, node_modules, target, vendor, dist, build
and other generated directories) and reads every lockfile for the ecosystem:

  npm       package-lock.json, npm-shrinkwrap.json, pnpm-lock.yaml, yarn.lock
            (classic and berry), bun.lock (text; binary bun.lockb is reported
            as unsupported)
  rust      Cargo.lock
  go        go.mod (require lines; "// indirect" marks a transitive dependency)
  pip       poetry.lock, uv.lock, Pipfile.lock, requirements*.txt (== pins)
            (aliases: python, pypi)
  composer  composer.lock (alias: php)

It also lists manifests that name the package directly: package.json
dependency fields, overrides and resolutions; pnpm-workspace.yaml catalogs;
Cargo.toml dependency tables; go.mod direct requires.

A resolved version is vulnerable when it falls inside any --affected range
(comparators joined by commas, e.g. ">= 1.0.0, < 1.2.2"). Without --affected,
it is vulnerable when a --target exists on its major line (0.x counts minor
as major) and it is lower, or when it is below every target line. With
neither, versions are listed and nothing is judged.

Prints JSON: package, ecosystem, lockfiles [{path, versions, vulnerable}],
manifests [{path, field, spec}], vulnerable [{path, version, needs}],
unsupported (lockfiles present that this script cannot read, e.g. bun.lockb),
ok. Exit codes: 0 when nothing resolved is vulnerable (including when the
package is absent), 1 when any resolved version is vulnerable, 2 on bad usage
or an unreadable repository.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

SKIP_DIRS = {".git", "node_modules", "target", "vendor", "dist", "build", ".next", ".turbo", ".pnpm-store",
             ".venv", "venv", "__pycache__", ".cargo", ".yarn"}
ALIASES = {"python": "pip", "pypi": "pip", "php": "composer", "cargo": "rust", "crates": "rust",
           "golang": "go", "node": "npm", "pnpm": "npm", "yarn": "npm"}
LOCKFILES = {
    "npm": ("package-lock.json", "npm-shrinkwrap.json", "pnpm-lock.yaml", "yarn.lock", "bun.lock"),
    "rust": ("Cargo.lock",),
    "go": ("go.mod",),
    "pip": ("poetry.lock", "uv.lock", "Pipfile.lock"),
    "composer": ("composer.lock",),
}
UNSUPPORTED = {"npm": ("bun.lockb",)}
MANIFESTS = {"npm": ("package.json", "pnpm-workspace.yaml"), "rust": ("Cargo.toml",), "go": ("go.mod",)}


# ---------------------------------------------------------------- versions

def version_key(version: str) -> tuple:
    v = version.strip().lstrip("vV=")
    v = v.split("+", 1)[0]
    release, _, pre = v.partition("-")
    parts = []
    for piece in release.split("."):
        m = re.match(r"\d+", piece)
        parts.append(int(m.group()) if m else 0)
    while len(parts) < 3:
        parts.append(0)
    pre_key = (1,) if not pre else (0, tuple((0, int(p)) if p.isdigit() else (1, p) for p in pre.split(".")))
    return (tuple(parts), pre_key)


def major_line(version: str) -> str:
    parts = version_key(version)[0]
    return f"0.{parts[1]}" if parts[0] == 0 else str(parts[0])


OPS = {
    "<": lambda a, b: a < b, "<=": lambda a, b: a <= b, ">": lambda a, b: a > b,
    ">=": lambda a, b: a >= b, "=": lambda a, b: a == b, "==": lambda a, b: a == b,
}


def in_range(version: str, rng: str) -> bool:
    """True when version satisfies every comparator in rng, e.g. '>= 1.0.0, < 1.2.2'."""
    comparators = re.findall(r"(<=|>=|==|=|<|>)\s*v?([0-9][^\s,]*)", rng)
    if not comparators:
        raise ValueError(f"unparseable range: {rng!r}")
    vk = version_key(version)
    return all(OPS[op](vk, version_key(bound)) for op, bound in comparators)


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

def norm(name: str, eco: str) -> str:
    name = name.strip().strip("'\"")
    return re.sub(r"[-_.]+", "-", name).lower() if eco == "pip" else name


def read_toml_packages(text: str) -> list[tuple[str, str]]:
    """[[package]] blocks with name/version keys: Cargo.lock, poetry.lock, uv.lock."""
    out = []
    for block in re.split(r"^\[\[package\]\]\s*$", text, flags=re.M)[1:]:
        name = re.search(r'^name\s*=\s*"([^"]+)"', block, re.M)
        ver = re.search(r'^version\s*=\s*"([^"]+)"', block, re.M)
        if name and ver:
            out.append((name.group(1), ver.group(1)))
    return out


def read_package_lock(text: str) -> list[tuple[str, str]]:
    data = json.loads(text)
    out = []
    for path, meta in (data.get("packages") or {}).items():
        if "node_modules/" in path and isinstance(meta, dict) and meta.get("version") and not meta.get("link"):
            out.append((path.rsplit("node_modules/", 1)[1], meta["version"]))

    def walk(deps):
        for name, meta in (deps or {}).items():
            if isinstance(meta, dict):
                if meta.get("version") and not str(meta["version"]).startswith(("file:", "link:")):
                    out.append((name, meta["version"]))
                walk(meta.get("dependencies"))
    if not data.get("packages"):
        walk(data.get("dependencies"))
    return out


PNPM_KEY = re.compile(r"""^\s{2}['"]?/?(?P<name>(?:@[^/\s'"]+/)?[^@/\s'"(]+)[@/](?P<ver>\d[^\s():'"_]*)""")


def read_pnpm_lock(text: str) -> list[tuple[str, str]]:
    out, section = [], None
    for line in text.splitlines():
        if line and not line[0].isspace():
            section = line.rstrip(":").strip()
            continue
        if section in ("packages", "snapshots"):
            m = PNPM_KEY.match(line)
            if m and line.rstrip().endswith(":"):
                out.append((m["name"], m["ver"]))
    return out


def read_yarn_lock(text: str) -> list[tuple[str, str]]:
    out, names = [], []
    for line in text.splitlines():
        if line and not line[0].isspace() and line.rstrip().endswith(":") and not line.startswith("#"):
            names = []
            for spec in line.rstrip()[:-1].split(","):
                spec = spec.strip().strip('"')
                at = spec.rfind("@")
                if at > 0:
                    names.append(spec[:at])
            continue
        m = re.match(r'^\s+version:?\s+"?([^"\s]+)"?', line)
        if m and names:
            out.extend((n, m.group(1)) for n in dict.fromkeys(names))
            names = []
    return out


BUN_ENTRY = re.compile(r'^\s+"[^"]+":\s*\[\s*"(?P<name>(?:@[^/"]+/)?[^@"]+)@(?P<ver>\d[^"]*)"', re.M)


def read_bun_lock(text: str) -> list[tuple[str, str]]:
    return [(m["name"], m["ver"]) for m in BUN_ENTRY.finditer(text)]


def read_go_mod(text: str) -> list[tuple[str, str]]:
    out = []
    for m in re.finditer(r"^\s*(?:require\s+)?([a-zA-Z0-9][\w.\-/]*\.[\w.\-/]+)\s+(v[0-9][^\s]*)", text, re.M):
        out.append((m.group(1), m.group(2)))
    return out


def read_pipfile_lock(text: str) -> list[tuple[str, str]]:
    data = json.loads(text)
    out = []
    for section in ("default", "develop"):
        for name, meta in (data.get(section) or {}).items():
            v = (meta or {}).get("version", "")
            if v.startswith("=="):
                out.append((name, v[2:]))
    return out


def read_requirements(text: str) -> list[tuple[str, str]]:
    return [(m.group(1), m.group(2)) for m in re.finditer(r"^\s*([A-Za-z0-9][\w.\-]*)(?:\[[^\]]*\])?\s*==\s*([^\s;#]+)", text, re.M)]


def read_composer_lock(text: str) -> list[tuple[str, str]]:
    data = json.loads(text)
    return [(p["name"], p["version"]) for s in ("packages", "packages-dev") for p in (data.get(s) or []) if "name" in p and "version" in p]


READERS = {
    "package-lock.json": read_package_lock, "npm-shrinkwrap.json": read_package_lock,
    "pnpm-lock.yaml": read_pnpm_lock, "yarn.lock": read_yarn_lock, "bun.lock": read_bun_lock, "Cargo.lock": read_toml_packages,
    "poetry.lock": read_toml_packages, "uv.lock": read_toml_packages, "Pipfile.lock": read_pipfile_lock,
    "go.mod": read_go_mod, "composer.lock": read_composer_lock,
}


# ---------------------------------------------------------------- manifests

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
        for m in re.finditer(rf"^\s*(?:require\s+)?{re.escape(package)}\s+(v\S+)(.*)$", text, re.M):
            if "// indirect" not in m.group(2):
                refs.append({"field": "require", "spec": m.group(1)})
    return refs


# ---------------------------------------------------------------- scan

def walk(root: Path):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".") or d == ".github")
        for f in sorted(filenames):
            yield Path(dirpath, f)


def scan(root: Path, eco: str, package: str, targets: list[str], affected: list[str]) -> dict:
    eco = ALIASES.get(eco, eco)
    if eco not in LOCKFILES:
        raise ValueError(f"unsupported ecosystem {eco!r}; supported: {', '.join(sorted(LOCKFILES))}")
    want = norm(package, eco)
    lockfiles, manifests, vulnerable, unsupported = [], [], [], []
    for path in walk(root):
        rel = str(path.relative_to(root))
        name = path.name
        is_req = eco == "pip" and re.match(r"requirements.*\.txt$", name)
        if name in LOCKFILES[eco] or is_req:
            text = path.read_text(encoding="utf-8", errors="replace")
            reader = read_requirements if is_req else READERS[name]
            try:
                entries = reader(text)
            except ValueError as exc:
                unsupported.append({"path": rel, "reason": f"unreadable: {exc}"})
                continue
            versions = sorted({v for n, v in entries if norm(n, eco) == want}, key=version_key)
            if versions:
                bad = []
                for v in versions:
                    need = judge(v, targets, affected)
                    if need is not None:
                        bad.append(v)
                        vulnerable.append({"path": rel, "version": v, "needs": need or None})
                lockfiles.append({"path": rel, "versions": versions, "vulnerable": bad})
        if name in UNSUPPORTED.get(eco, ()):
            unsupported.append({"path": rel, "reason": "lockfile format not supported; check by hand"})
        if name in MANIFESTS.get(eco, ()):
            for ref in manifest_refs(path, eco, package):
                manifests.append({"path": rel, **ref})
    return {"package": package, "ecosystem": eco, "targets": targets, "affected": affected,
            "lockfiles": lockfiles, "manifests": manifests, "vulnerable": vulnerable,
            "unsupported": unsupported, "ok": not vulnerable}


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
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
