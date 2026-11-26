#!/usr/bin/env python3
"""Check what each pinned git-subdir plugin source ships, at its pinned commit.

Claude Code refuses to update a plugin whose directory holds a plugin.json
anywhere but at .claude-plugin/plugin.json in its root ("plugin.json must be at
.claude-plugin/plugin.json at the plugin root ... found nested: ..."). A pin
that points at such a directory breaks for every user who updates it, so check
each pin before it merges. This needs network access, so it is a separate
script from validate.py.

It also checks each vendored copy in VENDORED: a plugin copied into this
repository from upstream, less the folders that broke it, must match upstream
at its recorded commit in every other file.

Usage: check_pinned_sources.py [marketplace.json ...]
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

from validate import nested_manifests


ROOT = Path(__file__).resolve().parents[1]
CATALOGS = (ROOT / ".claude-plugin" / "marketplace.json", ROOT / ".agents" / "plugins" / "marketplace.json")

# Local folder -> (url, upstream path, sha, upstream folders left out, files added here).
VENDORED = {
    "plugins/code-improver": (
        "https://github.com/trailofbits/skills.git",
        "plugins/code-improver",
        "149d7b21f4067765b82e67029730b42d228ef4b4",
        ("tests", "evals"),
        ("UPSTREAM.md", "LICENSE"),
    ),
}


def git_subdir_pins(catalog: Path) -> list[tuple[str, str, str, str]]:
    """(name, url, path, sha) for each git-subdir entry in a catalog."""
    pins = []
    for entry in json.loads(catalog.read_text()).get("plugins", []):
        source = entry.get("source")
        if isinstance(source, dict) and source.get("source") == "git-subdir":
            pins.append((entry["name"], source["url"], source["path"].removeprefix("./"), source["sha"]))
    return pins


def fetch(url: str, sha: str, path: str, into: Path) -> Path:
    """Check out only `path` of `url` at `sha` into `into`, and return that directory."""
    def git(*args: str) -> None:
        subprocess.run(["git", "-C", str(into), *args], check=True, capture_output=True, text=True)

    into.mkdir(parents=True)
    git("init", "-q")
    git("remote", "add", "origin", url)
    git("sparse-checkout", "set", "--no-cone", f"/{path}/")
    git("fetch", "-q", "--depth=1", "--filter=blob:none", "origin", sha)
    git("checkout", "-q", "FETCH_HEAD")
    return into / path


def files_under(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file() and ".git" not in path.relative_to(root).parts
    }


def vendored_differences(local: Path, upstream: Path, left_out: tuple[str, ...], added: tuple[str, ...]) -> list[str]:
    """Files that differ between a vendored copy and its upstream folder."""
    mine = {name: data for name, data in files_under(local).items() if name not in added}
    theirs = {
        name: data for name, data in files_under(upstream).items()
        if name.split("/", 1)[0] not in left_out
    }
    differences = [f"{name} is not upstream" for name in sorted(mine.keys() - theirs.keys())]
    differences += [f"{name} is missing" for name in sorted(theirs.keys() - mine.keys())]
    differences += [f"{name} differs" for name in sorted(mine.keys() & theirs.keys()) if mine[name] != theirs[name]]
    return differences


def main(argv: list[str]) -> int:
    catalogs = [Path(arg) for arg in argv] or list(CATALOGS)
    pins = sorted({pin for catalog in catalogs for pin in git_subdir_pins(catalog)})
    problems = []
    with tempfile.TemporaryDirectory() as temp:
        for number, (name, url, path, sha) in enumerate(pins):
            try:
                plugin_root = fetch(url, sha, path, Path(temp) / str(number))
            except subprocess.CalledProcessError as error:
                problems.append(f"{name}: could not fetch {path} at {sha} from {url}: {error.stderr.strip()}")
                continue
            if not plugin_root.is_dir():
                problems.append(f"{name}: {path} does not exist at {sha} in {url}")
                continue
            nested = nested_manifests(plugin_root)
            if nested:
                problems.append(
                    f"{name}: {path} at {sha} holds plugin.json below its root, which Claude Code refuses to "
                    f"install or update: {', '.join(nested)}"
                )
            else:
                print(f"ok  {name} ({path} at {sha[:12]})")
        for number, (folder, (url, path, sha, left_out, added)) in enumerate(sorted(VENDORED.items())):
            try:
                upstream = fetch(url, sha, path, Path(temp) / f"vendored-{number}")
            except subprocess.CalledProcessError as error:
                problems.append(f"{folder}: could not fetch {path} at {sha} from {url}: {error.stderr.strip()}")
                continue
            local = ROOT / folder
            for problem in nested_manifests(local):
                problems.append(f"{folder}: holds {problem} below its root, which Claude Code refuses")
            differences = vendored_differences(local, upstream, left_out, added)
            if differences:
                problems.append(
                    f"{folder}: does not match {path} at {sha} in {url} (see its UPSTREAM.md): {'; '.join(differences)}"
                )
            else:
                print(f"ok  {folder} (copy of {path} at {sha[:12]}, less {', '.join(left_out)})")
    if problems:
        print("Pinned source check failed:", file=sys.stderr)
        for problem in problems:
            print(f"- {problem}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
