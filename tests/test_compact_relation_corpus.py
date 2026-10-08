from collections import defaultdict
import unittest

from research import compact_relation_corpus as corpus
from research.measurement_projection import project_measurement


class CompactRelationCorpusTests(unittest.TestCase):
    def test_final_families_entities_inputs_are_reserved(self):
        splits = {split:corpus.build_split(split,2) for split in corpus.SEEDS}
        self.assertEqual(len(corpus.TRAIN_FAMILIES),18)
        self.assertEqual(len(corpus.RESERVED_FAMILIES),8)
        self.assertFalse(set(corpus.TRAIN_FAMILIES)&set(corpus.RESERVED_FAMILIES))
        for a,b in [('train','validation'),('train','final'),('validation','final')]:
            for field in ['entity','content_hash','id']:
                self.assertFalse({r[field] for r in splits[a]} & {r[field] for r in splits[b]})

    def test_same_report_changes_label_with_goal_without_passing_labels_to_view(self):
        rows = corpus.build_split('final',2)
        reports = defaultdict(list)
        counts = defaultdict(lambda:[0,0])
        for row in rows:
            reports[row['report_id']].append(row)
            self.assertEqual(row['label'],int(row['requested_slot']==row['semantic_slot']))
            view = project_measurement(row['objective'],row['text'])
            self.assertEqual(view['status'],'PROJECTED')
            self.assertNotIn('semantic_slot',view['text'])
            self.assertNotIn('label',view['text'])
            counts[row['numeric_band']][row['label']]+=1
        for pair in reports.values():
            self.assertEqual({r['label'] for r in pair},{0,1})
            self.assertEqual(pair[0]['text'],pair[1]['text'])
            self.assertNotEqual(pair[0]['objective'],pair[1]['objective'])
        for values in counts.values():
            self.assertEqual(values[0],values[1])


if __name__ == '__main__':
    unittest.main()
