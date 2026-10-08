import copy
import json
from pathlib import Path
import tempfile
import unittest

from research.audit_tool_relation_state_supervision import audit_design, inspect_row
from research.tool_relation_state_supervision import build_rows

BASE = Path(__file__).resolve().parents[1] / 'research/goal-engine-2026-10-04/tool-relation-states-v2'


class VariedStateSupervisionTests(unittest.TestCase):
    def test_explicit_fresh_cohort_uses_its_own_request_and_entity_identity(self):
        raw=copy.deepcopy(self.raw);raw['request']=dict(seed=552601,fixtures=64)
        requests={'final':raw['request']}
        design=copy.deepcopy(self.design)
        for key in ['wording_assignments','query_frames','semantic_UNKNOWN_frames']:
            design[key]={'final':design[key]['train']}
        rows=list(build_rows('final',raw,design,fixture_limit=1,requests=requests))
        self.assertEqual(len(rows),942)
        self.assertTrue(all(r['split']=='final' for r in rows))
        self.assertFalse({r['entity'] for r in rows}&{r['entity'] for r in self.rows})
        for row in rows:inspect_row(row,design,raw,requests=requests)
        with self.assertRaises(ValueError):
            list(build_rows('final',raw,design,requests={'final':dict(seed=552602,fixtures=64)}))

    @classmethod
    def setUpClass(cls):
        cls.design = json.loads((BASE / 'supervision-design-v3/protocol.json').read_text())
        cls.raw = json.loads((BASE / 'train/raw.json').read_text())
        cls.rows = list(build_rows('train', cls.raw, cls.design, fixture_limit=1))

    def test_design_is_bound_to_actual_raw_cohort_and_connected(self):
        result = audit_design(BASE)
        self.assertEqual(result['status'], 'PASS')
        self.assertEqual(result['graph']['connected_components'], 1)
        self.assertEqual(result['graph']['unordered_pairs'], 52)

    def test_binary_matrix_preserves_both_goals_and_numeric_balance(self):
        binary = [r for r in self.rows if r['label'] is not None]
        self.assertEqual(len(binary), 832)
        groups = {}
        for row in binary:
            inspect_row(row, self.design, self.raw)
            groups.setdefault((row['group'], row['requested_role']), {0: [], 1: []})[row['label']].append(row['reported_value'])
        for values in groups.values():
            self.assertEqual(sorted(values[0]), sorted(values[1]))
        self.assertTrue(any(r['label'] == 1 and not r['fact_truth'] for r in binary))

    def test_semantic_unknown_matches_field_vocabulary_but_is_never_binary(self):
        unknown = [r for r in self.rows if r['unknown_kind'] != 'unbound_record' and r['label'] is None]
        self.assertEqual(len(unknown), 108)
        self.assertEqual({r['observed_role'] for r in unknown}, set(self.design['roles']))
        self.assertEqual({r['goal_language'] for r in unknown}, {'en', 'pt'})
        for row in unknown:
            inspect_row(row, self.design, self.raw)
            self.assertEqual(row['projection_status'], 'PROJECTED')
        self.assertEqual(sum(r['projection_status'] == 'UNKNOWN' for r in self.rows), 2)

    def test_independent_inspection_rejects_changed_value_label_and_model_string(self):
        original = next(r for r in self.rows if r['label'] == 1)
        for key, value in [('label', 0), ('reported_value', original['reported_value'] + 1), ('text', original['text'] + ' truth=1')]:
            changed = copy.deepcopy(original)
            changed[key] = value
            with self.assertRaises(AssertionError):
                inspect_row(changed, self.design, self.raw)

    def test_calibration_and_final_cannot_become_development_labels(self):
        raw = json.loads((BASE / 'calibration/raw.json').read_text())
        with self.assertRaises(ValueError):
            list(build_rows('train', raw, self.design))
        with self.assertRaises(ValueError):
            list(build_rows('final', self.raw, self.design))

    def test_shared_writer_keeps_whole_pairs_and_refuses_overflow_or_overwrite(self):
        from research.tool_relation_state_supervision import write_rows
        from research.audit_tool_relation_state_supervision import rows
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            tokenizer = lambda a, b, truncation: {'input_ids': list(range(len((a+' '+b).split())))}
            result = write_rows(out, 'train', iter(self.rows), tokenizer)
            self.assertEqual(list(rows(out/'train.jsonl.gz')), self.rows)
            self.assertEqual(result['rows'], 942)
            self.assertEqual(result['cuts'], 0)
            with self.assertRaises(FileExistsError):
                write_rows(out, 'train', iter(self.rows), tokenizer)
            with self.assertRaises(ValueError):
                write_rows(out, 'oversize', iter(self.rows), lambda *a, **k: {'input_ids': list(range(513))})


if __name__ == '__main__':
    unittest.main()
