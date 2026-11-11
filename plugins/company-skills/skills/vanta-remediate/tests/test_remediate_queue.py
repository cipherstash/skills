"""Tests for scripts/remediate_queue.py. Run: python3 -m unittest discover -s tests (from the skill directory).

Fixtures in tests/fixtures/ keep the shape of a real list_issues response (see the README there)."""

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import remediate_queue  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"
PAGE1 = json.loads((FIXTURES / "todo-1.json").read_text())
PAGE2 = json.loads((FIXTURES / "todo-2.json").read_text())


def run(pages, *flags):
    """(exit code, parsed stdout or None, stderr) for remediate_queue.py over {name: JSON or text} page files."""
    with tempfile.TemporaryDirectory() as d:
        paths = []
        for name, data in pages.items():
            paths.append(str(Path(d, name)))
            Path(paths[-1]).write_text(data if isinstance(data, str) else json.dumps(data))
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = remediate_queue.main(["--pages", *paths, *flags])
    return code, (json.loads(out.getvalue()) if code == 0 else None), err.getvalue()


class Queue(unittest.TestCase):
    def test_every_page_builds_one_ordered_queue(self):
        code, q, err = run({"todo-1.json": PAGE1, "todo-2.json": PAGE2})
        self.assertEqual(code, 0, err)
        # Urgent first; then High by earliest due date; no priority last.
        self.assertEqual([i["id"] for i in q["queue"]], ["CIP-5301", "CIP-5320", "CIP-5242", "CIP-5330"])
        self.assertEqual((q["issues_read"], q["pages_read"], q["selected"]), (9, 2, 4))
        self.assertIn("9 issues read, 2 pages read, 4 selected", err)

    def test_page_order_does_not_matter(self):
        _, a, _ = run({"todo-1.json": PAGE1, "todo-2.json": PAGE2})
        _, b, _ = run({"b.json": PAGE2, "a.json": PAGE1})
        self.assertEqual(a["queue"], b["queue"])

    def test_aws_configuration_issue_is_left_out_and_listed(self):
        _, q, err = run({"todo-1.json": PAGE1, "todo-2.json": PAGE2})
        self.assertNotIn("CIP-5310", [i["id"] for i in q["queue"]])
        self.assertEqual(q["aws_configuration"], ["CIP-5310"])
        self.assertIn("CIP-5310", err)

    def test_track_upstream_and_other_issues_are_never_selected(self):
        _, q, _ = run({"todo-1.json": PAGE1, "todo-2.json": PAGE2}, "--include-assessments")
        ids = [i["id"] for i in q["queue"]]
        self.assertNotIn("CIP-4894", ids)
        self.assertNotIn("CIP-5340", ids)

    def test_include_assessments_adds_assess_issues_in_the_same_order(self):
        _, q, _ = run({"todo-1.json": PAGE1, "todo-2.json": PAGE2}, "--include-assessments")
        self.assertEqual([(i["id"], i["kind"]) for i in q["queue"]],
                         [("CIP-5301", "remediate"), ("CIP-5320", "remediate"), ("CIP-5056", "assess"),
                          ("CIP-5242", "remediate"), ("CIP-5256", "assess"), ("CIP-5330", "remediate")])
        self.assertEqual(q["selected"], 6)

    def test_empty_queue(self):
        code, q, err = run({"todo.json": {"issues": [], "hasNextPage": False, "cursor": None}})
        self.assertEqual((code, q["queue"], q["selected"], q["issues_read"]), (0, [], 0, 0), err)

    def test_host_saved_text_blocks_are_unwrapped(self):
        blocks = [{"type": "text", "text": json.dumps(PAGE2)}]
        code, q, err = run({"todo-1.json": PAGE1, "todo-2.json": blocks})
        self.assertEqual((code, q["selected"]), (0, 4), err)


class RejectsNonConnectorInput(unittest.TestCase):
    def rejected(self, pages, name):
        code, _, err = run(pages)
        self.assertEqual(code, 2, err)
        self.assertIn(name, err)
        return err

    def test_bare_array(self):
        self.rejected({"todo-1.json": PAGE1, "todo-2.json": PAGE2["issues"]}, "todo-2.json")

    def test_missing_field(self):
        page = {**PAGE2, "issues": [{k: v for k, v in i.items() if k != "dueDate"} for i in PAGE2["issues"]]}
        err = self.rejected({"todo-1.json": PAGE1, "todo-2.json": page}, "todo-2.json")
        self.assertIn("dueDate", err)

    def test_missing_has_next_page(self):
        self.rejected({"todo-1.json": PAGE1, "todo-2.json": {"issues": PAGE2["issues"]}}, "todo-2.json")

    def test_incomplete_final_page(self):
        err = self.rejected({"todo-1.json": PAGE1}, "todo-1.json")
        self.assertIn("hasNextPage", err)

    def test_summarised_data(self):
        summary = {"issues": [{"id": "CIP-5242", "title": "[Vanta] Remediate left-pad to 1.2.2 (stack)"}],
                   "hasNextPage": False}
        self.rejected({"todo.json": summary}, "todo.json")

    def test_unreadable_json(self):
        self.rejected({"todo.json": "not json"}, "todo.json")


if __name__ == "__main__":
    unittest.main()
