"""Tests for plugins/company-skills/skills/review-pr/workflows/review-pr.js.

The workflow is a Claude Code Workflow script. These tests run it under Node with a stub
agent(), pipeline() and phase() that return canned results per agent label, and assert on the
agents it starts and what it returns. No model, git or GitHub call is made.
"""

import json
import os
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKILL_DIR = ROOT / "plugins" / "company-skills" / "skills" / "review-pr"
SCRIPT = SKILL_DIR / "workflows" / "review-pr.js"
SKILL = SKILL_DIR / "SKILL.md"
NODE = shutil.which("node")

# The stub runtime. SCENARIO is a JSON object:
#   args       the workflow's args
#   scope      the Scope agent's result
#   overrides  {label: result}; a label mapped to null makes that agent fail
HARNESS = r"""
const SCENARIO = JSON.parse(process.env.SCENARIO);
const calls = [];
let active = 0, peak = 0;
const args = SCENARIO.args;
const log = () => {};
const phase = () => {};

async function pipeline(items, ...stages) {
  return Promise.all(items.map(async (item, i) => {
    let v = item;
    for (const s of stages) {
      try { v = await s(v, item, i); } catch (e) { return null; }
    }
    return v;
  }));
}

const auditOk = { headSha: 'h1', unresolved: [], needsDecision: [], resolvable: [],
  counts: { total: 0, unresolved: 0, addressed: 0, refuted: 0, needsDecision: 0 }, deviations: [] };

function confirmAll(prompt) {
  const list = JSON.parse(prompt.slice(prompt.lastIndexOf('Findings:') + 9));
  return { verifiedSha: 'h1', otherDefects: [], deviations: [],
    verdicts: list.map(f => ({ id: f.id, verdict: 'confirmed', evidence: 'a.go:1 trace' })) };
}

function crossAllNew(prompt) {
  const list = JSON.parse(prompt.slice(prompt.lastIndexOf('Findings:') + 9));
  return { headSha: 'h1', deviations: [],
    entries: list.map((f, i) => ({ id: 'N' + (i + 1), sources: [f.id], outcome: 'new',
      severity: f.severity, location: f.location, claim: f.claim })) };
}

function canned(label, prompt) {
  if (label in SCENARIO.overrides) {
    const o = SCENARIO.overrides[label];
    return typeof o === 'string' && o === 'CONFIRM' ? confirmAll(prompt) : o;
  }
  if (label === 'scope') return SCENARIO.scope;
  if (label.startsWith('review ')) {
    return { reviewedSha: 'h1', skillUsed: 'x', skillMissing: false, findings: [], limits: [],
             decisions: [], deviations: [] };
  }
  if (label.startsWith('verify ')) return confirmAll(prompt);
  if (label === 'cross-check') return crossAllNew(prompt);
  if (label === 'audit') return auditOk;
  if (label === 'post') return { posted: true, reviewUrl: 'https://example.test/r', deviations: [] };
  if (label === 'run report') return { status: 'ok', report: 'report' };
  throw new Error('no canned result for ' + label);
}

async function agent(prompt, opts) {
  active++;
  peak = Math.max(peak, active);
  calls.push({ label: opts.label, model: opts.model || null, isolation: opts.isolation || null, prompt });
  await new Promise(r => setTimeout(r, 2));
  active--;
  return canned(opts.label, prompt);
}

(async () => {
  let out = null, error = null;
  try {
    out = await (async () => {
/*SCRIPT*/
    })();
  } catch (e) {
    error = e.message;
  }
  process.stdout.write(JSON.stringify({ out, error, peak, calls }));
})();
"""


def scope(languages=(), installed=True, security=False, linked=(7,)):
    return {
        "repo": "o/r", "number": 5, "url": "https://github.com/o/r/pull/5", "title": "t",
        "headSha": "h1", "base": "main", "files": ["a.go"], "languages": list(languages),
        "linkedIssues": list(linked),
        "languageReviewers": [
            {"language": lang, "skill": f"company-skills:{lang}-review", "installed": installed}
            for lang in languages
        ],
        "securitySensitive": security, "securityReason": "touches auth" if security else "",
        "decisions": [], "deviations": [],
    }


def finding(i, severity="major"):
    return {"id": f"X{i}", "severity": severity, "location": f"a.go:{i}", "claim": f"claim {i}",
            "trigger": "t", "evidence": "e", "fix": "f"}


def review(*findings):
    return {"reviewedSha": "h1", "skillUsed": "x", "skillMissing": False, "findings": list(findings),
            "limits": [], "decisions": [], "deviations": []}


def run(scope_result=None, overrides=None, **extra_args):
    body = SCRIPT.read_text().replace("export const meta", "const meta", 1)
    source = HARNESS.replace("/*SCRIPT*/", body)
    scenario = {
        "args": {"pr": 5, **extra_args},
        "scope": scope_result or scope(),
        "overrides": overrides or {},
    }
    result = subprocess.run(
        [NODE, "-"], input=source, capture_output=True, text=True, timeout=60,
        env={**os.environ, "SCENARIO": json.dumps(scenario)},
    )
    if result.returncode != 0:
        raise AssertionError(f"node failed:\n{result.stderr}")
    return json.loads(result.stdout)


def labels(result, prefix=""):
    return [c["label"] for c in result["calls"] if c["label"].startswith(prefix)]


def prompt(result, label):
    return next(c["prompt"] for c in result["calls"] if c["label"] == label)


def ledger_texts(result):
    return [e["text"] for e in result["out"]["ledger"]]


@unittest.skipUnless(NODE or os.environ.get("CI"), "node is not installed")
class ReviewPrWorkflowTest(unittest.TestCase):
    def setUp(self):
        if not NODE:
            self.fail("node is required in CI to test the review-pr workflow")

    def test_needs_a_pull_request(self):
        body = SCRIPT.read_text().replace("export const meta", "const meta", 1)
        source = HARNESS.replace("/*SCRIPT*/", body)
        scenario = {"args": {}, "scope": scope(), "overrides": {}}
        out = subprocess.run([NODE, "-"], input=source, capture_output=True, text=True, timeout=60,
                             env={**os.environ, "SCENARIO": json.dumps(scenario)})
        self.assertIn("args.pr", json.loads(out.stdout)["error"])

    def test_picks_one_reviewer_per_dimension(self):
        r = run(scope(["go", "rust"], security=True))
        self.assertIsNone(r["error"])
        self.assertEqual(sorted(labels(r, "review ")), [
            "review correctness", "review lang-go", "review lang-rust", "review security",
            "review standards-spec",
        ])
        self.assertIn("`code-review` skill with the arguments `high https://github.com/o/r/pull/5`",
                      prompt(r, "review correctness"))
        self.assertIn("#7 as the spec", prompt(r, "review standards-spec"))
        self.assertIn("company-skills:go-review", prompt(r, "review lang-go"))
        self.assertIn("security-review", prompt(r, "review security"))

    def test_every_reviewer_checks_out_the_pinned_head(self):
        r = run(scope(["go"]))
        for c in r["calls"]:
            if c["label"].startswith("review "):
                self.assertIn("git checkout --detach h1", c["prompt"])
                self.assertEqual(c["isolation"], "worktree")

    def test_a_language_reviewer_that_is_not_installed_is_a_limit(self):
        r = run(scope(["python"], installed=False))
        self.assertNotIn("review lang-python", labels(r))
        self.assertTrue(any("python-review is not installed" in t for t in r["out"]["limits"]))

    def test_a_reviewer_that_reports_its_skill_missing_is_a_limit(self):
        missing = {**review(), "skillMissing": True}
        r = run(overrides={"review correctness": missing})
        dims = {d["key"]: d["status"] for d in r["out"]["dimensions"]}
        self.assertEqual(dims["correctness"], "skill missing")
        self.assertTrue(any("code-review is not installed" in t for t in r["out"]["limits"]))

    def test_each_reviewer_gets_its_own_verifier_with_its_findings(self):
        r = run(overrides={"review correctness": review(finding(1)),
                           "review standards-spec": review(finding(2))})
        self.assertEqual(sorted(labels(r, "verify ")), ["verify correctness", "verify standards-spec"])
        v = prompt(r, "verify correctness")
        self.assertIn('"correctness-1"', v)
        self.assertNotIn('"standards-spec-1"', v)
        self.assertIn("You did not raise them", v)
        self.assertIn("verify-brief.md", v)

    def test_no_findings_means_no_verifier(self):
        r = run()
        self.assertEqual(labels(r, "verify "), [])
        self.assertEqual(labels(r, "cross-check"), [])

    def test_runs_at_most_four_agents_at_once(self):
        r = run(scope(["go", "rust", "python", "typescript"], security=True),
                overrides={f"review {k}": review(finding(1)) for k in
                           ["correctness", "standards-spec", "lang-go", "lang-rust", "lang-python"]})
        self.assertIsNone(r["error"])
        self.assertEqual(r["peak"], 4)

    def test_uses_the_agreed_model_for_each_step(self):
        r = run(overrides={"review correctness": review(finding(1))}, post=True)
        models = {c["label"].split(" ")[0]: c["model"] for c in r["calls"]}
        self.assertEqual(models, {
            "scope": "sonnet", "audit": "opus", "review": "opus", "verify": "opus",
            "cross-check": "opus", "post": "sonnet", "run": "sonnet",
        })

    def test_counts_reconcile_every_outcome(self):
        refute = {"verifiedSha": "h1", "otherDefects": [], "deviations": [], "verdicts": [
            {"id": "correctness-1", "verdict": "confirmed", "evidence": "a.go:1 trace"},
            {"id": "correctness-2", "verdict": "refuted", "evidence": "a.go:2 guard"},
            {"id": "correctness-3", "verdict": "needs-decision", "evidence": "", "question": "q"},
        ]}
        r = run(overrides={"review correctness": review(finding(1), finding(2), finding(3)),
                           "verify correctness": refute})
        c = r["out"]["counts"]
        self.assertEqual((c["raw"], c["new"], c["refuted"], c["needs-decision"], c["unaccounted"]), (3, 1, 1, 1, 0))
        self.assertTrue(r["out"]["reconciled"])
        self.assertEqual([p["id"] for p in r["out"]["postable"]], ["N1"])

    def test_a_finding_dropped_by_cross_check_is_unaccounted(self):
        drop = {"headSha": "h1", "deviations": [], "entries": [
            {"id": "N1", "sources": ["correctness-1"], "outcome": "new"}]}
        r = run(overrides={"review correctness": review(finding(1), finding(2)), "cross-check": drop}, post=True)
        self.assertFalse(r["out"]["reconciled"])
        self.assertEqual(r["out"]["counts"]["unaccounted"], 1)
        self.assertTrue(any("correctness-2" in t and "no outcome" in t for t in ledger_texts(r)))
        self.assertEqual(labels(r, "post"), [])
        self.assertTrue(any("did not reconcile" in t for t in ledger_texts(r)))

    def test_a_verdict_without_head_evidence_is_downgraded(self):
        weak = {"verifiedSha": "h1", "otherDefects": [], "deviations": [], "verdicts": [
            {"id": "correctness-1", "verdict": "confirmed", "evidence": "looks right"}]}
        r = run(overrides={"review correctness": review(finding(1)), "verify correctness": weak})
        self.assertEqual(r["out"]["counts"]["needs-decision"], 1)
        self.assertEqual(labels(r, "cross-check"), [])

    def test_a_missing_verdict_or_failed_verifier_is_needs_decision(self):
        partial = {"verifiedSha": "h1", "otherDefects": [], "deviations": [], "verdicts": [
            {"id": "correctness-1", "verdict": "confirmed", "evidence": "a.go:1"}]}
        r = run(overrides={"review correctness": review(finding(1), finding(2)),
                           "verify correctness": partial,
                           "review standards-spec": review(finding(3)),
                           "verify standards-spec": None})
        c = r["out"]["counts"]
        self.assertEqual((c["new"], c["needs-decision"], c["unaccounted"]), (1, 2, 0))

    def test_other_defects_from_a_verifier_go_to_a_person(self):
        extra = {"verifiedSha": "h1", "deviations": [], "verdicts": [
            {"id": "correctness-1", "verdict": "refuted", "evidence": "a.go:1 guard"}],
            "otherDefects": [{"location": "b.go:4", "claim": "other"}]}
        r = run(overrides={"review correctness": review(finding(1)), "verify correctness": extra})
        nd = r["out"]["findings"]["needs-decision"]
        self.assertEqual([f["id"] for f in nd], ["correctness-other-1"])
        self.assertEqual(r["out"]["postable"], [])

    def test_cross_check_merges_duplicates_across_dimensions(self):
        merged = {"headSha": "h1", "deviations": [], "entries": [
            {"id": "N1", "sources": ["correctness-1", "standards-spec-1"], "outcome": "new",
             "severity": "major", "location": "a.go:1", "claim": "c"}]}
        r = run(overrides={"review correctness": review(finding(1)),
                           "review standards-spec": review(finding(1)), "cross-check": merged})
        self.assertEqual(r["out"]["counts"]["new"], 2)
        self.assertEqual(len(r["out"]["postable"]), 1)
        self.assertEqual(sorted(r["out"]["postable"][0]["sources"]),
                         ["code-review", "mattpocock-skills:code-review"])

    def test_nothing_is_posted_without_post(self):
        r = run(overrides={"review correctness": review(finding(1))})
        self.assertEqual(labels(r, "post"), [])
        self.assertFalse(r["out"]["posted"])
        self.assertIn("Nothing in this run writes to GitHub", prompt(r, "scope"))

    def test_post_sends_the_postable_set_at_the_pinned_head(self):
        r = run(overrides={"review correctness": review(finding(1))}, post=True)
        p = prompt(r, "post")
        self.assertIn("company-skills:review-post", p)
        self.assertIn("reviewed commit is h1", p)
        self.assertIn('"N1"', p)
        self.assertTrue(r["out"]["posted"])

    def test_does_not_post_when_the_head_moved(self):
        moved = {"headSha": "h2", "deviations": [], "entries": [
            {"id": "N1", "sources": ["correctness-1"], "outcome": "new"}]}
        r = run(overrides={"review correctness": review(finding(1)), "cross-check": moved}, post=True)
        self.assertEqual(labels(r, "post"), [])
        self.assertTrue(any("moved" in t for t in ledger_texts(r)))

    def test_audit_runs_unless_turned_off_and_its_counts_are_checked(self):
        bad = {"headSha": "h1", "unresolved": [], "needsDecision": [], "deviations": [],
               "counts": {"total": 2, "unresolved": 0, "addressed": 1, "refuted": 0, "needsDecision": 0}}
        r = run(overrides={"audit": bad})
        self.assertIn("audit", labels(r))
        self.assertTrue(any("do not reconcile" in t for t in ledger_texts(r)))
        self.assertNotIn("audit", labels(run(audit=False)))

    def test_dimensions_arg_limits_the_reviewers(self):
        r = run(scope(["go"]), dimensions=["lang-go"])
        self.assertEqual(labels(r, "review "), ["review lang-go"])

    def test_report_gets_the_ledger_and_counts(self):
        r = run(scope(["python"], installed=False))
        p = prompt(r, "run report")
        self.assertIn("company-skills:run-report", p)
        self.assertIn("python-review is not installed", p)
        self.assertIn('"reconciled": true', p)


class ReviewPrSkillTest(unittest.TestCase):
    def test_only_a_person_can_start_the_skill(self):
        front = SKILL.read_text().split("---")[1]
        self.assertIn("name: review-pr", front)
        self.assertIn("disable-model-invocation: true", front)

    def test_skill_resolves_the_script_from_its_own_directory(self):
        text = SKILL.read_text()
        self.assertIn("${CLAUDE_SKILL_DIR}/workflows/review-pr.js", text)
        self.assertNotIn("git rev-parse", text)
        self.assertTrue(SCRIPT.is_file())

    def test_codex_never_selects_it_implicitly(self):
        yaml = (SKILL_DIR / "agents" / "openai.yaml").read_text()
        self.assertIn("allow_implicit_invocation: false", yaml)


if __name__ == "__main__":
    unittest.main()
