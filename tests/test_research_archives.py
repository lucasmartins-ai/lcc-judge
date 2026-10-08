"""Historical audits use immutable run inputs, not current implementation files."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
RUNS = [('replay-real-2026-10-03', 'verify_run.py'),
        ('verifier-calibration-2026-10-03', 'verify.py'),
        ('pdb-routing-2026-10-04', 'verify.py')]


class ResearchArchiveTests(unittest.TestCase):
    def test_training_history_survives_current_model_and_probe_fixes(self):
        result=subprocess.run([sys.executable,str(ROOT/'research/continuation-2026-10-03/verify_completion.py')],
                              capture_output=True,text=True,timeout=20)
        self.assertEqual(result.returncode,0,result.stderr)
        evidence=json.loads(result.stdout)
        self.assertEqual(evidence['source_verification_mode'],'archived')
        self.assertIs(evidence['actual_weights_verified'],False)
        self.assertIs(evidence['training_reexecuted'],False)

    def test_training_history_copy_without_current_sources_or_weights(self):
        with tempfile.TemporaryDirectory() as temp:
            copied=Path(temp)
            run='continuation-2026-10-03'
            shutil.copytree(ROOT/'research'/run,copied/'research'/run,
                            ignore=shutil.ignore_patterns('__pycache__'))
            for directory in ['data/exp02e','data/d6_pilot','bakeoff/results']:
                shutil.copytree(ROOT/directory,copied/directory)
            shutil.copyfile(ROOT/'research/detect-supervision-results.scores.json',
                            copied/'research/detect-supervision-results.scores.json')
            saved=copied/'research'/run/'verification.json'
            saved.write_text('existing independent report\n')
            for path in copied.rglob('*'):
                if path.is_file(): os.utime(path,(0,0))
            result=subprocess.run([sys.executable,str(copied/'research'/run/'verify_completion.py')],
                                  capture_output=True,text=True,timeout=20)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertIs(json.loads(result.stdout)['checkpoint_final_metrics_reproduced'],True)
            self.assertEqual(saved.read_text(),'existing independent report\n')

    def test_historical_audits_use_run_local_evidence(self):
        for run, script in RUNS:
            with self.subTest(run=run), tempfile.TemporaryDirectory() as cwd:
                result = subprocess.run([sys.executable, str(ROOT/'research'/run/script)],
                                        cwd=cwd, capture_output=True, text=True, timeout=20)
                self.assertEqual(result.returncode, 0, result.stderr)
                evidence = json.loads(result.stdout)
                self.assertEqual(evidence['source_verification_mode'], 'archived')
                self.assertEqual(evidence['canonical_ledger_scope'], 'run-local-export')
                self.assertIs(evidence['temporal_preregistration_certified'], False)
                if run.startswith('pdb'):
                    self.assertIs(evidence['upstream_reference_reexecuted'], False)

    def test_copied_evidence_without_current_code_or_original_binary(self):
        with tempfile.TemporaryDirectory() as temp:
            copied = Path(temp)
            (copied/'research').mkdir()
            shutil.copyfile(ROOT/'research/archives.py', copied/'research/archives.py')
            for run, _ in RUNS:
                shutil.copytree(ROOT/'research'/run, copied/'research'/run,
                                ignore=shutil.ignore_patterns('__pycache__', 'pdb-oracle'))
            shutil.copytree(ROOT/'data/d6_real_pilot', copied/'data/d6_real_pilot')
            for path in copied.rglob('*'):
                if path.is_file():
                    os.utime(path, (0, 0))
            for run, script in RUNS:
                with self.subTest(run=run):
                    saved = copied/'research'/run/'verification.json'
                    saved.write_text('existing independent report\n')
                    result = subprocess.run([sys.executable, str(copied/'research'/run/script)],
                                            capture_output=True, text=True, timeout=20)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(saved.read_text(),'existing independent report\n')

    def test_ledger_tampering_is_rejected(self):
        from research.archives import read_ledger
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            run = ROOT/'research/verifier-calibration-2026-10-03'
            shutil.copyfile(run/'ledger-manifest.json', directory/'ledger-manifest.json')
            ledger = directory/'canonical-ledger.jsonl'
            ledger.write_bytes((run/'canonical-ledger.jsonl').read_bytes()+b'{}\n')
            with self.assertRaisesRegex(AssertionError, 'Ledger export changed'):
                read_ledger(directory)


if __name__ == '__main__':
    unittest.main()
