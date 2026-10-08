import unittest
import json
from pathlib import Path
import tempfile
from unittest.mock import patch

from research import varied_relation_confirmation_scoring as study
from research.varied_relation_confirmation_scoring import attach_scores, slices, unique_population


class ConfirmationScoringTests(unittest.TestCase):
    def test_duplicate_projection_reuses_one_logit_and_keeps_structural_unknown(self):
        rows = [
            {'id':'a','projected_input_hash':'h'},
            {'id':'b','projected_input_hash':'h'},
            {'id':'c','projected_input_hash':None},
        ]
        views = [
            {'id':'a','projected_tokens':5,'view':{'status':'PROJECTED','projected_input_sha256':'h'}},
            {'id':'b','projected_tokens':5,'view':{'status':'PROJECTED','projected_input_sha256':'h'}},
            {'id':'c','projected_tokens':None,'view':{'status':'UNKNOWN','projected_input_sha256':None}},
        ]
        scores = attach_scores(rows, views, {'h':[1.0,3.0,0.0]})
        self.assertEqual([s['score'] for s in scores[:2]], [2.0,2.0])
        # The independent UNKNOWN logit is the trained/calibrated support axis.
        self.assertEqual(scores[0]['support_score'], 0.0)
        self.assertEqual(scores[1]['support_score'], 0.0)
        self.assertEqual(scores[2]['status'], 'UNKNOWN')

    def test_shared_unknowns_and_all_language_slices_are_required(self):
        rows = []
        scores = []
        for goal in ('en', 'pt'):
            for report in ('en', 'pt'):
                for family in ('primary:a:b', 'seen_control:a:c'):
                    for label in (0, 1):
                        row = dict(id=str(len(rows)), goal_language=goal, report_language=report,
                                   family=family, label=label, unknown_kind=None, fact_truth=False,
                                   objective=goal, report_id=report)
                        rows.append(row)
                        scores.append(dict(id=row['id'], status='SCORED', score=float(label), support_score=-1.))
                for kind in ('diagnosis_goal', 'unbound_record'):
                    row = dict(id=str(len(rows)), goal_language=goal, report_language=report,
                               family='unknown', label=None, unknown_kind=kind)
                    rows.append(row)
                    scores.append(dict(id=row['id'], status='UNKNOWN'))
        result = slices(rows, scores, dict(support=0., relevance=.5))
        self.assertEqual(len(result), 15)
        for name, value in result.items():
            self.assertEqual(value['semantic_unknown_recognition'], 1., name)
            self.assertEqual(value['structural_unknown_recognition'], 1., name)
        self.assertEqual(result['primary']['semantic_unknown'], 4)

    def test_unique_hashes_reject_conflicting_labels_and_third_candidate_blocks_final(self):
        view = dict(status='PROJECTED', objective='q', text='r')
        key = study.digest(['q','r'])
        rows = [dict(id='a',label=1,projected_input_hash=key), dict(id='b',label=1,projected_input_hash=key)]
        views = [dict(id=r['id'],view=view,projected_tokens=5) for r in rows]
        self.assertEqual(len(unique_population(rows,views)[0]), 1)
        rows[1]['label'] = 0
        with self.assertRaises(ValueError):
            unique_population(rows,views)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            candidates = {}
            for seed in study.SEEDS:
                directory = root/str(seed)
                directory.mkdir()
                weight = directory/'weights'
                weight.write_bytes(b'weights')
                p = dict(seed=seed)
                p['sha256'] = study.digest(p)
                values = dict(
                    protocol=p,
                    training_meta=dict(seed=seed, epochs_completed=3, final_inspected=False,
                                       weights_sha256=study.sha(weight), trainability={}),
                    thresholds=dict(final_inspected=False, thresholds={}),
                    audit=dict(status='FAIL' if seed == 303 else 'PASS', private_weights_verified=True),
                    summary=dict(final_evaluated=False),
                    **{'process-exit':dict(returncode=0,study_complete=True)},
                )
                for name,value in values.items():
                    if name != 'protocol':
                        value['protocol_sha256'] = p['sha256']
                    (directory/f'{name}.json').write_text(json.dumps(value))
                candidates[seed] = directory,weight
            with patch.object(study,'ROOT',root), patch.object(study,'OUT',root/'evaluation'), \
                 patch.object(study,'candidate',side_effect=lambda seed:candidates[seed]), patch.object(study,'audit') as final_audit:
                with self.assertRaises(ValueError):
                    study.prepare()
                final_audit.assert_not_called()
                self.assertFalse((root/'evaluation').exists())


if __name__ == '__main__':
    unittest.main()
