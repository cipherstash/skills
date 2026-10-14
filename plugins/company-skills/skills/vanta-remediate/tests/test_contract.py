"""Contract between vanta-triage's rendered issue description and what vanta-remediate reads back from it.

Groups with adversarial field values are rendered by triage's real vanta.py (group_findings and render_description)
and read back by the remediate side. Every advisory and every field remediation uses must round-trip exactly:
advisory ids, affected ranges (raw), fixed versions (or none), targets, repo or asset, ecosystem, package, and the
Advisory set digest.

read_back() is the remediate side: scripts/checks.py, which reads only the fenced JSON advisory block and trusts it
only when its recomputed digest matches the section's "Advisory set:" line.

Run: python3 -m unittest discover -s tests -p 'test_contract.py' (from the skill directory).
"""

from __future__ import annotations

import contextlib
import io
import json
import random
import re
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_checks import SCRIPTS, vanta  # noqa: E402

sys.path.insert(0, str(SCRIPTS))
import checks  # noqa: E402

GHSA_URL = "https://github.com/advisories/GHSA-abcd-efgh-ijkl"


def read_back(title: str, description: str) -> dict:
    """The remediate side: checks.py's entry point on get_issue's saved result."""
    with tempfile.TemporaryDirectory() as d:
        path = Path(d, "issue.json")
        path.write_text(json.dumps({"id": "CIP-1", "title": title, "status": "Todo", "description": description}))
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = checks.main(["--issue", str(path)])
    assert code in (0, 1), code
    return json.loads(out.getvalue())


def finding(n, advisory, affected, fixed, package="left-pad", ecosystem="npm", repo="acme/stack", target=None,
            url=None):
    return {"id": f"v{n}", "advisory": advisory, "severity": "HIGH", "cvss": 7.5, "kind": "dependency",
            "target": target or repo, "repo": repo, "ecosystem": ecosystem, "package": package, "affected": affected,
            "fixed_version": fixed, "sla": "2026-11-05", "detected": "2026-10-05",
            "url": f"https://github.com/acme/stack/security/dependabot/{n}", "advisory_url": url,
            "summary": "Something is wrong."}


def expected(g: dict) -> dict:
    return {"repo": g["repo"], "asset": None if g["repo"] else g["target"], "ecosystem": g["ecosystem"],
            "package": g["package"], "targets": g["targets"], "digest": g["advisory_digest"],
            "advisories": sorted(([a["id"], a["affected"], a["fixed_version"]] for a in g["advisories"]), key=repr)}


def got(parsed: dict) -> dict:
    out = {k: parsed.get(k) for k in ("repo", "asset", "ecosystem", "package", "targets", "digest")}
    out["advisories"] = sorted(([a["id"], a["affected"], a["fixed_version"]] for a in parsed["advisories"]), key=repr)
    return out


IDS = ["CVE-2026-0001", "GHSA-wxyz-wxyz-wxyz", "Vanta finding v|7", "ID `tick`", "ünïcødé-ID", "n/a", "none",
       "[bracket]", "A / GHSA-1111-2222-3333"]
RANGES = [None, "< 1.2.2", "< 1.2.2 || >= 2.0.0, < 2.1.0", ">= 2.0.0-rc.1, < 2.0.0", ">= 0.4.0, < 0.4.40",
          "<= 3.0.0 | > 4", "`< 1.0.0`", "n/a", "none", "< 1.2.3-ünï"]
FIXES = [None, "1.2.2", "2.1.0", "2.0.0-rc.3", "0.4.40", "3.1.0.post1"]
PACKAGES = [("left-pad", "npm"), ("@scope/pkg", "npm"), ("org.apache.commons:commons-text", "maven"),
            ("golang.org/x/Net", "go"), ("ünï-pkg", "pip"), ("tar", "rust")]
WHERE = [("acme/stack", None), (None, "stack-asset"), (None, "arn:aws:ecr:us-east-1:123:repository/x")]


def random_group(rng: random.Random) -> dict:
    package, ecosystem = rng.choice(PACKAGES)
    repo, target = rng.choice(WHERE)
    findings = []
    for n in range(rng.randint(1, 8)):
        findings.append(finding(n, rng.choice(IDS), rng.choice(RANGES), rng.choice(FIXES), package, ecosystem, repo,
                                target, rng.choice([None, GHSA_URL])))
    [g] = vanta.group_findings(findings)
    return g


class RoundTrip(unittest.TestCase):
    def assertRoundTrips(self, g):
        parsed = read_back(g["title"], g["description"])
        self.assertEqual(got(parsed), expected(g), f"\n{g['title']}\n{g['description']}")

    def test_j4_alternation_range_survives_the_table(self):
        # The review's range: `||` inside a backticked table cell still splits the cell.
        g, = vanta.group_findings([finding(1, "CVE-2026-0001", "< 1.2.2 || >= 2.0.0, < 2.1.0", "2.1.0"),
                                   finding(2, "CVE-2026-0002", ">= 3.0.0, < 3.0.4", "3.0.4")])
        self.assertRoundTrips(g)

    def test_r4c_asset_name_with_colons_keeps_the_ecosystem(self):
        g, = vanta.group_findings([finding(1, "CVE-2026-0001", "< 1.2.2", "1.2.2", repo=None,
                                           target="arn:aws:ecr:us-east-1:123:repository/x")])
        self.assertRoundTrips(g)

    def test_r4d_advisory_ids_with_table_and_link_syntax(self):
        g, = vanta.group_findings([finding(1, "Vanta finding v|7", "< 1.2.2", "1.2.2"),
                                   finding(2, "[bracket]", "< 1.2.2", "1.2.2", url=GHSA_URL),
                                   finding(3, "ID `tick`", None, None)])
        self.assertRoundTrips(g)

    def test_control_plain_group_round_trips(self):
        g, = vanta.group_findings([finding(1, "CVE-2026-0001", ">= 1.0.0, < 1.2.2", "1.2.2", url=GHSA_URL),
                                   finding(2, "CVE-2026-0002", "< 2.0.0", None)])
        self.assertRoundTrips(g)

    def test_r4d_span_markers_and_fences_in_values_stay_inside_the_block(self):
        g, = vanta.group_findings([finding(1, "Vanta key: `x`", "< 1.2.2", "1.2.2", package="a:b"),
                                   finding(2, "Advisory set: `0123456789ab` ```", None, None, package="a:b")])
        self.assertEqual(vanta.generated_span(g["description"]), g["description"])
        self.assertRoundTrips(g)

    def test_digest_implementations_agree(self):
        rng = random.Random(7)
        for _ in range(300):
            g = random_group(rng)
            block = json.loads(re.search(r"^```json\n(.*?)\n```$", g["description"], re.S | re.M).group(1))
            self.assertEqual(checks.advisory_digest(block), vanta.advisory_digest(g))

    def test_altered_block_is_rejected(self):
        g, = vanta.group_findings([finding(1, "CVE-2026-0001", "< 1.2.2 || >= 2.0.0, < 2.1.0", "2.1.0"),
                                   finding(2, "CVE-2026-0002", "< 3.0.0", None)])
        desc = g["description"]
        self.assertEqual(read_back(g["title"], desc)["status"], "ok")
        start = desc.index("```json")
        block = desc[start:desc.index("\n```\n", start)]
        alterations = {
            "a | escaped as \\| by a Markdown rewrite": block.replace("\\u007c", "\\\\|", 1),
            "one range character changed": block.replace("2.1.0\"}", "2.1.1\"}", 1),
            "an advisory dropped": re.sub(r",\n  \{[^\n]*\}(?=\n\])", "", block, count=1),
            "invalid JSON": block.replace("{", "", 1),
            "unknown schema": block.replace('"schema": 1', '"schema": 2', 1),
        }
        for name, altered in alterations.items():
            with self.subTest(name):
                self.assertNotEqual(altered, block)
                out = read_back(g["title"], desc.replace(block, altered))
                self.assertEqual(out["status"], "skip")
                self.assertIn("needs a triage refresh", out["reasons"][0])

    def test_property_every_field_round_trips(self):
        rng = random.Random(20261014)
        failures = []
        for i in range(300):
            g = random_group(rng)
            try:
                if got(read_back(g["title"], g["description"])) != expected(g):
                    failures.append(g)
            except Exception as exc:  # a parse that crashes loses the issue just as surely
                failures.append({**g, "error": repr(exc)})
        if failures:
            first = failures[0]
            self.fail(f"{len(failures)}/300 groups did not round-trip; first:\n{first['title']}\n{first['description']}"
                      + (f"\n{first['error']}" if "error" in first else ""))


if __name__ == "__main__":
    unittest.main()
