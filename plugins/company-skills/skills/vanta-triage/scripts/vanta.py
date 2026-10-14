#!/usr/bin/env python3
"""Fetch open Vanta vulnerabilities, group them into issues, and reconcile with Linear.

Usage:
  vanta.py fetch [--out FILE]
  vanta.py plan --findings FILE --issues FILE [FILE ...] [--config FILE] [--today YYYY-MM-DD]

Standard library only. Python 3.9+.

fetch
  Authenticates with the Vanta API (OAuth client credentials, read scope) and
  writes every active vulnerability, joined to its vulnerable asset, as
  normalised findings JSON. Credentials come from VANTA_CLIENT_ID and
  VANTA_CLIENT_SECRET, or from the JSON file named by VANTA_ENV_FILE with
  client_id and client_secret keys. Exits 1 on a missing credential or an
  API error, with the reason on stderr.

  Each finding:
    id, advisory (CVE or GHSA), severity (CRITICAL|HIGH|MEDIUM|LOW), cvss,
    kind ("dependency" from GitHub/Dependabot, "container" from AWS
    Inspector), target (owner/repo for dependency, image name for
    container), repo (owner/repo for dependency; for container, the source
    repo from the config's images map, or null), ecosystem (npm, rust, go,
    ...; "os" for container), package, affected (version range; the
    installed version for container), fixed_version (null when Vanta has
    none), sla (YYYY-MM-DD), detected (YYYY-MM-DD), url (Dependabot alert
    or Inspector finding), advisory_url, summary (first sentence of the
    description).

plan
  Reads findings (from fetch) and the Linear issues in the tracking
  project, and prints one JSON document:
    groups   one entry per issue Vanta findings call for. Dependency
             findings group by (repo, ecosystem, package); container
             findings group by (source repo, package) across every image
             built from that repo — one base-image fix clears them all —
             or by (image, package) when the image is not in the config. Each carries key, kind
             (remediate | track-upstream | assess-container), severity,
             priority (Linear 1-4), sla, images (container only), targets (highest fixed version
             per major line), advisories, title, description (Markdown),
             match (the open Linear issue it maps to, or null).
    actions  create | retarget | resolve | keep | await-rescan, one per
             group or unmatched open issue, each with the reason. Each open
             issue serves at most one group. A retarget or keep whose issue
             was matched by title alone and also fits other groups carries
             ambiguous: [group keys]; the issue's description (with its
             "Vanta key:" line) settles it.
             await-rescan replaces create when a matching issue was closed
             as Done within --rescan-days (default 7) of --today and its
             version covers the targets: Vanta has not rescanned yet.
    unparsed open Linear issues whose title is not a recognised Vanta
             package title, left untouched.

  --issues takes one or more files, each a JSON array (or an object with an
  "issues" array, as the Linear connector returns it) of Linear
  issues with id or identifier, title, status or state (a string or an
  object with name and type), and optionally statusType, description and
  completedAt. An issue whose state type is completed (or named Done) is done,
  canceled (or named Canceled or Duplicate) is ignored, and anything else is
  open. A description line "Vanta key: `<key>`" takes precedence over the
  title for matching. An id listed more than once is merged, keeping any
  description, so a get_issue result can be added to a list result.

  Exits 2 on bad usage or unreadable input.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://api.vanta.com"
SCOPE = "vanta-api.all:read"
SEVERITY_RANK = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}
PRIORITY = {"CRITICAL": 1, "HIGH": 2, "MEDIUM": 3, "LOW": 4}
DONE_STATES = {"done", "completed"}
CANCELED_STATES = {"canceled", "cancelled", "duplicate"}
NO_FIX = {None, "", "notavailable", "none", "n/a"}
DEFAULT_CONFIG = Path(__file__).resolve().parent.parent / "references" / "config.json"

DEPENDABOT_RE = re.compile(r"^https://github\.com/(?P<repo>[^/]+/[^/]+)/security/dependabot/\d+")
PACKAGE_RE = re.compile(r"^(?P<eco>[a-z0-9]+)-(?P<pkg>\S+?)(?:\s+(?P<range>[<>=!~^].*))?$")
OS_PACKAGE_RE = re.compile(r"^(?P<pkg>[^:\s]+):(?P<ver>\S+)$")
KEY_LINE_RE = re.compile(r"Vanta key:\s*`([^`]+)`")
TITLE_RES = [
    ("remediate", re.compile(r"^\[Vanta\] Remediate (?P<pkg>[^\s\"]+) to (?P<ver>.+?) \((?P<where>[^()]+)\)\s*$")),
    ("track-upstream", re.compile(r"^\[Vanta\] Track upstream fix for (?P<pkg>\S+) \((?P<where>[^()]+)\)\s*$")),
    ("assess", re.compile(r"^\[Vanta\] Assess (?P<pkg>\S+)\b.*\((?P<where>[^()]+?)(?: image)?\)\s*$")),
]


# ---------------------------------------------------------------- versions

PY_SUFFIX = re.compile(
    r"^(?:[-_.]?(?P<pre>a|alpha|b|beta|c|rc|pre|preview)[-_.]?(?P<pre_n>\d*))?"
    r"(?:[-_.]?(?:post|rev|r)[-_.]?(?P<post>\d*))?"
    r"(?:[-_.]?(?P<dev>dev)[-_.]?(?P<dev_n>\d*))?$", re.I)
PY_PRE = {"a": "a", "alpha": "a", "b": "b", "beta": "b"}


def version_key(version: str) -> tuple:
    """Order versions: numeric release parts, then pre-release, post-release, and dev-release.

    A `-` suffix is a semver pre-release (1.2.3-rc.1); a dashless suffix is read as PEP 440
    (1.2.3rc1, 1.2.3.post1, 1.2.3.dev1). Any other suffix is ignored."""
    v = version.strip().lstrip("vV=")
    v = v.split("+", 1)[0]
    if ":" in v and v.split(":", 1)[0].isdigit():  # Debian epoch
        v = v.split(":", 1)[1]
    m = re.match(r"(\d+(?:\.\d+)*)(.*)$", v)
    py = PY_SUFFIX.match(m.group(2)) if m and m.group(2) and not m.group(2).startswith("-") else None
    pre_key, post_key, dev_key = (1,), (-1,), (1,)
    if py and (py["pre"] or py["post"] is not None or py["dev"]):
        parts = [int(p) for p in m.group(1).split(".")]
        if py["pre"]:
            label = PY_PRE.get(py["pre"].lower(), "rc")
            pre_key = (0, ((1, label), (0, int(py["pre_n"] or 0))))
        elif py["dev"] and py["post"] is None:
            pre_key = (-1,)  # 1.2.3.dev1 precedes every 1.2.3 pre-release
        if py["post"] is not None:
            post_key = (int(py["post"] or 0),)
        if py["dev"]:
            dev_key = (0, int(py["dev_n"] or 0))
    else:
        release, _, pre = v.partition("-")
        parts = []
        for piece in release.split("."):
            d = re.match(r"\d+", piece)
            parts.append(int(d.group()) if d else 0)
        if pre:
            pre_key = (0, tuple((0, int(p)) if p.isdigit() else (1, p) for p in pre.split(".")))
    while len(parts) > 3 and parts[-1] == 0:
        parts.pop()
    while len(parts) < 3:
        parts.append(0)
    return (tuple(parts), pre_key, post_key, dev_key)


def major_line(version: str) -> str:
    """The compatibility line a version belongs to: major, or 0.minor for 0.x."""
    parts = version_key(version)[0]
    return f"0.{parts[1]}" if parts[0] == 0 else str(parts[0])


def max_per_line(versions) -> list[str]:
    best: dict[str, str] = {}
    for v in versions:
        line = major_line(v)
        if line not in best or version_key(v) > version_key(best[line]):
            best[line] = v
    return sorted(best.values(), key=version_key, reverse=True)


# ---------------------------------------------------------------- fetch

def load_credentials() -> tuple[str, str]:
    cid, secret = os.environ.get("VANTA_CLIENT_ID"), os.environ.get("VANTA_CLIENT_SECRET")
    if cid and secret:
        return cid, secret
    env_file = os.environ.get("VANTA_ENV_FILE")
    if env_file:
        try:
            data = json.loads(Path(env_file).read_text())
            return data["client_id"], data["client_secret"]
        except (OSError, ValueError, KeyError) as exc:
            raise SystemExit(f"error: cannot read client_id/client_secret from VANTA_ENV_FILE={env_file}: {exc}")
    raise SystemExit("error: set VANTA_CLIENT_ID and VANTA_CLIENT_SECRET (or VANTA_ENV_FILE)")


def http_json(req: urllib.request.Request) -> dict:
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            # Vanta descriptions can carry raw control characters; strict=False accepts them.
            return json.loads(resp.read().decode("utf-8"), strict=False)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")[:500]
        raise SystemExit(f"error: {req.get_method()} {req.full_url} -> HTTP {exc.code}: {body}")
    except urllib.error.URLError as exc:
        raise SystemExit(f"error: {req.full_url}: {exc.reason} (is api.vanta.com allowed by the network policy?)")


def token() -> str:
    cid, secret = load_credentials()
    body = json.dumps({"client_id": cid, "client_secret": secret, "grant_type": "client_credentials", "scope": SCOPE})
    req = urllib.request.Request(f"{API}/oauth/token", data=body.encode(), headers={"Content-Type": "application/json"})
    return http_json(req)["access_token"]


def get_all(path: str, bearer: str) -> list[dict]:
    out, cursor = [], None
    while True:
        params = {"pageSize": 100}
        if cursor:
            params["pageCursor"] = cursor
        req = urllib.request.Request(f"{API}{path}?{urllib.parse.urlencode(params)}", headers={"Authorization": f"Bearer {bearer}"})
        results = http_json(req)["results"]
        out.extend(results["data"])
        if not results["pageInfo"].get("hasNextPage"):
            return out
        cursor = results["pageInfo"]["endCursor"]


def first_sentence(text: str | None) -> str:
    text = " ".join((text or "").split())
    m = re.match(r"(.{20,300}?[.!?])(\s|$)", text)
    return m.group(1) if m else text[:300]


def advisory_url(vuln: dict) -> str | None:
    urls = vuln.get("relatedUrls") or []
    for u in urls:
        if "github.com/advisories/GHSA-" in u:
            return u
    return urls[0] if urls else None


def normalise(vuln: dict, assets: dict, config: dict) -> dict:
    asset = assets.get(vuln.get("targetId")) or {}
    ident = (vuln.get("packageIdentifier") or "").strip()
    fixed = vuln.get("fixedVersion")
    fixed = None if (fixed or "").strip().lower() in NO_FIX else fixed.strip()
    finding = {
        "id": vuln["id"],
        "advisory": vuln.get("name") or f"Vanta finding {vuln['id']}",
        "severity": (vuln.get("severity") or "MEDIUM").upper(),
        "cvss": vuln.get("cvssSeverityScore"),
        "fixed_version": fixed,
        "sla": (vuln.get("remediateByDate") or "")[:10] or None,
        "detected": (vuln.get("firstDetectedDate") or "")[:10] or None,
        "url": vuln.get("externalURL"),
        "advisory_url": advisory_url(vuln),
        "summary": first_sentence(vuln.get("description")),
    }
    dependabot = DEPENDABOT_RE.match(vuln.get("externalURL") or "")
    m = PACKAGE_RE.match(ident)
    if dependabot and m:
        finding.update(kind="dependency", target=dependabot["repo"], repo=dependabot["repo"],
                       ecosystem=m["eco"], package=m["pkg"], affected=(m["range"] or "").strip() or None)
        return finding
    image = asset.get("name") or vuln.get("externalId") or "unknown"
    os_pkg = OS_PACKAGE_RE.match(ident)
    container = asset.get("assetType") == "CONTAINER_REPOSITORY" or bool(os_pkg)
    repo = dependabot["repo"] if dependabot and not container else (config.get("images", {}).get(image) or {}).get("repo")
    finding.update(kind="container" if container else "dependency",
                   target=dependabot["repo"] if dependabot and not container else image, repo=repo,
                   ecosystem="os" if os_pkg else (m["eco"] if m else "unknown"),
                   package=os_pkg["pkg"] if os_pkg else (m["pkg"] if m else ident or "unknown"),
                   affected=os_pkg["ver"] if os_pkg else (m["range"] if m else None))
    return finding


def cmd_fetch(args) -> int:
    config = load_config(args.config)
    bearer = token()
    vulns = get_all("/v1/vulnerabilities", bearer)
    assets = {a["id"]: a for a in get_all("/v1/vulnerable-assets", bearer)}
    findings = [normalise(v, assets, config) for v in vulns if not v.get("deactivateMetadata")]
    text = json.dumps(findings, indent=2)
    if args.out:
        Path(args.out).write_text(text + "\n")
        print(f"{len(findings)} findings written to {args.out}", file=sys.stderr)
    else:
        print(text)
    return 0


# ---------------------------------------------------------------- plan

def load_config(path: str | None) -> dict:
    p = Path(path) if path else DEFAULT_CONFIG
    try:
        return json.loads(p.read_text())
    except FileNotFoundError:
        if path:
            raise SystemExit(f"error: config not found: {path}")
        return {}
    except ValueError as exc:
        raise SystemExit(f"error: invalid config {p}: {exc}")


def short(repo: str) -> str:
    return repo.split("/")[-1]


def place(g: dict) -> str:
    """Where a dependency group lives: the repo's short name, or the Vanta asset name when the repo is unknown."""
    return short(g["repo"]) if g["repo"] else g["target"]


def group_key(f: dict) -> str:
    """Keeps the package's spelling (Go module paths are case-sensitive); compare keys with same_key()."""
    if f["kind"] == "container":
        return f"container:{f['repo'] or f['target']}:{f['package']}"
    return f"dependency:{f['repo'] or f['target']}:{f['ecosystem']}:{f['package']}"


def same_key(a: str, b: str) -> bool:
    return a.lower() == b.lower()


def group_findings(findings: list[dict]) -> list[dict]:
    buckets: dict[str, list[dict]] = {}
    for f in findings:
        buckets.setdefault(group_key(f).lower(), []).append(f)
    groups = []
    for items in buckets.values():
        first = items[0]
        key = group_key(first)
        severity = max((f["severity"] for f in items), key=lambda s: SEVERITY_RANK.get(s, 0))
        fixes = [f["fixed_version"] for f in items if f["fixed_version"]]
        unfixed = [f for f in items if not f["fixed_version"]]
        if first["kind"] == "container":
            kind = "assess-container"
        elif fixes:
            kind = "remediate"
        else:
            kind = "track-upstream"
        advisories: dict[tuple, dict] = {}
        for f in items:  # one row per advisory and affected range: an advisory can span several version lines
            a = advisories.setdefault((f["advisory"], f["affected"]), {"id": f["advisory"], "url": f["advisory_url"], "cvss": f["cvss"],
                                                     "fixed_version": f["fixed_version"], "affected": f["affected"],
                                                     "summary": f["summary"], "findings": []})
            if f["url"] and f["url"] not in a["findings"]:
                a["findings"].append(f["url"])
        slas = sorted(f["sla"] for f in items if f["sla"])
        groups.append({
            "key": key, "kind": kind, "target": first["target"], "repo": first["repo"],
            "ecosystem": first["ecosystem"], "package": first["package"], "severity": severity,
            "priority": PRIORITY.get(severity, 3), "sla": slas[0] if slas else None,
            "targets": max_per_line(fixes), "unfixed_advisories": sorted({f["advisory"] for f in unfixed}),
            "advisories": sorted(advisories.values(), key=lambda a: -(a["cvss"] or 0)),
            "finding_count": len(items),
            "images": sorted({f["target"] for f in items}) if first["kind"] == "container" else [],
        })
    groups.sort(key=lambda g: (g["priority"], g["sla"] or "9999", g["key"]))
    for g in groups:
        g["title"] = render_title(g)
        g["description"] = render_description(g)
    return groups


def where(g: dict) -> str:
    if g["kind"] == "assess-container":
        return " + ".join(g["images"]) + (" images" if len(g["images"]) > 1 else " image")
    return place(g)


def render_title(g: dict) -> str:
    if g["kind"] == "remediate":
        return f"[Vanta] Remediate {g['package']} to {' / '.join(g['targets'])} ({where(g)})"
    if g["kind"] == "track-upstream":
        return f"[Vanta] Track upstream fix for {g['package']} ({where(g)})"
    unique = list(dict.fromkeys(a["id"] for a in g["advisories"]))
    ids = ", ".join(unique[:3]) + (" …" if len(unique) > 3 else "")
    return f"[Vanta] Assess {g['package']} {ids} ({where(g)})"


def render_description(g: dict) -> str:
    sev = g["severity"].title()
    lines = ["## Vulnerability", ""]
    if g["kind"] == "assess-container":
        lines += [f"**Package:** `{g['package']}` {g['advisories'][0]['affected'] or ''} (OS package)".rstrip(),
                  "**Images:** " + ", ".join(f"`{i}`" for i in g["images"])
                  + (f", built from `{g['repo']}`" if g["repo"] else ", source repo unknown")]
    else:
        lines += [f"**Package:** `{g['package']}` ({g['ecosystem']})",
                  f"**Repo:** `{g['repo']}`" if g["repo"] else f"**Asset:** `{g['target']}` (source repo unknown)"]
    if g["targets"]:
        lines.append("**Fix version:** " + " / ".join(f"`>= {t}`" for t in g["targets"]))
    else:
        lines.append("**Fix version:** none available from Vanta")
    lines += [f"**Severity:** {sev}" + (f", Vanta SLA {g['sla']}" if g["sla"] else ""), "",
              "### Advisories", "", "| Advisory | CVSS | Affected | Fixed in | Vanta findings |", "| -- | -- | -- | -- | -- |"]
    for a in g["advisories"]:
        ghsa = re.search(r"GHSA(-[0-9a-z]{4}){3}", a["url"] or "")
        label = f"{a['id']} / {ghsa.group()}" if ghsa and ghsa.group() != a["id"] else a["id"]
        link = f"[{label}](<{a['url']}>)" if a["url"] else label
        finds = " ".join(f"[{i + 1}](<{u}>)" for i, u in enumerate(a["findings"])) or "n/a"
        affected = f"`{a['affected']}`" if a["affected"] else "n/a"
        lines.append(f"| {link} | {a['cvss'] if a['cvss'] is not None else 'n/a'} | {affected} | {a['fixed_version'] or 'none'} | {finds} |")
    lines += ["", "## Action", ""]
    if g["kind"] == "remediate":
        lines.append(f"Bump `{g['package']}` to " + " / ".join(f"`>= {t}`" for t in g["targets"])
                     + " in every lockfile location that resolves a vulnerable version.")
        if g["unfixed_advisories"]:
            lines += ["", "Advisories with no fixed version yet: " + ", ".join(g["unfixed_advisories"]) + "."]
    elif g["kind"] == "track-upstream":
        lines.append(f"No patched `{g['package']}` release exists. Watch the advisory for a fix, check whether the "
                     "vulnerable code path is reachable, and remove the dependency path or record a risk acceptance in "
                     "Vanta if no fix lands before the SLA.")
    else:
        lines.append("Check whether the distribution has a fixed or staged package version, whether the vulnerable "
                     "code is present and reachable in this image, and whether a base-image refresh or Dockerfile "
                     "change clears it. Record a not-affected determination in Vanta where the code is absent.")
    lines += ["", f"Vanta key: `{g['key']}`"]
    return "\n".join(lines)


def issue_fields(issue: dict) -> tuple[str, str, str, str, str]:
    """(id, title, state name, state class, description); class is open, done or canceled."""
    ident = issue.get("identifier") or issue.get("id") or ""
    state = issue.get("status") or issue.get("state") or ""
    stype = issue.get("statusType") or ""
    if isinstance(state, dict):
        stype = stype or state.get("type") or ""
        state = state.get("name") or state.get("type") or ""
    name, stype = str(state).lower(), str(stype).lower()
    if stype == "completed" or (not stype and name in DONE_STATES):
        cls = "done"
    elif stype == "canceled" or (not stype and name in CANCELED_STATES):
        cls = "canceled"
    else:
        cls = "open"
    return ident, issue.get("title") or "", str(state), cls, issue.get("description") or ""


def parse_issue(title: str, description: str) -> dict | None:
    """Recover (kind, package, where, version) from a Vanta issue, or None if it is not a package issue."""
    m = KEY_LINE_RE.search(description)
    if m:
        parts = m.group(1).split(":")
        if parts[0] == "container" and len(parts) >= 3:
            return {"key": m.group(1), "package": parts[2], "where": {short(parts[1])}, "versions": parse_versions(title)}
        if parts[0] == "dependency" and len(parts) >= 4:
            return {"key": m.group(1), "package": parts[3], "where": {short(parts[1])}, "versions": parse_versions(title)}
    for kind, rx in TITLE_RES:
        t = rx.match(title)
        if not t:
            continue
        return {"key": None, "package": t["pkg"].lower(), "where": parse_where(t["where"]), "versions": parse_versions(title)}
    return None


def parse_where(text: str) -> set[str]:
    """'stack' -> {'stack'}; 'zerokms + cts images' -> {'zerokms', 'cts'}."""
    text = re.sub(r"\s+images?$", "", text.strip().lower())
    return {w for w in re.split(r"\s*(?:\+|,|&|\band\b)\s*", text) if w}


def parse_versions(title: str) -> list[str]:
    m = re.search(r" to (?:>=\s*)?(.+?) \(", title)
    if not m:
        return []
    return [v.strip().lstrip(">= ") for v in m.group(1).split("/") if re.match(r"\s*(>=\s*)?v?\d", v)]


def covers(have: list[str], need: list[str]) -> bool:
    """True when every needed version is met by an existing target on the same major line."""
    for n in need:
        same = [h for h in have if major_line(h) == major_line(n)]
        if not same or max(version_key(h) for h in same) < version_key(n):
            return False
    return True


def matches(g: dict, parsed: dict) -> bool:
    if parsed["key"]:
        return same_key(parsed["key"], g["key"])
    if parsed["package"] != g["package"].lower():
        return False
    if g["kind"] == "assess-container":
        places = {i.lower() for i in g["images"]} | ({short(g["repo"]).lower()} if g["repo"] else set())
        return bool(parsed["where"] & places)
    return place(g).lower() in parsed["where"]


def cmd_plan(args) -> int:
    try:
        findings = json.loads(Path(args.findings).read_text())
        issues = []
        for path in args.issues:
            data = json.loads(Path(path).read_text())
            if isinstance(data, dict):
                data = data.get("issues") or data.get("nodes") or []
            issues.extend(data)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    config = load_config(args.config)
    for f in findings:  # re-apply the image map so config edits take effect without a re-fetch
        if f.get("kind") == "container" and not f.get("repo"):
            f["repo"] = (config.get("images", {}).get(f["target"]) or {}).get("repo")
    groups = group_findings(findings)
    merged: dict[str, dict] = {}
    for issue in issues:
        ident = issue.get("identifier") or issue.get("id") or ""
        prev = merged.get(ident)
        merged[ident] = {**prev, **{k: v for k, v in issue.items() if v not in (None, "")}} if prev else issue
    issues = list(merged.values())

    today = dt.date.fromisoformat(args.today) if args.today else dt.date.today()
    open_issues, recent_done, unparsed = [], [], []
    for issue in issues:
        ident, title, state, cls, desc = issue_fields(issue)
        if not title.startswith("[Vanta]") or cls == "canceled":
            continue
        if cls == "done":
            done = (issue.get("completedAt") or "")[:10]
            if done and (today - dt.date.fromisoformat(done)).days <= args.rescan_days:
                parsed = parse_issue(title, desc)
                if parsed:
                    recent_done.append({"id": ident, "title": title, "state": state, "completed": done, **parsed})
            continue
        parsed = parse_issue(title, desc)
        if parsed is None:
            unparsed.append({"id": ident, "title": title, "state": state})
        else:
            open_issues.append({"id": ident, "title": title, "state": state, **parsed})

    # Each open issue serves one group. Claim in rounds so a weak title match never takes an issue
    # that another group fits better: key line first, then titles whose versions cover the targets, then any match.
    fits = {g["key"]: [i for i in open_issues if matches(g, i)] for g in groups}
    claimed: dict[str, dict] = {}
    owner: dict[str, str] = {}
    rounds = (lambda g, i: bool(i["key"]),
              lambda g, i: g["kind"] != "remediate" or covers(i["versions"], g["targets"]),
              lambda g, i: True)
    for ok in rounds:
        for g in groups:
            if g["key"] in claimed:
                continue
            pick = next((i for i in fits[g["key"]] if i["id"] not in owner and ok(g, i)), None)
            if pick:
                claimed[g["key"]], owner[pick["id"]] = pick, g["key"]
    actions, used = [], set(owner)
    for g in groups:
        chosen = claimed.get(g["key"])
        g["match"] = {"id": chosen["id"], "title": chosen["title"], "state": chosen["state"]} if chosen else None
        dups = [i["id"] for i in fits[g["key"]] if i["id"] not in owner
                and all(i not in fits[o["key"]] for o in groups if o is not g)]
        if dups:
            g["duplicates"] = dups
            used.update(dups)
        ambiguous = sorted(o["key"] for o in groups if chosen and not chosen["key"] and chosen in fits[o["key"]])
        closed = [i for i in recent_done if matches(g, i) and (g["kind"] != "remediate" or covers(i["versions"], g["targets"]))]
        if chosen is None and closed:
            actions.append({"action": "await-rescan", "key": g["key"], "issue": closed[0]["id"],
                            "reason": f"{closed[0]['id']} closed {closed[0]['completed']} with a covering fix; "
                                      "Vanta has not rescanned yet"})
        elif chosen is None:
            actions.append({"action": "create", "key": g["key"], "title": g["title"],
                            "reason": f"{g['finding_count']} open finding(s), no open Linear issue"})
        elif g["kind"] == "remediate" and chosen["title"].startswith("[Vanta] Track upstream fix"):
            actions.append({"action": "retarget", "key": g["key"], "issue": chosen["id"], "title": g["title"],
                            "reason": f"a fix is now available: {' / '.join(g['targets'])}"})
        elif g["kind"] == "remediate" and not covers(chosen["versions"], g["targets"]):
            actions.append({"action": "retarget", "key": g["key"], "issue": chosen["id"], "title": g["title"],
                            "reason": f"issue targets {' / '.join(chosen['versions']) or 'no version'}; "
                                      f"Vanta now requires {' / '.join(g['targets'])}"})
        else:
            missing = [i for i in g["images"] if not chosen["key"] and i.lower() not in chosen["where"]]
            actions.append({"action": "keep", "key": g["key"], "issue": chosen["id"],
                            "reason": f"tracked ({chosen['state']})"
                                      + (f"; issue title does not name image(s) {', '.join(missing)}" if missing else "")})
        if chosen and len(ambiguous) > 1:
            actions[-1]["ambiguous"] = ambiguous
    for i in open_issues:
        if i["id"] not in used:
            actions.append({"action": "resolve", "issue": i["id"], "title": i["title"], "state": i["state"],
                            "reason": "no active Vanta finding matches this issue"})
    json.dump({"generated": today.isoformat(), "groups": groups, "actions": actions, "unparsed": unparsed}, sys.stdout, indent=2)
    print()
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fetch")
    f.add_argument("--out")
    f.add_argument("--config")
    p = sub.add_parser("plan")
    p.add_argument("--findings", required=True)
    p.add_argument("--issues", required=True, nargs="+")
    p.add_argument("--config")
    p.add_argument("--today", help="YYYY-MM-DD; defaults to the current date")
    p.add_argument("--rescan-days", type=int, default=7)
    args = parser.parse_args(argv)
    return cmd_fetch(args) if args.cmd == "fetch" else cmd_plan(args)


if __name__ == "__main__":
    sys.exit(main())
