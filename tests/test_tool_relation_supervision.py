import copy
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from research.audit_tool_relation_supervision import audit
from research.tool_relation_supervision import build_rows, check_row_binding, prepare

ROOT = Path(__file__).resolve().parents[1]
CAPTURE = ROOT / 'research/goal-engine-2026-10-04/tool-relations-grounded-v1'


class ToolRelationSupervisionTests(unittest.TestCase):
    def setUp(self):
        self.raw = json.loads((CAPTURE / 'train/raw.json').read_text())

    def test_all_four_wording_pairs_are_present_and_numeric_claims_are_balanced(self):
        rows = build_rows('train', self.raw)
        binary = [row for row in rows if row['label'] is not None]
        self.assertEqual({(row['intent_alias'], row['report_caption']) for row in binary},
                         {(0, 0), (0, 1), (1, 0), (1, 1)})
        goals = {}
        for row in binary:
            goals.setdefault(row['objective'], {0: [], 1: []})[row['label']].append(row['reported_value'])
            check_row_binding(row, self.raw)
        for goal in goals.values():
            self.assertEqual(sorted(goal[0]), sorted(goal[1]))
        self.assertTrue(any(row['label'] == 1 and not row['fact_truth'] for row in binary))

    def test_broader_inference_goals_are_unknown_and_tampered_bindings_fail(self):
        rows = build_rows('train', self.raw)
        unknown = [row for row in rows if row['label'] is None]
        self.assertTrue(any(row['unknown_kind'] == 'derived_or_multifield_goal' for row in unknown))
        self.assertTrue(any(row['unknown_kind'] == 'diagnosis_goal' for row in unknown))
        for row in unknown:
            check_row_binding(row, self.raw)
        changed = copy.deepcopy(next(row for row in rows if row['label'] is not None))
        changed['binding']['actual_value'] += 1
        with self.assertRaises(ValueError):
            check_row_binding(changed, self.raw)

    def test_exposed_calibration_cannot_be_used_as_a_training_cohort(self):
        raw = json.loads((CAPTURE / 'calibration/raw.json').read_text())
        with self.assertRaises(ValueError):
            build_rows('train', raw)
        # Preparation requires an immutable output destination, not an overwrite
        # of the source/raw capture or any existing protocol.
        with self.assertRaises(ValueError):
            prepare(CAPTURE, CAPTURE)

    def test_independent_audit_rejects_false_binding_even_with_updated_file_checksum(self):
        original = CAPTURE / 'supervision-v1'
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'cohort'
            shutil.copytree(original, target)
            path = target / 'train.jsonl'
            rows = [json.loads(line) for line in path.read_text().splitlines()]
            rows[0]['binding']['actual_value'] += 1
            path.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows))
            coverage_path = target / 'coverage.json'
            coverage = json.loads(coverage_path.read_text())
            coverage['splits']['train']['rows_sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
            coverage_path.write_text(json.dumps(coverage))
            with self.assertRaises(AssertionError):
                audit(target)


if __name__ == '__main__':
    unittest.main()
