import json
import math
from pathlib import Path
import tempfile
import unittest

from research.audit_tool_role_support import audited_scores, reduce_metrics, thresholds_from_validation
from tests.test_tool_role_policy import examples


class ToolRoleSupportAuditTests(unittest.TestCase):
    def test_equal_positive_negative_scores_receive_no_half_credit(self):
        rows, scores = examples()
        scores[0]['score'] = -2.0
        thresholds = thresholds_from_validation(rows, scores)
        result = reduce_metrics(rows, scores, thresholds)
        self.assertEqual(result['pooled_wins'], 14)
        self.assertEqual(result['pooled_comparisons'], 16)
        self.assertEqual(result['pooled_auc'], .875)
        self.assertEqual(result['within_goal_auc'], .875)
        self.assertEqual(result['unknown_drops'], 0)

    def test_raw_logits_cannot_be_changed_without_invalidating_scores(self):
        row = dict(id='one', content_hash='original', projected_input_hash='projected', label=1)
        view = dict(id='one', projected_tokens=5, view=dict(status='PROJECTED'))
        score = dict(id='one', original_input_hash='original', input_hash='projected', actual_tokens=5,
                     status='SCORED', score=3.0, support_score=-2.0-math.log(math.exp(1)+math.exp(4)),
                     logits=[1.0, 4.0, -2.0], submitted=True, forward_completed=True,
                     guard_reason=None, truncated=False, error=None)
        accounting = {key: (5 if key.endswith('tokens') else 1) for key in
                      ['counted_pairs', 'counted_tokens', 'submitted_pairs', 'submitted_tokens',
                       'forward_completed_pairs', 'forward_completed_tokens', 'valid_score_pairs', 'valid_score_tokens']}
        raw = dict(protocol_sha256='protocol', scalar_control=False, rows=[score], accounting=accounting)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'scores.json'
            path.write_text(json.dumps(raw))
            audited_scores(path, [row], [view], dict(sha256='protocol'), False)
            raw['rows'][0]['logits'][1] += .25
            path.write_text(json.dumps(raw))
            with self.assertRaises(AssertionError):
                audited_scores(path, [row], [view], dict(sha256='protocol'), False)


if __name__ == '__main__':
    unittest.main()
