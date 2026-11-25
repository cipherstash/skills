"""Tests for the implement-tickets skill's workflows/implement-tickets.js.

The workflow is a Claude Code Workflow script. These tests run it under Node with a stub
agent() that returns canned results per agent label, and assert on the agents it starts and
what it returns. No model, git or GitHub call is made.
"""

import json
import os
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKILL_DIR = ROOT / "plugins" / "company-skills" / "skills" / "implement-tickets"
SCRIPT = SKILL_DIR / "workflows" / "implement-tickets.js"
NODE = shutil.which("node")

# The stub runtime. SCENARIO is a JSON object:
#   args       the workflow's args
#   plan       the Plan agent's result
#   overrides  {label: result}; a label mapped to null makes that agent fail
HARNESS = r"""
const SCENARIO = JSON.parse(process.env.SCENARIO);
const calls = [];
let active = 0, peak = 0;
const args = SCENARIO.args;
const log = () => {};
const phase = () => {};
const ticketOf = label => Number((label.match(/#(\d+)/) || [])[1]);

function canned(label, prompt) {
  if (label in SCENARIO.overrides) return SCENARIO.overrides[label];
  const n = ticketOf(label);
  if (label === 'plan') return SCENARIO.plan;
  if (label.startsWith('build')) {
    const base = prompt.match(/from \`origin\/([^`]+)\`/)[1];
    return { status: 'done', branch: 'feat/' + n, base, headSha: 'b' + n,
             criteria: [{ criterion: 'c', met: true }], checks: [], decisions: [], deviations: [] };
  }
  if (label.startsWith('pr')) {
    const base = prompt.match(/its base is \`([^`]+)\`/)[1];
    return { number: 100 + n, url: 'https://example.test/pr/' + n, headSha: 'b' + n, base,
             decisions: [], deviations: [] };
  }
  if (label.startsWith('review')) {
    return { reviewedSha: 'b' + n, skillsUsed: [], findings: [], limits: [], decisions: [], deviations: [] };
  }
  if (label.startsWith('fix')) {
    return { headSha: 'f' + n, pushed: true, fixed: [], refuted: [], needsDecision: [], checks: [],
             decisions: [], deviations: [] };
  }
  if (label.startsWith('wait')) {
    return { headSha: 'b' + n, routineReviewLanded: true, ci: 'passed', failingChecks: [], deviations: [] };
  }
  if (label.startsWith('audit')) {
    return { headSha: 'b' + n, unresolved: [], needsDecision: [], ci: 'passed',
             counts: { total: 0, unresolved: 0, addressed: 0, refuted: 0, needsDecision: 0 }, deviations: [] };
  }
  if (label === 'sync stack') return { merges: [], decisions: [], deviations: [] };
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


def ticket(number, blocked_by=(), labels=("ready-for-agent",), state="open", open_pr=None):
    return {
        "number": number, "title": f"ticket {number}", "state": state,
        "labels": list(labels), "blockedBy": list(blocked_by), "openPr": open_pr,
    }


def plan(tickets, blocker_states=(), review_routine=True):
    return {
        "repo": "o/r", "defaultBranch": "main", "spec": {"number": 1, "title": "spec"},
        "reviewRoutine": review_routine,
        "tickets": tickets, "blockerStates": list(blocker_states),
        "checks": ["make test"], "decisions": [], "deviations": [],
    }


def run(ticket_list, blocker_states=(), overrides=None, review_routine=True, **extra_args):
    body = SCRIPT.read_text().replace("export const meta", "const meta", 1)
    source = HARNESS.replace("/*SCRIPT*/", body)
    scenario = {
        "args": {"spec": 1, **extra_args},
        "plan": plan(ticket_list, blocker_states, review_routine),
        "overrides": overrides or {},
    }
    result = subprocess.run(
        [NODE, "-"], input=source, capture_output=True, text=True, timeout=60,
        env={**os.environ, "SCENARIO": json.dumps(scenario)},
    )
    if result.returncode != 0:
        raise AssertionError(f"node failed:\n{result.stderr}")
    return json.loads(result.stdout)


def labels(result, prefix):
    return [c["label"] for c in result["calls"] if c["label"].startswith(prefix)]


def prompt(result, label):
    return next(c["prompt"] for c in result["calls"] if c["label"] == label)


def by_ticket(result):
    return {t["ticket"]: t for t in result["out"]["tickets"]}


@unittest.skipUnless(NODE or os.environ.get("CI"), "node is not installed")
class ImplementTicketsWorkflowTest(unittest.TestCase):
    def setUp(self):
        if not NODE:
            self.fail("node is required in CI to test the implement-tickets workflow")

    def test_stacks_each_ticket_on_its_blocker(self):
        r = run([ticket(2), ticket(3, [2]), ticket(4, [3])])
        self.assertIsNone(r["error"])
        bases = {n: t["base"] for n, t in by_ticket(r).items()}
        self.assertEqual(bases, {2: "main", 3: "feat/2", 4: "feat/3"})
        order = labels(r, "build")
        self.assertEqual(order, ["build #2", "build #3", "build #4"])
        # A blocked ticket starts once its blocker's PR is open, not after its review.
        self.assertLess(r["calls"].index(next(c for c in r["calls"] if c["label"] == "pr #2")),
                        r["calls"].index(next(c for c in r["calls"] if c["label"] == "build #3")))
        self.assertIn("sync stack", labels(r, "sync"))

    def test_runs_at_most_four_agents_at_once(self):
        r = run([ticket(n) for n in range(2, 12)])
        self.assertIsNone(r["error"])
        self.assertEqual(r["peak"], 4)
        self.assertEqual(len(labels(r, "build")), 10)

    def test_uses_the_agreed_model_for_each_step(self):
        r = run([ticket(2)])
        models = {c["label"].split(" ")[0]: c["model"] for c in r["calls"]}
        self.assertEqual(models, {
            "plan": "sonnet", "build": "opus", "pr": "sonnet", "review": "opus",
            "wait": "haiku", "audit": "opus", "run": "sonnet",
        })
        isolated = {c["label"] for c in r["calls"] if c["isolation"] == "worktree"}
        self.assertEqual(isolated, {"build #2"})

    def test_refuses_a_dependency_cycle_before_building(self):
        r = run([ticket(2, [3]), ticket(3, [2])])
        self.assertIn("cycle", r["error"])
        self.assertEqual(labels(r, "build"), [])

    def test_skips_tickets_that_are_closed_or_not_ready(self):
        r = run([ticket(2), ticket(3, labels=["needs-triage"]), ticket(4, state="closed")])
        self.assertEqual(labels(r, "build"), ["build #2"])
        self.assertEqual(r["out"]["skipped"], [3, 4])
        texts = [e["text"] for e in r["out"]["ledger"]]
        self.assertTrue(any("#3" in t and "ready-for-agent" in t for t in texts))

    def test_explicit_ticket_list_builds_unlabelled_tickets(self):
        r = run([ticket(2, labels=[])], tickets=[2])
        self.assertEqual(labels(r, "build"), ["build #2"])

    def test_two_blockers_branch_from_one_and_merge_the_other(self):
        r = run([ticket(2), ticket(3), ticket(4, [2, 3])])
        p = prompt(r, "build #4")
        self.assertIn("git fetch origin feat/2 feat/3", p)
        self.assertIn("merge `origin/feat/3`", p)
        self.assertEqual(by_ticket(r)[4]["base"], "feat/2")

    def test_stacks_on_an_open_blocker_outside_the_run(self):
        r = run([ticket(2, [9])], [{"number": 9, "state": "open", "openPrBranch": "feat/9"}])
        self.assertEqual(by_ticket(r)[2]["base"], "feat/9")

    def test_does_not_build_on_an_open_outside_blocker_without_a_pr(self):
        r = run([ticket(2, [9])], [{"number": 9, "state": "open"}])
        self.assertEqual(labels(r, "build"), [])
        self.assertEqual(by_ticket(r)[2]["status"], "not built")

    def test_does_not_build_when_an_outside_blocker_has_no_state(self):
        r = run([ticket(2, [9])])
        self.assertEqual(labels(r, "build"), [])
        self.assertEqual(by_ticket(r)[2]["status"], "not built")
        texts = [e["text"] for e in r["out"]["ledger"]]
        self.assertTrue(any("no state for blocker #9" in t for t in texts))

    def test_does_not_build_after_a_blocker_fails(self):
        r = run([ticket(2), ticket(3, [2])], overrides={"build #2": None})
        self.assertEqual(labels(r, "build"), ["build #2"])
        self.assertEqual(by_ticket(r)[3]["status"], "not built")

    def test_plan_only_stops_before_building(self):
        r = run([ticket(2)], planOnly=True)
        self.assertEqual([c["label"] for c in r["calls"]], ["plan"])
        self.assertEqual(r["out"]["inScope"], [2])

    def test_reports_not_audited_when_the_audit_fails(self):
        r = run([ticket(2)], overrides={"audit #2 r1": None})
        self.assertEqual(by_ticket(r)[2]["status"], "not audited")

    def test_fixes_review_findings_and_audits_them(self):
        finding = {"id": "F1", "severity": "major", "location": "a.go:1", "claim": "c",
                   "evidence": "e", "source": "review"}
        r = run([ticket(2)], overrides={
            "review #2": {"reviewedSha": "b2", "skillsUsed": [], "findings": [finding], "limits": [],
                          "decisions": [], "deviations": []},
        })
        self.assertIn('"F1"', prompt(r, "fix #2 r1"))
        self.assertIn('"F1"', prompt(r, "audit #2 r1"))
        self.assertIn("head f2", prompt(r, "wait #2 r1.1"))
        self.assertEqual(by_ticket(r)[2]["status"], "clean")

    def test_an_unpushed_fix_does_not_move_the_head(self):
        finding = {"id": "F1", "severity": "minor", "location": "a.go:1", "claim": "c",
                   "evidence": "e", "source": "review"}
        r = run([ticket(2)], overrides={
            "review #2": {"reviewedSha": "b2", "skillsUsed": [], "findings": [finding], "limits": [],
                          "decisions": [], "deviations": []},
            "fix #2 r1": {"headSha": "local", "pushed": False, "fixed": [], "refuted": [],
                          "needsDecision": [], "checks": [], "decisions": [], "deviations": []},
        })
        self.assertIn("head b2", prompt(r, "wait #2 r1.1"))

    def test_stops_after_the_last_fix_round_with_findings_open(self):
        open_finding = {"id": "A1", "severity": "major", "location": "a.go:1", "claim": "c",
                        "evidence": "e", "source": "audit"}
        audit = {"headSha": "b2", "unresolved": [open_finding], "needsDecision": [],
                 "counts": {"total": 1, "unresolved": 1, "addressed": 0, "refuted": 0, "needsDecision": 0},
                 "deviations": []}
        r = run([ticket(2)], overrides={"audit #2 r1": audit, "audit #2 r2": audit}, maxFixRounds=2)
        self.assertEqual(labels(r, "fix"), ["fix #2 r2"])
        t = by_ticket(r)[2]
        self.assertEqual(t["status"], "open findings")
        self.assertEqual([f["id"] for f in t["openFindings"]], ["A1"])

    def test_records_audit_counts_that_do_not_add_up(self):
        audit = {"headSha": "b2", "unresolved": [], "needsDecision": [],
                 "counts": {"total": 3, "unresolved": 0, "addressed": 1, "refuted": 0, "needsDecision": 0},
                 "deviations": []}
        r = run([ticket(2)], overrides={"audit #2 r1": audit})
        texts = [e["text"] for e in r["out"]["ledger"]]
        self.assertTrue(any("do not reconcile" in t for t in texts))

    def test_waits_again_until_the_routine_review_lands(self):
        pending = {"headSha": "b2", "routineReviewLanded": False, "ci": "pending", "failingChecks": [],
                   "deviations": []}
        r = run([ticket(2)], overrides={"wait #2 r1.1": pending})
        self.assertEqual(labels(r, "wait"), ["wait #2 r1.1", "wait #2 r1.2"])

    def test_without_the_routine_starts_no_wait_and_requests_no_review(self):
        r = run([ticket(2)], routine=False)
        self.assertIsNone(r["error"])
        self.assertEqual(labels(r, "wait"), [])
        for c in r["calls"]:
            self.assertNotIn("cipherstash-agent", c["prompt"], c["label"])
        self.assertEqual(labels(r, "audit"), ["audit #2 r1"])
        self.assertIn("Check CI on the PR's current head", " ".join(prompt(r, "audit #2 r1").split()))
        self.assertEqual(by_ticket(r)[2]["status"], "clean")

    def test_plan_looks_for_the_routine_workflow(self):
        r = run([ticket(2)])
        self.assertIn(".github/workflows/claude-review.yml", prompt(r, "plan"))

    def test_routine_defaults_to_whether_the_repository_has_it(self):
        # This repository has the routine, so its Plan agent reports it and the run waits for it.
        self.assertTrue((ROOT / ".github" / "workflows" / "claude-review.yml").is_file())
        with_routine = run([ticket(2)], review_routine=True)
        self.assertEqual(labels(with_routine, "wait"), ["wait #2 r1.1"])
        self.assertIn("cipherstash-agent", prompt(with_routine, "pr #2"))
        without = run([ticket(2)], review_routine=False)
        self.assertEqual(labels(without, "wait"), [])
        self.assertNotIn("cipherstash-agent", prompt(without, "pr #2"))

    def test_routine_arg_overrides_what_the_plan_found(self):
        r = run([ticket(2)], review_routine=False, routine=True)
        self.assertEqual(labels(r, "wait"), ["wait #2 r1.1"])
        r = run([ticket(2)], review_routine=True, routine=False)
        self.assertEqual(labels(r, "wait"), [])

    def test_routine_is_off_when_the_plan_does_not_say(self):
        r = run([ticket(2)], review_routine=None)
        self.assertEqual(labels(r, "wait"), [])

    def test_routine_off_note_does_not_invent_what_the_plan_found(self):
        r = run([ticket(2)], review_routine=None)
        texts = [e["text"] for e in r["out"]["ledger"]]
        self.assertFalse(any("found no" in t for t in texts), texts)
        self.assertIn("deviation", [e["kind"] for e in r["out"]["ledger"]
                                    if "did not report" in e["text"]])

    def test_failing_ci_the_audit_did_not_list_is_an_open_finding(self):
        audit = {"headSha": "b2", "unresolved": [], "needsDecision": [], "ci": "failed",
                 "counts": {"total": 0, "unresolved": 0, "addressed": 0, "refuted": 0, "needsDecision": 0},
                 "deviations": []}
        r = run([ticket(2)], routine=False, maxFixRounds=1, overrides={"audit #2 r1": audit})
        t = by_ticket(r)[2]
        self.assertNotEqual(t["status"], "clean")
        self.assertEqual([f["id"] for f in t["openFindings"]], ["CI"])

    def test_failing_ci_gets_a_fix_round_when_the_audit_omits_it(self):
        failed = {"headSha": "b2", "unresolved": [], "needsDecision": [], "ci": "failed",
                  "counts": {"total": 0, "unresolved": 0, "addressed": 0, "refuted": 0, "needsDecision": 0},
                  "deviations": []}
        r = run([ticket(2)], routine=False, overrides={"audit #2 r1": failed})
        self.assertEqual(labels(r, "fix"), ["fix #2 r2"])
        self.assertIn('"source": "CI"', prompt(r, "fix #2 r2"))
        self.assertEqual(by_ticket(r)[2]["status"], "clean")

    def test_audit_reports_ci_with_or_without_the_routine(self):
        for routine in (True, False):
            r = run([ticket(2)], routine=routine)
            self.assertIn('Report CI\'s state on the head as "ci"',
                          " ".join(prompt(r, "audit #2 r1").split()), routine)

    def test_audit_without_a_ci_state_is_a_deviation(self):
        audit = {"headSha": "b2", "unresolved": [], "needsDecision": [],
                 "counts": {"total": 0, "unresolved": 0, "addressed": 0, "refuted": 0, "needsDecision": 0},
                 "deviations": []}
        r = run([ticket(2)], routine=False, overrides={"audit #2 r1": audit})
        texts = [e["text"] for e in r["out"]["ledger"] if e["kind"] == "deviation"]
        self.assertTrue(any("did not report CI" in t for t in texts), texts)

    def test_build_and_review_name_a_fallback_without_mattpocock_skills(self):
        r = run([ticket(2)])
        build = " ".join(prompt(r, "build #2").split())
        self.assertIn("If `mattpocock-skills:tdd` cannot be loaded", build)
        self.assertIn("red, green, refactor", build[build.index("cannot be loaded"):])
        review = " ".join(prompt(r, "review #2").split())
        self.assertIn("If `mattpocock-skills:code-review` cannot be loaded", review)
        self.assertIn("review the diff against ticket #2", review)
        for text in (build, review):
            self.assertIn("record a deviation", text[text.index("cannot be loaded"):])

    def test_run_report_gets_every_ledger_entry(self):
        r = run([ticket(2), ticket(3, labels=[])])
        self.assertIn("Skipped #3", prompt(r, "run report"))
        self.assertEqual(labels(r, "run"), ["run report"])


class ImplementTicketsSkillTest(unittest.TestCase):
    SKILL = SKILL_DIR / "SKILL.md"

    def test_only_a_person_can_start_the_skill(self):
        text = self.SKILL.read_text()
        front = text.split("---")[1]
        self.assertIn("name: implement-tickets", front)
        self.assertIn("disable-model-invocation: true", front)

    def test_skill_resolves_the_script_from_its_own_directory(self):
        text = self.SKILL.read_text()
        self.assertIn("${CLAUDE_SKILL_DIR}/workflows/implement-tickets.js", text)
        self.assertNotIn("git rev-parse", text)
        self.assertNotIn(".claude/workflows", text)
        self.assertTrue(SCRIPT.is_file())

    def test_codex_never_selects_the_skill_implicitly(self):
        # No YAML parser in the standard library, so require the exact shape: the key
        # nested under policy:, set to false, with nothing commented out.
        yaml = (SKILL_DIR / "agents" / "openai.yaml").read_text()
        lines = [line.rstrip() for line in yaml.splitlines() if line.strip()]
        self.assertEqual(lines, ["policy:", "  allow_implicit_invocation: false"])


class ImplementTicketsReadmeTest(unittest.TestCase):
    def test_readme_dependency_list_matches_the_script(self):
        text = (ROOT / "README.md").read_text()
        start = text.index("`implement-tickets` runs a Claude Code workflow script")
        section = " ".join(text[start:text.index("`run-report` publishes", start)].split())
        # Neither dependency is required: each has a fallback the script names.
        self.assertIn("`mattpocock-skills`", section)
        self.assertIn("follow its steps themselves", section)
        self.assertIn("`routine`", section)
        self.assertIn(".github/workflows/claude-review.yml", section)
        self.assertNotIn("45 minutes", section)


if __name__ == "__main__":
    unittest.main()
