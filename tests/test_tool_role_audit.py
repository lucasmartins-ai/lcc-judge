import json
from pathlib import Path
import unittest

from research.audit_tool_role_data import audit_fixture


class ToolRoleAuditTests(unittest.TestCase):
    def test_every_saved_field_is_reconstructed_from_raw_receipts(self):
        root = Path(__file__).resolve().parents[1]
        raw = json.loads((root / 'research/goal-engine-2026-10-04/tool-role-grounded-v1/calibration-probe-v1/raw.json').read_text())
        for fixture in raw['measurements']['fixtures']:
            fields = audit_fixture(fixture)
            self.assertEqual(fields, fixture['fields'])
        fixture['fields']['profile_cpu_ns'] += 1
        with self.assertRaises(AssertionError):
            audit_fixture(fixture)

    def test_command_identity_is_part_of_measurement_evidence(self):
        root = Path(__file__).resolve().parents[1]
        raw = json.loads((root / 'research/goal-engine-2026-10-04/tool-role-grounded-v1/calibration-probe-v1/raw.json').read_text())
        fixture = raw['measurements']['fixtures'][0]
        fixture['raw_observations'][2]['argv'][1] = '--bytes'
        with self.assertRaises(AssertionError):
            audit_fixture(fixture)


if __name__ == '__main__':
    unittest.main()
