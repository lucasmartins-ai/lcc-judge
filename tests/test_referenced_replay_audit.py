import json
from pathlib import Path
import shutil
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT/'data/d6_referenced_pilot_v03'


class ReferencedReplayAuditTests(unittest.TestCase):
    def test_receipts_reproduce_labels_and_distinguish_quarantine(self):
        from research.referenced_replay_audit import audit
        result = audit(DATA)
        self.assertEqual(result['episodes'], 120)
        self.assertEqual(result['quarantined_verdicts'], 12)
        self.assertEqual(result['executor_errors'], 3)
        self.assertEqual(result['canonical_ledger_entries'], 62)
        self.assertEqual(result['label_counts'], {'NECESSARY': 5, 'UNNECESSARY': 7, 'UNKNOWN': 8})
        self.assertFalse(result['pilot_targets_pass'])

    def test_changed_verdict_is_rejected_before_reduction(self):
        from research.referenced_replay_audit import audit
        with tempfile.TemporaryDirectory() as tmp:
            copied = Path(tmp)/'evidence'
            shutil.copytree(DATA, copied, ignore=shutil.ignore_patterns('__pycache__'))
            path = next((copied/'episodes').rglob('receipt.json'))
            row = json.loads(path.read_text())
            row['verification']['passed'] = not row['verification']['passed']
            path.write_text(json.dumps(row))
            with self.assertRaisesRegex(AssertionError, 'Evidence changed'):
                audit(copied)


if __name__ == '__main__':
    unittest.main()
