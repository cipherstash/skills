"""Tests for the code-review routine workflow, .github/workflows/code-review.yml."""

import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

import yaml


REPO = Path(__file__).resolve().parents[2]
WORKFLOW = yaml.safe_load((REPO / ".github/workflows/code-review.yml").read_text())
# PyYAML reads the bare key `on` as the boolean true.
TRIGGERS = WORKFLOW.get("on", WORKFLOW.get(True))
REQUEST = WORKFLOW["jobs"]["request"]
FIRE = next(step for step in REQUEST["steps"] if step["name"] == "Fire the code-review routine")


def gha(expression):
    return "${{ " + expression + " }}"


class WorkflowTests(unittest.TestCase):
    def test_contains_only_the_request_job_with_a_single_step(self):
        self.assertEqual(list(WORKFLOW["jobs"]), ["request"])
        self.assertEqual(REQUEST["steps"], [FIRE])

    def test_fires_once_per_lifecycle_event_never_on_every_push(self):
        # No `synchronize`: each push would start another review session. Mark
        # the pull request draft and ready again for a fresh review.
        self.assertEqual(list(TRIGGERS), ["pull_request"])
        self.assertEqual(TRIGGERS["pull_request"]["types"], ["opened", "reopened", "ready_for_review"])

    def test_admits_only_non_draft_non_bot_pull_requests_from_this_repository(self):
        # Forks are not given the routine token; bots are not reviewed.
        condition = re.sub(r"\s+", " ", REQUEST["if"]).strip()
        self.assertEqual(
            condition,
            "github.event.pull_request.head.repo.full_name == github.repository"
            " && github.event.pull_request.draft != true"
            " && github.event.pull_request.user.type != 'Bot'",
        )

    def test_runs_one_request_per_pull_request_at_a_time_never_cancelling_one(self):
        # Cancelling a run mid-request could leave a session started behind a
        # cancelled check; a queued run is replaced by the next, bounding a burst.
        self.assertEqual(
            WORKFLOW["concurrency"],
            {
                "group": f"{gha('github.workflow')}-{gha('github.event.pull_request.number')}",
                "cancel-in-progress": False,
            },
        )

    def test_reports_a_failed_request_without_failing_the_pull_request_check(self):
        self.assertIs(FIRE["continue-on-error"], True)

    def test_grants_the_job_token_nothing_and_stays_bounded(self):
        # The request is authenticated by the routine token alone.
        self.assertEqual(WORKFLOW["permissions"], {})
        self.assertNotIn("permissions", REQUEST)
        self.assertEqual(REQUEST["runs-on"], "ubuntu-latest")
        self.assertEqual(REQUEST["timeout-minutes"], 5)

    def test_reads_the_routine_token_from_a_secret_and_the_trigger_id_from_a_variable(self):
        self.assertEqual(
            FIRE["env"],
            {
                "CLAUDE_ROUTINE_TOKEN": gha("secrets.CLAUDE_ROUTINE_TOKEN"),
                "TRIGGER_ID": gha("vars.CLAUDE_ROUTINE_TRIGGER_ID"),
                "PR_URL": gha("github.event.pull_request.html_url"),
                "PR_NUMBER": gha("github.event.pull_request.number"),
                "REPO": gha("github.repository"),
            },
        )
        # Pull-request fields reach the script only through env, never expanded into it.
        self.assertNotIn("${{", FIRE["run"])

    def test_does_not_retry_so_a_timed_out_request_never_reviews_twice(self):
        self.assertNotIn("--retry", FIRE["run"])


# The step's script, run as GitHub runs it (`bash -eo pipefail`), with `curl`
# replaced by a stub that records its arguments and standard input.
CURL_STUB = f"""#!{sys.executable}
import json, os, sys
with open(os.environ["CURL_LOG"], "w") as log:
    log.write(json.dumps(sys.argv[1:]) + "\\0" + sys.stdin.read())
sys.exit(int(os.environ.get("CURL_EXIT", "0")))
"""


class ScriptTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.dir = Path(temp.name)
        stub = self.dir / "curl"
        stub.write_text(CURL_STUB)
        stub.chmod(0o755)
        self.log = self.dir / "curl.log"

    def env(self, **overrides):
        env = {
            "PATH": f"{self.dir}{os.pathsep}{os.environ['PATH']}",
            "CURL_LOG": str(self.log),
            "CLAUDE_ROUTINE_TOKEN": "sk-routine-token",
            "TRIGGER_ID": "trig_01ABCdef",
            "PR_URL": "https://github.com/cipherstash/skills/pull/7",
            "PR_NUMBER": "7",
            "REPO": "cipherstash/skills",
        }
        env.update(overrides)
        return env

    def run_step(self, **overrides):
        return subprocess.run(
            ["bash", "--noprofile", "--norc", "-eo", "pipefail", "-c", FIRE["run"]],
            cwd=self.dir,
            env=self.env(**overrides),
            capture_output=True,
            text=True,
        )

    def curl_call(self):
        args, stdin = self.log.read_text().split("\0")
        return json.loads(args), stdin

    def test_posts_the_pull_request_to_the_trigger_the_token_only_on_standard_input(self):
        result = self.run_step()
        self.assertEqual(result.returncode, 0, result.stderr)
        args, stdin = self.curl_call()

        self.assertIn("https://api.anthropic.com/v1/claude_code/routines/trig_01ABCdef/fire", args)
        self.assertNotIn("sk-routine-token", " ".join(args))
        self.assertEqual(stdin.strip(), "Authorization: Bearer sk-routine-token")
        self.assertEqual(args[args.index("-H") + 1], "@-")
        self.assertEqual(
            json.loads(args[args.index("-d") + 1]),
            {"text": "Review pull request #7 in cipherstash/skills: https://github.com/cipherstash/skills/pull/7"},
        )

    def test_fails_the_step_when_curl_reports_an_http_error(self):
        # curl exits 22 when --fail-with-body receives a 4xx or 5xx answer: a
        # revoked token or a deleted trigger must not read as a fired review.
        result = self.run_step(CURL_EXIT="22")
        self.assertEqual(result.returncode, 22)
        self.assertIn("--fail-with-body", self.curl_call()[0])

    def test_keeps_quotes_in_pull_request_fields_inside_the_json_body(self):
        result = self.run_step(PR_URL='https://x/"},"text":"evil')
        self.assertEqual(result.returncode, 0, result.stderr)
        args, _ = self.curl_call()
        body = json.loads(args[args.index("-d") + 1])
        self.assertEqual(list(body), ["text"])
        self.assertIn('"},"text":"evil', body["text"])

    def test_fails_without_calling_curl_when_the_token_is_missing(self):
        result = self.run_step(CLAUDE_ROUTINE_TOKEN="")
        self.assertEqual(result.returncode, 1)
        self.assertIn("::error::CLAUDE_ROUTINE_TOKEN is empty", result.stdout)
        self.assertFalse(self.log.exists())

    def test_refuses_a_malformed_trigger_id_without_calling_curl(self):
        for trigger_id, case in [
            ("", "unset"),
            ("trig_01../../other", "a path"),
            ("trig_01?x=1", "a query"),
            ("01ABCdef", "no trig_ prefix"),
            ("../../other/trig_01ABC", "a path before trig_"),
        ]:
            with self.subTest(case):
                result = self.run_step(TRIGGER_ID=trigger_id)
                self.assertEqual(result.returncode, 1)
                self.assertIn("::error::CLAUDE_ROUTINE_TRIGGER_ID is not a trigger id", result.stdout)
                self.assertFalse(self.log.exists())


if __name__ == "__main__":
    unittest.main()
