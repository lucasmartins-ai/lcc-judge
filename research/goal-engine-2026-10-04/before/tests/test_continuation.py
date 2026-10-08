import json
import shlex
import sys
import tempfile
import unittest
from pathlib import Path

from bakeoff.runner import auc_fact_vs_noise, summarize
from replay.harness import JsonCommand, run_single_task_ablation
from replay.tasks import TASKS
from specialist.train_detect import compute_auc, evaluate_pilot
from research.bench_cpu import assess_m8


class ContinuationRegressionTests(unittest.TestCase):
    def test_gate_counts_only_strict_wins(self):
        self.assertEqual(auc_fact_vs_noise([1.0], [1.0]), 0.0)
        self.assertEqual(compute_auc([1.0], [1.0]), 0.0)

    def test_cpu_short_block_pass_does_not_certify_reference_dossier(self):
        result = assess_m8(per_block_p50_ms=100, dossier_s=20, context_tokens=66000, truncated=0)
        self.assertFalse(result['overall_m8_compliant'])
        self.assertTrue(result['dossier_pass'])

    def test_cpu_truncated_or_short_dossier_cannot_pass(self):
        for tokens, truncated in [(35000, 0), (66000, 1)]:
            result = assess_m8(per_block_p50_ms=10, dossier_s=20, context_tokens=tokens, truncated=truncated)
            self.assertFalse(result['overall_m8_compliant'])

    def test_rounded_auc_below_bar_does_not_pass_gate(self):
        rows = []
        for i in range(100):
            fact = 1.0 if i < 89 else .7 if i == 89 else 0.0
            noise = .9 if i == 0 else .5
            for kind, score in [('fact', fact), ('noise_decoy', noise), ('noise_unrelated', noise)]:
                rows.append(dict(model='fixture', depth_tokens=512, case_id=str(i), kind=kind,
                                 score=score, latency_ms=1, error=None, truncated=False, probe_version='1.2'))
        result = summarize(dict(rows=rows, depths=[512], model_meta={'fixture': {}}))[0]
        self.assertEqual(result['by_depth']['512']['auc_judge'], .9)  # .8999 rounded
        self.assertEqual(result['effective_context_judge'], 0)

    def test_synthetic_replay_cannot_enter_training(self):
        record = run_single_task_ablation(TASKS[0], simulation=True)
        self.assertEqual(record['provenance']['dataset_type'], 'SYNTHETIC')
        self.assertFalse(record['training_eligible'])
        self.assertIsNone(record['labels']['critical'])
        self.assertIsNone(record['labels']['redundant'])

    def test_replay_requires_explicit_execution_mode(self):
        with self.assertRaises(ValueError):
            run_single_task_ablation(TASKS[0])

    def test_executor_never_receives_answer_key(self):
        seen = []
        def executor(payload):
            seen.append(payload)
            return {'status': 'SUCCESS', 'output': ' '.join(b['content'] for b in payload['context'])}
        record = run_single_task_ablation(TASKS[0], executor=executor)
        self.assertFalse(record['training_eligible'])  # keyword check is diagnostic
        for payload in seen:
            text = json.dumps(payload)
            for forbidden in ('is_decisive', 'required_keywords', 'candidate_block', 'necessary'):
                self.assertNotIn(forbidden, text)
        self.assertIn('output', record['baseline']['evaluation']['repeats'][0])

    def test_executor_error_does_not_prove_necessity(self):
        def executor(payload):
            if any('leaked_conn_holding_stack' in b['content'] for b in payload['context']):
                return {'status': 'SUCCESS', 'output': ' '.join(TASKS[0].required_keywords)}
            return {'status': 'ERROR', 'output': 'process crashed'}
        record = run_single_task_ablation(TASKS[0], executor=executor)
        self.assertEqual(record['labels']['necessary'], 'UNKNOWN')

    def test_subprocess_executor_contract_and_pinning(self):
        with tempfile.TemporaryDirectory() as directory:
            script = Path(directory)/'executor.py'
            script.write_text("import json,sys\np=json.load(sys.stdin)\nprint(json.dumps(dict(status='SUCCESS',output=p['objective'],cost_usd=0.0)))\n")
            command = JsonCommand(shlex.quote(sys.executable)+' '+shlex.quote(str(script)))
            result = command(dict(objective='Round trip', context=[], seed=42))
            self.assertEqual(result['output'], 'Round trip')
            script.write_text("print('changed')\n")
            with self.assertRaises(ValueError):
                command(dict(objective='Round trip', context=[], seed=42))

    def test_invalid_executor_receipt_becomes_unknown(self):
        with tempfile.TemporaryDirectory() as directory:
            script=Path(directory)/'executor.py'
            script.write_text("print('not JSON')\n")
            command=JsonCommand(shlex.quote(sys.executable)+' '+shlex.quote(str(script)))
            record=run_single_task_ablation(TASKS[0], executor=command)
            self.assertEqual(record['labels']['necessary'],'UNKNOWN')

    def test_detect_uses_independent_baseline(self):
        records = [dict(case_id='fixture', depth=0,
                        f_joint=.8, dec_joint=.1, unr_joint=.3,
                        f_judge=.9, dec_judge=.1, unr_judge=.2,
                        f_baseline=.1, dec_baseline=.9, unr_baseline=.8)]
        result = evaluate_pilot(records, depths=[0])['depth_0']
        self.assertEqual(result['single_head_baseline']['D'], 0.0)
        self.assertEqual(result['delta_D'], 1.0)

    def test_detect_rejects_missing_independent_control(self):
        with self.assertRaises(ValueError):
            evaluate_pilot([dict(case_id='fixture', depth=0,
                                f_joint=.8, dec_joint=.1, unr_joint=.3,
                                f_judge=.9, dec_judge=.1, unr_judge=.2)], depths=[0])


if __name__ == '__main__':
    unittest.main()
