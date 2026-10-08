import collections
import json
import unittest

from research.measurement_projection import project_measurement
from research.tool_role_corpus import build_rows, validate_receipt


def receipt():
    # Calibration measurements are sufficient for unit tests; the prospective
    # dataset uses distinct seeds and captures every receipt separately.
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    return json.loads((root / 'research/goal-engine-2026-10-04/tool-role-grounded-v1/calibration-probe-v1/raw.json').read_text())


class ToolRoleCorpusTests(unittest.TestCase):
    def test_counterfactual_values_cannot_predict_relevance(self):
        rows = build_rows('train', receipt())
        groups = collections.defaultdict(list)
        for row in rows:
            if row['label'] is not None:
                groups[(row['group'], row['requested_role'])].append(row)
        self.assertTrue(groups)
        for group in groups.values():
            positive = collections.Counter(r['reported_value'] for r in group if r['label'] == 1)
            negative = collections.Counter(r['reported_value'] for r in group if r['label'] == 0)
            self.assertEqual(positive, negative)
        contradictions = [r for r in rows if r['label'] == 1 and r['fact_truth'] is False]
        self.assertTrue(contradictions)
        self.assertTrue(all(r['report_variant'] == 'value_swap' for r in contradictions))

    def test_source_roles_are_separate_from_the_only_two_model_inputs(self):
        rows = build_rows('final', receipt())
        self.assertEqual({r['goal_language'] for r in rows}, {'en', 'pt'})
        for row in rows:
            self.assertEqual(set(row['model_pair']), {'objective', 'text'})
            self.assertEqual(row['model_pair'], {k: row[k] for k in ['objective', 'text']})
            if row['label'] is not None:
                self.assertIn(row['binding']['source'], ['du', 'df', 'gzip'])
                view = project_measurement(**row['model_pair'])
                self.assertEqual(view['status'], 'PROJECTED')
                self.assertNotIn(row['entity'], view['text'])

    def test_semantic_unknown_is_distinct_from_parser_unknown(self):
        rows = build_rows('validation', receipt())
        semantic = [r for r in rows if r['unknown_kind'] == 'unsupported_goal']
        structural = [r for r in rows if r['unknown_kind'] == 'unbound_record']
        self.assertTrue(semantic and structural)
        self.assertTrue(all(r['label'] is None for r in semantic + structural))
        # The current view checks syntax/scope, not semantic answerability.
        self.assertTrue(all(project_measurement(**r['model_pair'])['status'] == 'PROJECTED' for r in semantic))
        self.assertTrue(all(project_measurement(**r['model_pair'])['status'] == 'UNKNOWN' for r in structural))

    def test_tampered_or_failed_receipts_cannot_supply_labels(self):
        raw = receipt()
        raw['measurements']['fixtures'][0]['fields']['wc_bytes'] += 1
        with self.assertRaises(ValueError):
            validate_receipt(raw)
        raw = receipt()
        raw['status'] = 'UNKNOWN'
        with self.assertRaises(ValueError):
            build_rows('train', raw)


if __name__ == '__main__':
    unittest.main()
