"""Tests for the Claude review caller workflow, .github/workflows/claude-review.yml.

The rules about who may request a review, and the request itself, live in the shared workflow in cipherstash/workflows
and are tested there. These tests cover only what this repository's caller decides.
"""

from pathlib import Path
import re
import unittest

import yaml


REPO = Path(__file__).resolve().parents[2]
WORKFLOW = yaml.safe_load((REPO / ".github/workflows/claude-review.yml").read_text())
# PyYAML reads the bare key `on` as the boolean true.
TRIGGERS = WORKFLOW.get("on", WORKFLOW.get(True))
REVIEW = WORKFLOW["jobs"]["review"]


def gha(expression):
    return "${{ " + expression + " }}"


class WorkflowTests(unittest.TestCase):
    def test_contains_only_the_job_that_calls_the_shared_workflow(self):
        self.assertEqual(list(WORKFLOW["jobs"]), ["review"])
        self.assertNotIn("steps", REVIEW)

    def test_pins_the_shared_workflow_to_a_full_commit(self):
        # A branch or tag could be moved to other code, which would then run with this repository's secrets.
        self.assertRegex(
            REVIEW["uses"],
            r"^cipherstash/workflows/\.github/workflows/claude-review\.yml@[0-9a-f]{40}$",
        )

    def test_listens_for_every_kind_of_review_request_never_for_every_push(self):
        # No `synchronize`: each push would start another review session.
        self.assertEqual(list(TRIGGERS), ["pull_request", "issue_comment"])
        self.assertEqual(
            TRIGGERS["pull_request"]["types"],
            ["opened", "reopened", "ready_for_review", "review_requested"],
        )
        # Only new comments: an edited or deleted comment is never a comment command.
        self.assertEqual(TRIGGERS["issue_comment"]["types"], ["created"])

    def test_starts_only_for_comments_and_reviewer_requests_that_name_the_review_agent(self):
        condition = re.sub(r"\s+", " ", REVIEW["if"]).strip()
        self.assertEqual(
            condition,
            "(github.event_name != 'issue_comment' || ("
            " github.event.issue.pull_request"
            " && contains(github.event.comment.body, '@cipherstash-agent') ))"
            " && (github.event.action != 'review_requested'"
            " || github.event.requested_reviewer.login == 'cipherstash-agent')",
        )

    def test_grants_only_the_permission_the_reaction_needs(self):
        self.assertEqual(WORKFLOW["permissions"], {})
        self.assertEqual(REVIEW["permissions"], {"issues": "write"})

    def test_passes_the_trigger_id_from_a_variable_and_each_secret_by_name(self):
        # No `secrets: inherit`: the shared workflow gets only the three secrets it needs.
        self.assertEqual(REVIEW["with"], {"routine-trigger-id": gha("vars.CLAUDE_ROUTINE_TRIGGER_ID")})
        self.assertEqual(
            REVIEW["secrets"],
            {
                name: gha(f"secrets.{name}")
                for name in ("CLAUDE_ROUTINE_TOKEN", "CLAUDE_REVIEW_APP_ID", "CLAUDE_REVIEW_APP_PRIVATE_KEY")
            },
        )


if __name__ == "__main__":
    unittest.main()
