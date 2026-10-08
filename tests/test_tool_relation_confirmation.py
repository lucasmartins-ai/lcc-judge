import copy
import json
from pathlib import Path
import unittest

from research.audit_tool_relation_state_supervision import digest


class ConfirmationReceiptTests(unittest.TestCase):
    def test_raw_auditor_integer_keys_survive_receipt_serialization(self):
        from research.audit_tool_relation_confirmation import audit_design
        declaration = audit_design()
        saved = json.loads(json.dumps(declaration))
        self.assertNotEqual(declaration, saved)
        self.assertEqual(digest(declaration), digest(saved))

    def test_revision_preserves_original_capture_and_rejects_changed_request_or_gate(self):
        from research.audit_tool_relation_confirmation import check_revision
        base = Path(__file__).resolve().parents[1] / 'research/goal-engine-2026-10-04/varied-relation-confirm-v1'
        original = json.loads((base/'design/protocol.json').read_text())
        revised = json.loads((base/'design-v2/protocol.json').read_text())
        receipt = json.loads((base/'design/superseded-before-derivation.json').read_text())
        check_revision(original, revised, receipt)
        for key, value in [('requests', {'final': {'seed': 1, 'fixtures': 64}}),
                           ('criteria', dict(revised['criteria'], pooled_auc=.5)),
                           ('pairs', {})]:
            changed = copy.deepcopy(revised); changed[key] = value
            changed['sha256'] = digest({k:v for k,v in changed.items() if k != 'sha256'})
            with self.assertRaises(AssertionError):
                check_revision(original, changed, dict(receipt, replacement_design_sha256=changed['sha256']))


if __name__ == '__main__':
    unittest.main()
