"""Independent triage and queue parsers must interpret their shared inputs consistently."""
import importlib.util
from pathlib import Path
import unittest

SKILLS = Path(__file__).resolve().parents[2]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


triage = module("parser_contract_triage", SKILLS / "vanta-triage/scripts/vanta.py")
queue = module("parser_contract_queue", SKILLS / "vanta-remediate/scripts/remediate_queue.py")


class ParserContract(unittest.TestCase):
    def test_title_acceptance_and_captured_fields_agree(self):
        cases = [
            ("[Vanta] Remediate foo to 1.2.3 (stack)", True),
            ("[Vanta] Remediate @scope/pkg to 5.0.1 / 2.1.0 (stack)", True),
            ("[Vanta] Remediate foo to 1.0.0-rc.1 (org/repo) ", True),
            ("[Vanta] Remediate foo to  1.2.3 (stack)", False),
            ("[Vanta] Remediate foo to   (stack)", False),
            ("[Vanta] Remediate foo to 1.2.3 for stack", False),
            ('[Vanta] Remediate "AWS test"', False),
            ("[Vanta] Track upstream fix for foo (stack)", False),
        ]
        for title, accepted in cases:
            with self.subTest(title=title):
                left = triage.TITLE_RES[0][1].match(title)
                right = queue.REMEDIATE_RE.match(title)
                self.assertEqual(bool(left), accepted, "triage title acceptance")
                self.assertEqual(bool(right), accepted, "queue title acceptance")
                if accepted:
                    self.assertEqual((left['pkg'], left['ver'], left['where']),
                                     (right['pkg'], right['ver'], right['repo']))

    def test_priority_representations_agree(self):
        for value in (None, 0, 1, 2, 3, 4, -1, 5, "2", {}, {"value": 2, "name": "High"}, {"value": None}):
            with self.subTest(priority=value):
                issue = {"priority": value}
                self.assertEqual(triage.urgency(issue)["priority"], queue.priority(issue))


if __name__ == "__main__":
    unittest.main()
