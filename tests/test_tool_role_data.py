import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from research.tool_role_data import freeze, collect


class ToolRoleDataTests(unittest.TestCase):
    def test_freeze_is_immutable_and_changed_protocol_cannot_be_reused(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            identity = dict(image_id='sha256:test', source_sha256='test', profile='trusted-tool-observations/0.1')
            with patch('research.tool_role_data.runtime_identity', return_value=identity):
                protocol = freeze(out)
                original = (out / 'protocol.json').read_bytes()
                self.assertEqual(freeze(out), protocol)
                self.assertEqual((out / 'protocol.json').read_bytes(), original)
                changed = dict(protocol)
                changed['language_scope'] = 'changed'
                (out / 'protocol.json').write_text(json.dumps(changed))
                with self.assertRaises(ValueError):
                    collect(out)

    def test_unknown_measurement_is_saved_but_never_rendered_or_retried(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            identity = dict(image_id='sha256:test', source_sha256='test', profile='trusted-tool-observations/0.1')
            with patch('research.tool_role_data.runtime_identity', return_value=identity):
                freeze(out)
                with patch('research.tool_role_data.measure_batch', return_value=dict(status='UNKNOWN', error='worker_failure')) as execute:
                    with self.assertRaises(ValueError):
                        collect(out)
                    execute.assert_called_once()
                    self.assertTrue((out / 'train-raw.json').exists())
                    self.assertFalse((out / 'train.jsonl').exists())
                    with self.assertRaises(ValueError):
                        collect(out)
                    execute.assert_called_once()


if __name__ == '__main__':
    unittest.main()
