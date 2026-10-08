import unittest
from pathlib import Path
import tempfile
from unittest.mock import patch

from research import audit_varied_relation_dev as auditor
from research import wording_pilot_study as study


class WordingPilotStudyTests(unittest.TestCase):
    def test_data_path_override_still_requires_frozen_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            data = Path(directory)/'data';data.mkdir()
            out = data/'study';out.mkdir()
            (data/'rows').write_bytes(b'original')
            p = dict(data_directory='.',data_files={'rows':auditor.sha(data/'rows')})
            self.assertEqual(auditor.pinned_data_path(out,p),data)
            p['data_directory'] = '..'
            with self.assertRaises(FileNotFoundError):
                auditor.pinned_data_path(out,p)
            self.assertEqual(auditor.pinned_data_path(out,p,data),data)
            (data/'rows').write_bytes(b'changed')
            with self.assertRaises(AssertionError):
                auditor.pinned_data_path(out,p,data)

    def test_actual_preflight_budget_and_seed_guard(self):
        # Historical completed execution keeps its archived producer sources.
        p = study.checked_protocol(study.OUT,verify_current=False)
        with patch.object(study,'checked_protocol',return_value=p):
            self.assertEqual(study.checked(),p)
        rows,views = study.read_population(study.DATA,'train')
        items,units,counts = study.reconstruct_training(rows,views)
        self.assertEqual(p['train_class_counts'],counts)
        self.assertEqual(p['declared_training_pairs'],3*(len(items)+4*len(units)))
        self.assertEqual(p['train_unique_items_sha256'],study.digest(items))
        self.assertEqual(p['train_quartets_sha256'],study.digest(units))
        changed = dict(p,seed=202)
        with patch.object(study,'checked_protocol',return_value=changed):
            with self.assertRaises(AssertionError):
                study.checked()


if __name__ == '__main__':
    unittest.main()
