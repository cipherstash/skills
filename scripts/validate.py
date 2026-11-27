#!/usr/bin/env python3
"""Validate repository manifests and Agent Skills without third-party packages."""

from __future__ import annotations

import fnmatch
import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins" / "company-skills"
SKILLS = PLUGIN / "skills"
NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$")
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
LINK_RE =re.compile(r"\[[^]]*]\(([^)]+)\)")
REQUIRED_CASES = ("Should activate", "Should not activate", "Expected behavior")
RESERVED_WORDS = ("anthropic", "claude")
XML_TAG_RE = re.compile(r"<[^>]+>")
errors: list[str] = []

# Plugins each catalog lists beside company-skills, for users to install by
# name. company-skills must not declare them as dependencies: Claude Code
# disables a plugin while a dependency is missing, and the claude.ai
# organisation sync delivers company-skills without its sibling plugins.
# Removing a bundled plugin means removing it here and from every catalog.
CODEX_BUNDLED_PLUGINS = frozenset({"differential-review", "insecure-defaults"})
CLAUDE_BUNDLED_PLUGINS = CODEX_BUNDLED_PLUGINS | frozenset(
    {"code-improver", "plugin-dev", "rust-engineer", "typescript-pro"}
)

# A skill can use another plugin's skill only as an option: within three lines
# of the reference, before or after, a sentence that names the plugin or skill
# must say what to do when it is missing, because company-skills cannot make
# Claude Code or Codex install it.
SKILL_NAME = r"[a-z0-9]+(?:-[a-z0-9]+)*"
# Backticked `<plugin>:<skill>` (optionally a /command), for any plugin.
BACKTICKED_SKILL_RE = re.compile(rf"`/?({SKILL_NAME}):({SKILL_NAME}(?:-\*)?)`")
# Unbackticked <plugin>:<skill>, only for names that are clearly plugins.
PLAIN_SKILL_RE = re.compile(rf"(?<![\w/.:-])({SKILL_NAME}):({SKILL_NAME}(?:-\*)?)(?![\w/:-])")
# Backticked forms that look like <plugin>:<skill> but are not.
NOT_SKILL_NAMESPACES = frozenset({"localhost", "http", "https", "file", "path", "npm", "pypi", "docker", "github"})
NOT_SKILL_NAMES = frozenset({"line", "col", "column", "port"})
BARE_SKILL_RE = re.compile(rf"\b(?:[Tt]he|[Aa]n?) `({SKILL_NAME}(?:-\*)?)` skills?\b")
FALLBACK_RE = re.compile(r"cannot be loaded|is not installed|is not available|is unavailable|if (?:it is |it's )?available")
FALLBACK_LINES = 3
REFERENCE_SUFFIXES = (".md", ".js", ".yaml", ".yml", ".py", ".json", ".sh", ".toml")

def fail(path: Path, message: str) -> None:
    errors.append(f"{path.relative_to(ROOT)}: {message}")


def load_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(path, f"invalid JSON: {exc}")
        return {}
    if not isinstance(value, dict):
        fail(path, "root must be an object")
        return {}
    return value


def scalar(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def parse_frontmatter(path: Path, text: str) -> dict[str, str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        fail(path, "must start with YAML frontmatter")
        return {}
    try:
        end = next(index for index, line in enumerate(lines[1:], 1) if line.strip() == "---")
    except StopIteration:
        fail(path, "frontmatter has no closing ---")
        return {}

    fields: dict[str, str] = {}
    for line in lines[1:end]:
        if not line.strip() or line.startswith((" ", "\t")):
            continue
        match = re.match(r"^([A-Za-z0-9_-]+):\s*(.+)$", line)
        if match:
            fields[match.group(1)] = scalar(match.group(2))
    if not "\n".join(lines[end + 1 :]).strip():
        fail(path, "instruction body must not be empty")
    return fields


def validate_git_subdir(path: Path, entry: dict) -> None:
    """A git-subdir entry must be pinned to a full commit so nothing auto-updates."""
    source = entry.get("source")
    if not isinstance(source, dict) or source.get("source") != "git-subdir":
        return
    name = entry.get("name")
    if not all(isinstance(source.get(field), str) and source[field].strip() for field in ("url", "path")):
        fail(path, f"{name}: git-subdir source needs url and path")
    if not isinstance(source.get("sha"), str) or not SHA_RE.fullmatch(source["sha"]):
        fail(path, f"{name}: sha must be a full 40-character lowercase commit SHA")


def git_subdir_pins(entries: list) -> dict[str, tuple]:
    """Map each git-subdir plugin name to its (url, path, sha) pin."""
    pins = {}
    for entry in entries:
        source = entry.get("source") if isinstance(entry, dict) else None
        if isinstance(source, dict) and source.get("source") == "git-subdir":
            path = source.get("path")
            if isinstance(path, str):
                path = path.removeprefix("./")
            pins[entry.get("name")] = (source.get("url"), path, source.get("sha"))
    return pins


def validate_manifests() -> None:
    portable_path = PLUGIN / "plugin.json"
    portable = load_json(portable_path)
    expected_schema = "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
    if portable.get("$schema") != expected_schema:
        fail(portable_path, f"$schema must be {expected_schema}")
    if portable.get("name") != PLUGIN.name:
        fail(portable_path, "name must match the plugin directory")
    if not SEMVER_RE.fullmatch(str(portable.get("version", ""))):
        fail(portable_path, "version must be semantic versioning")
    expected_license = "MIT AND Apache-2.0 AND OGL-UK-3.0"
    if portable.get("license") != expected_license:
        fail(portable_path, f"license must be {expected_license}")
    author = portable.get("author")
    if (
        not isinstance(author, dict)
        or not isinstance(author.get("name"), str)
        or not author["name"].strip()
    ):
        fail(portable_path, "author.name is required")
    if not isinstance(portable.get("description"), str) or not portable["description"].strip():
        fail(portable_path, "description is required")

    for relative in (".codex-plugin/plugin.json", ".claude-plugin/plugin.json"):
        path = PLUGIN / relative
        manifest = load_json(path)
        for field in ("name", "version", "description", "license", "author"):
            if manifest.get(field) != portable.get(field):
                fail(path, f"{field} must match plugin.json")
        if relative == ".codex-plugin/plugin.json" and manifest.get("skills") != "./skills/":
            fail(path, "skills must be ./skills/ (relative to the plugin root)")

    if not SKILLS.is_dir():
        fail(SKILLS, "shared skills directory is required")

    # A portable OpenAI extension overrides the compatibility fallback. This
    # repository keeps its OpenAI settings in the latter, so reject a shadow.
    extensions = portable.get("extensions", {})
    if isinstance(extensions, dict) and "com.openai" in extensions:
        fail(portable_path, "keep OpenAI settings in .codex-plugin/plugin.json; com.openai would override it")

    codex_market_path = ROOT / ".agents" / "plugins" / "marketplace.json"
    codex_market = load_json(codex_market_path)
    if codex_market.get("name") != "company":
        fail(codex_market_path, "name must be company (the documented install selector)")
    interface = codex_market.get("interface", {})
    if (
        not isinstance(interface, dict)
        or not isinstance(interface.get("displayName"), str)
        or not interface["displayName"].strip()
    ):
        fail(codex_market_path, "interface.displayName is required")
    codex_entries = codex_market.get("plugins", [])
    if not isinstance(codex_entries, list):
        fail(codex_market_path, "plugins must be an array")
        codex_entries = []
    for entry in codex_entries:
        if not isinstance(entry, dict):
            fail(codex_market_path, "each plugin entry must be an object")
            continue
        policy = entry.get("policy", {})
        if (
            not isinstance(policy, dict)
            or policy.get("installation") != "AVAILABLE"
            or policy.get("authentication") != "ON_INSTALL"
        ):
            fail(codex_market_path, "plugin policy must use AVAILABLE installation and ON_INSTALL authentication")
        if entry.get("category") != "Productivity":
            fail(codex_market_path, "plugin category must be Productivity")
        validate_git_subdir(codex_market_path, entry)
    if not any(
        entry.get("name") == portable.get("name")
        and entry.get("source", {}).get("source") == "local"
        and entry.get("source", {}).get("path") == "./plugins/company-skills"
        for entry in codex_entries
        if isinstance(entry, dict) and isinstance(entry.get("source"), dict)
    ):
        fail(codex_market_path, "must publish ./plugins/company-skills")

    claude_market_path = ROOT / ".claude-plugin" / "marketplace.json"
    claude_market = load_json(claude_market_path)
    if claude_market.get("name") != "company":
        fail(claude_market_path, "name must be company (the documented install selector)")
    claude_entries = claude_market.get("plugins", [])
    if not isinstance(claude_entries, list):
        fail(claude_market_path, "plugins must be an array")
        claude_entries = []
    for entry in claude_entries:
        if isinstance(entry, dict):
            validate_git_subdir(claude_market_path, entry)
    if not any(
        entry.get("name") == portable.get("name")
        and entry.get("source") == "./plugins/company-skills"
        for entry in claude_entries
        if isinstance(entry, dict)
    ):
        fail(claude_market_path, "must publish ./plugins/company-skills")

    for manifest_path in (PLUGIN / "plugin.json", PLUGIN / ".codex-plugin" / "plugin.json", PLUGIN / ".claude-plugin" / "plugin.json"):
        if "dependencies" in load_json(manifest_path):
            fail(
                manifest_path,
                "must not declare dependencies: Claude Code disables company-skills when a synced copy lacks them",
            )
    # Any catalog entry not in its bundled list, or listed plugin missing from
    # its catalog, is a half-finished addition or removal: update the list and
    # every catalog together. A catalog that did not parse has already failed,
    # so skip it rather than report every listed plugin as missing.
    for path, market, entries, bundled in (
        (claude_market_path, claude_market, claude_entries, CLAUDE_BUNDLED_PLUGINS),
        (codex_market_path, codex_market, codex_entries, CODEX_BUNDLED_PLUGINS),
    ):
        if not isinstance(market.get("plugins"), list):
            continue
        listed = {entry.get("name") for entry in entries if isinstance(entry, dict)}
        for name in sorted(listed - bundled - {portable.get("name")}, key=str):
            fail(path, f"{name}: a bundled plugin in the catalog must be listed in validate.py")
        for name in sorted(bundled - listed):
            fail(path, f"{name}: listed in validate.py as bundled but missing from the catalog")

    claude_pins = git_subdir_pins(claude_entries)
    codex_pins = git_subdir_pins(codex_entries)
    # The Claude catalog may list plugins the Codex catalog does not; a plugin
    # the Codex catalog lists must carry the Claude catalog's pin.
    for name in sorted(codex_pins, key=str):
        if claude_pins.get(name) != codex_pins[name]:
            fail(claude_market_path, f"{name}: git-subdir pin must match in both marketplace catalogs")


def validate_cases(skill: Path) -> None:
    path = skill / "tests" / "prompts.md"
    if not path.is_file():
        fail(path, "is required for behavior testing")
        return
    text = path.read_text(encoding="utf-8")
    for index, heading in enumerate(REQUIRED_CASES):
        match = re.search(rf"(?m)^## {re.escape(heading)}\s*$", text)
        if not match:
            fail(path, f"missing '## {heading}'")
            continue
        next_heading = re.search(r"(?m)^## ", text[match.end() :])
        end = match.end() + next_heading.start() if next_heading else len(text)
        if not re.search(r"(?m)^- \S", text[match.end() : end]):
            fail(path, f"'## {heading}' needs at least one case")


def validate_skill(skill: Path) -> None:
    path = skill / "SKILL.md"
    if not path.is_file():
        fail(path, "is required")
        return
    text = path.read_text(encoding="utf-8")
    fields = parse_frontmatter(path, text)
    name = fields.get("name", "")
    description = fields.get("description", "")
    if name != skill.name:
        fail(path, "frontmatter name must match the directory")
    if not 1 <= len(name) <= 64 or not NAME_RE.fullmatch(name):
        fail(path, "name must be 1-64 lowercase letters, digits, and single hyphens")
    if any(word in name for word in RESERVED_WORDS):
        fail(path, "name must not contain reserved words: " + ", ".join(RESERVED_WORDS))
    if not 1 <= len(description) <= 1024:
        fail(path, "description must be 1-1024 characters")
    if XML_TAG_RE.search(name) or XML_TAG_RE.search(description):
        fail(path, "name and description must not contain XML tags")
    if len(text.splitlines()) > 500:
        fail(path, "SKILL.md must stay at or below 500 lines")
    if "[TODO:" in text:
        fail(path, "contains an unfinished scaffold placeholder")

    for target in LINK_RE.findall(text):
        target = target.split("#", 1)[0]
        if not target or "://" in target or target.startswith(("#", "mailto:")):
            continue
        resolved = (skill / target).resolve()
        try:
            resolved.relative_to(skill.resolve())
        except ValueError:
            fail(path, f"reference escapes the skill directory: {target}")
            continue
        if not resolved.exists():
            fail(path, f"reference does not exist: {target}")
    validate_cases(skill)


def is_plugin_namespace(name: str) -> bool:
    return name == "company-skills" or name in CLAUDE_BUNDLED_PLUGINS or name.endswith("-skills")


def skill_references(line: str) -> set[tuple[str, str]]:
    found = {
        (plugin, name)
        for plugin, name in BACKTICKED_SKILL_RE.findall(line)
        if plugin not in NOT_SKILL_NAMESPACES and name not in NOT_SKILL_NAMES and not name.isdigit()
    }
    found |= {(plugin, name) for plugin, name in PLAIN_SKILL_RE.findall(line) if is_plugin_namespace(plugin)}
    return found


def has_fallback(lines: list[str], number: int, plugin: str, name: str) -> bool:
    window = lines[max(0, number - FALLBACK_LINES) : number + 1 + FALLBACK_LINES]
    # The fallback and the plugin or skill name must share a sentence, so an
    # unrelated "is not available" next to the reference does not count.
    return any(
        FALLBACK_RE.search(sentence.lower()) and (plugin in sentence or f":{name}" in sentence)
        for line in window
        for sentence in re.split(r"(?<=[.;])\s+", line)
    )


def validate_skill_references(skills: list[Path]) -> None:
    """Fail on a reference to a skill company-skills does not ship, unless it is
    a `<plugin>:<skill>` reference to another plugin's skill with a fallback."""
    shipped = {skill.name for skill in skills}
    for skill in skills:
        for path in sorted(skill.rglob("*")):
            if not path.is_file() or path.suffix not in REFERENCE_SUFFIXES:
                continue
            if "tests" in path.relative_to(skill).parts:
                continue  # behaviour cases describe hosts and prompts, not instructions
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
            for number, line in enumerate(lines):
                for plugin, name in sorted(skill_references(line)):
                    if plugin == "company-skills":
                        if not fnmatch.filter(shipped, name):
                            fail(path, f"line {number + 1}: company-skills does not ship `{name}`")
                    elif not has_fallback(lines, number, plugin, name):
                        fail(
                            path,
                            f"line {number + 1}: `{plugin}:{name}` is another plugin's skill; within "
                            f"{FALLBACK_LINES} lines, a sentence naming it must say what to do when it cannot be loaded",
                        )
                for name in BARE_SKILL_RE.findall(line):
                    if not fnmatch.filter(shipped, name):
                        fail(
                            path,
                            f"line {number + 1}: `{name}` is not a company-skills skill; name it as "
                            "`<plugin>:<skill>` with a fallback",
                        )


def main() -> int:
    errors.clear()
    validate_manifests()
    skills = (
        sorted(path for path in SKILLS.iterdir() if path.is_dir() and not path.name.startswith("."))
        if SKILLS.is_dir() else []
    )
    if SKILLS.is_dir() and not skills:
        fail(SKILLS, "must contain at least one skill")
    for skill in skills:
        validate_skill(skill)
    validate_skill_references(skills)
    if errors:
        print("Validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    count = len(skills)
    print(f"Validation passed ({count} skill{'s' if count != 1 else ''}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
