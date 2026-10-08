import unittest
from bakeoff.runner import summarize


def cell(case, kind, score, version='1.2'):
    return dict(model='fixture', depth_tokens=512, case_id=case, kind=kind, score=score,
                latency_ms=1, error=None, truncated=False, probe_version=version)


def report(rows):
    return summarize(dict(rows=rows, depths=[512], model_meta={'fixture': {}}))[0]


class BakeoffCellTests(unittest.TestCase):
    def test_different_case_populations_cannot_pass_the_gate(self):
        rows = [cell('a','fact',1),cell('b','fact',1),cell('a','noise_decoy',0),
                cell('c','noise_decoy',0),cell('a','noise_unrelated',0),cell('b','noise_unrelated',0)]
        summary = report(rows)
        self.assertEqual(summary['by_depth']['512']['auc_judge'], 1)
        self.assertEqual(summary['passing_depths_judge'], [])
        self.assertEqual(summary['passing_depths_detect'], [512])

    def test_mixed_probe_versions_cannot_pass_as_one_cell(self):
        rows = [cell(case,kind,score,version) for case,version in [('a','1.1'),('b','1.2')]
                for kind,score in [('fact',1),('noise_decoy',0),('noise_unrelated',0)]]
        self.assertEqual(report(rows)['passing_depths_judge'], [])

    def test_duplicate_rows_cannot_pass_as_extra_samples(self):
        rows = [cell('a',kind,score) for kind,score in [('fact',1),('noise_decoy',0),('noise_unrelated',0)]]
        self.assertEqual(report(rows+[rows[0]])['passing_depths_judge'], [])

    def test_truncated_cell_cannot_establish_effective_context(self):
        rows = [cell('a',kind,score) for kind,score in [('fact',1),('noise_decoy',0),('noise_unrelated',0)]]
        rows[0]['truncated'] = True
        self.assertEqual(report(rows)['passing_depths_judge'], [])


if __name__ == '__main__':
    unittest.main()
