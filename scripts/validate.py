#!/usr/bin/env python3
"""Validate repository manifests and Agent Skills without third-party packages."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins" / "company-skills"
SKILLS = PLUGIN / "skills"
NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$")
LINK_RE = re.compile(r"\[[^]]*]\(([^)]+)\)")
REQUIRED_CASES = ("Should activate", "Should not activate", "Expected behavior")
RESERVED_WORDS = ("anthropic", "claude")
XML_TAG_RE = re.compile(r"<[^>]+>")
errors: list[str] = []


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
    if portable.get("license") != "MIT":
        fail(portable_path, "license must be MIT")
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
    if not any(
        entry.get("name") == portable.get("name")
        and entry.get("source") == "./plugins/company-skills"
        for entry in claude_entries
        if isinstance(entry, dict)
    ):
        fail(claude_market_path, "must publish ./plugins/company-skills")


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
