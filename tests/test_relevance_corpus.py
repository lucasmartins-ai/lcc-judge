import unittest


class RelevanceCorpusTests(unittest.TestCase):
    def test_health_is_independent_of_relevance(self):
        from research.relevance_corpus import make_group, verify_label
        rows = make_group('container_cpu', 771, 0)
        labels = {row['kind']: verify_label(row) for row in rows}
        self.assertEqual(labels['healthy_relevant'], 1)
        self.assertEqual(labels['anomalous_relevant'], 1)
        for kind in ['wrong_entity', 'wrong_field', 'wrong_window']:
            self.assertEqual(labels[kind], 0)
        self.assertIsNone(labels['ambiguous_entity'])
        self.assertIsNone(labels['missing_window'])

    def test_oracle_checks_observations_not_generator_kind(self):
        import copy
        from research.relevance_corpus import make_group, verify_label
        row = copy.deepcopy(make_group('container_cpu', 771, 0)[0])
        row['kind'] = 'wrong_entity'
        self.assertEqual(verify_label(row), 1)
        row['observations'][0]['entity'] = 'other'
        self.assertEqual(verify_label(row), 0)

    def test_metadata_and_labels_are_not_model_inputs(self):
        from research.relevance_corpus import make_group, model_input
        for row in make_group('container_cpu', 771, 0):
            objective, text = model_input(row)
            self.assertEqual((objective, text), (row['objective'], row['text']))
            self.assertNotIn(row['id'], objective + text)
            self.assertNotIn(row['kind'], objective + text)
            self.assertNotIn('relevance_label', objective + text)

    def test_splits_and_entities_are_disjoint_and_reproducible(self):
        from research.relevance_corpus import build_split
        splits = {name: build_split(name, 2) for name in ['train', 'validation', 'final']}
        self.assertEqual(splits['train'], build_split('train', 2))
        for left, right in [('train', 'validation'), ('train', 'final'), ('validation', 'final')]:
            self.assertFalse({r['content_hash'] for r in splits[left]} &
                             {r['content_hash'] for r in splits[right]})
            self.assertFalse({r['request']['entity'] for r in splits[left]} &
                             {r['request']['entity'] for r in splits[right]})
        self.assertFalse({r['domain'] for r in splits['train']} &
                         {r['domain'] for r in splits['final']})

    def test_all_generated_labels_and_balanced_formats_are_verified(self):
        from research.relevance_corpus import build_split, verify_label, typed_control
        rows = build_split('train', 4)
        self.assertTrue(all(r['label'] == verify_label(r) for r in rows))
        self.assertTrue(all(r['label'] == typed_control(r['objective'], r['text']) for r in rows))
        for kind in {r['kind'] for r in rows}:
            self.assertEqual({r['format'] for r in rows if r['kind'] == kind},
                             {'jsonl', 'key_value', 'pipe', 'sentence'})

    def test_typed_control_refuses_unknown_grammar(self):
        from research.relevance_corpus import make_group, typed_control
        row = make_group('container_cpu', 771, 0)[0]
        self.assertIsNone(typed_control('Diagnose the service', row['text']))
        self.assertIsNone(typed_control(row['objective'], row['text'] + '\nopaque causality'))

    def test_oracle_rejects_unsupported_and_duplicate_identity(self):
        import copy
        from research.relevance_corpus import make_group, verify_label
        row = copy.deepcopy(make_group('container_cpu', 771, 0)[0])
        row['schema_supported'] = False
        self.assertIsNone(verify_label(row))
        row['schema_supported'] = True
        row['observations'][0]['entity_candidates'] = [row['request']['entity'], 'other']
        self.assertIsNone(verify_label(row))


if __name__ == '__main__':
    unittest.main()
