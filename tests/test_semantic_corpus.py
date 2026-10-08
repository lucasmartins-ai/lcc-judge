import unittest

from research.semantic_corpus import build_split, verify_label, TRAIN_FAMILIES, FINAL_FAMILIES


class SemanticCorpusTests(unittest.TestCase):
    def test_objective_changes_label_for_same_report(self):
        rows = build_split('train', 1)
        texts = {}
        for row in rows:
            texts.setdefault(row['text'], []).append(row)
        self.assertTrue(texts)
        for pairs in texts.values():
            self.assertEqual({r['label'] for r in pairs}, {0, 1})
            self.assertEqual(len({r['objective'] for r in pairs}), 2)

    def test_no_final_family_or_input_hash_overlap(self):
        self.assertFalse(set(TRAIN_FAMILIES) & set(FINAL_FAMILIES))
        splits = {s: build_split(s, 2) for s in ['train', 'validation', 'final']}
        for first, second in [('train','validation'),('train','final'),('validation','final')]:
            self.assertFalse({r['content_hash'] for r in splits[first]} & {r['content_hash'] for r in splits[second]})
        self.assertEqual({r['domain'] for r in splits['final']}, set(FINAL_FAMILIES))

    def test_label_uses_requested_measurement_not_severity(self):
        for row in build_split('final', 1):
            self.assertEqual(verify_label(row), row['label'])
            changed = dict(row, observation_status='arbitrary', id='changed')
            self.assertEqual(verify_label(changed), row['label'])

    def test_model_inputs_hide_label_slots_and_markers(self):
        for row in build_split('train', 1):
            pair = row['objective'] + row['text']
            for token in [row['id'], 'semantic_slot', 'requested_slot', 'GROUND TRUTH', 'not evidence']:
                self.assertNotIn(token, pair)


if __name__ == '__main__':
    unittest.main()
