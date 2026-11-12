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
            Path(paths[-1]).parent.mkdir(parents=True, exist_ok=True)
            Path(paths[-1]).write_text(data if isinstance(data, str) else json.dumps(data))
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = remediate_queue.main(["--pages", *paths, *flags])
    return code, (json.loads(out.getvalue()) if code == 0 else None), err.getvalue()


class Queue(unittest.TestCase):
    def test_every_page_builds_one_ordered_queue(self):
        code, q, err = run({"page-1.json": PAGE1, "page-2.json": PAGE2})
        self.assertEqual(code, 0, err)
        # Urgent first; then High by earliest due date; no priority last.
        self.assertEqual([i["id"] for i in q["queue"]], ["CIP-5301", "CIP-5320", "CIP-5242", "CIP-5330"])
        self.assertEqual((q["issues_read"], q["pages_read"], q["selected"]), (9, 2, 4))
        self.assertIn("9 issues read, 2 pages read, 4 selected", err)

    def test_page_order_does_not_matter(self):
        _, a, _ = run({"page-1.json": PAGE1, "page-2.json": PAGE2})
        _, b, _ = run({"page-2.json": PAGE2, "page-1.json": PAGE1})
        self.assertEqual(a["queue"], b["queue"])

    def test_aws_configuration_issue_is_left_out_and_listed(self):
        _, q, err = run({"page-1.json": PAGE1, "page-2.json": PAGE2})
        self.assertNotIn("CIP-5310", [i["id"] for i in q["queue"]])
        self.assertEqual(q["aws_configuration"], ["CIP-5310"])
        self.assertIn("CIP-5310", err)

    def test_track_upstream_and_other_issues_are_never_selected(self):
        _, q, _ = run({"page-1.json": PAGE1, "page-2.json": PAGE2}, "--include-assessments")
        ids = [i["id"] for i in q["queue"]]
        self.assertNotIn("CIP-4894", ids)
        self.assertNotIn("CIP-5340", ids)

    def test_include_assessments_adds_assess_issues_in_the_same_order(self):
        _, q, _ = run({"page-1.json": PAGE1, "page-2.json": PAGE2}, "--include-assessments")
        self.assertEqual([(i["id"], i["kind"]) for i in q["queue"]],
                         [("CIP-5301", "remediate"), ("CIP-5320", "remediate"), ("CIP-5056", "assess"),
                          ("CIP-5242", "remediate"), ("CIP-5256", "assess"), ("CIP-5330", "remediate")])
        self.assertEqual(q["selected"], 6)

    def test_empty_queue(self):
        code, q, err = run({"page-1.json": {"issues": [], "hasNextPage": False, "cursor": None}})
        self.assertEqual((code, q["queue"], q["selected"], q["issues_read"]), (0, [], 0, 0), err)

    def test_unrecognised_remediate_titles_are_reported_even_when_queue_is_empty(self):
        for title in ("[Vanta] Remediate foo to 2.0 for stack", "[Vanta] Remediate foo to 2.0"):
            with self.subTest(title=title):
                issue = {"id": "CIP-99", "title": title, "status": "Todo", "statusType": "unstarted",
                         "priority": 2, "dueDate": None}
                code, q, err = run({"page-1.json": {"issues": [issue], "hasNextPage": False}})
                self.assertEqual(code, 0, err)
                self.assertEqual(q["queue"], [])
                self.assertEqual(q["unrecognised"], ["CIP-99"])
                self.assertIn("CIP-99", err, "Excluded remediation issues must be visible in the run summary")

    def test_host_saved_text_blocks_are_unwrapped(self):
        blocks = [{"type": "text", "text": json.dumps(PAGE2)}]
        code, q, err = run({"page-1.json": PAGE1, "page-2.json": blocks})
        self.assertEqual((code, q["selected"]), (0, 4), err)


class RejectsNonConnectorInput(unittest.TestCase):
    def rejected(self, pages, name):
        code, _, err = run(pages)
        self.assertEqual(code, 2, err)
        self.assertIn(name, err)
        return err

    def test_bare_array(self):
        self.rejected({"page-1.json": PAGE1, "page-2.json": PAGE2["issues"]}, "page-2.json")

    def test_missing_field(self):
        page = {**PAGE2, "issues": [{k: v for k, v in i.items() if k != "dueDate"} for i in PAGE2["issues"]]}
        err = self.rejected({"page-1.json": PAGE1, "page-2.json": page}, "page-2.json")
        self.assertIn("dueDate", err)

    def test_missing_has_next_page(self):
        self.rejected({"page-1.json": PAGE1, "page-2.json": {"issues": PAGE2["issues"]}}, "page-2.json")

    def test_incomplete_final_page(self):
        err = self.rejected({"page-1.json": PAGE1}, "page-1.json")
        self.assertIn("hasNextPage", err)

    def test_summarised_data(self):
        summary = {"issues": [{"id": "CIP-5242", "title": "[Vanta] Remediate left-pad to 1.2.2 (stack)"}],
                   "hasNextPage": False}
        self.rejected({"page-1.json": summary}, "page-1.json")

    def test_unreadable_json(self):
        self.rejected({"page-1.json": "not json"}, "page-1.json")


class NumberedPageSequence(unittest.TestCase):
    def test_missing_middle_page_is_rejected_before_selecting(self):
        first = {"issues": [], "hasNextPage": True, "cursor": "page-2"}
        middle = {**PAGE2, "hasNextPage": True, "cursor": "page-3"}
        last = {"issues": [], "hasNextPage": False, "cursor": None}
        code, complete, err = run({"page-1.json": first, "page-2.json": middle, "page-3.json": last})
        self.assertEqual(code, 0, err)
        self.assertIn("CIP-5301", [issue["id"] for issue in complete["queue"]])
        code, incomplete, err = run({"page-1.json": first, "page-3.json": last})
        self.assertEqual(code, 2, "Missing urgent page 2 was silently accepted: " + err)
        self.assertIsNone(incomplete)
        self.assertIn("2", err)

    def test_missing_first_page_is_rejected(self):
        code, result, err = run({"page-2.json": PAGE2})
        self.assertEqual(code, 2, err)
        self.assertIsNone(result)
        self.assertIn("1", err)

    def test_duplicate_page_number_is_rejected(self):
        code, result, err = run({"a/page-1.json": PAGE1, "b/page-1.json": PAGE1, "page-2.json": PAGE2})
        self.assertEqual(code, 2, err)
        self.assertIsNone(result)
        self.assertIn("duplicate", err.lower())

    def test_terminal_page_must_have_highest_number(self):
        code, result, err = run({"page-1.json": PAGE2, "page-2.json": PAGE1})
        self.assertEqual(code, 2, err)
        self.assertIsNone(result)
        self.assertIn("page-1.json", err)

    def test_arbitrary_names_are_rejected(self):
        code, result, err = run({"unindexed.json": PAGE2})
        self.assertEqual(code, 2, err)
        self.assertIsNone(result)
        self.assertIn("unindexed.json", err)

    def test_numeric_sequence_accepts_lexical_glob_order(self):
        pages = {f"page-{n}.json": {"issues": [], "hasNextPage": n < 12, "cursor": str(n + 1)}
                 for n in range(1, 13)}
        code, result, err = run(dict(sorted(pages.items())))
        self.assertEqual(code, 0, err)
        self.assertEqual(result["pages_read"], 12)


if __name__ == "__main__":
    unittest.main()
