"""Remove-and-replay pilot harness (docs/04-dataset-strategy.md §3-4, R19 reliability audit).

Supports explicit synthetic smoke tests or externally supplied real executors.
Synthetic outputs are never outcome-backed P2 ground truth.
The built-in keyword verifier is diagnostic, not an AST or execution verifier.

Paired protocol:
1. Executing paired baseline runs (all blocks present).
2. Executing paired ablation runs (candidate block removed).
3. Repeating both across multiple seeds to test executor/verifier determinism (R19).
4. Labeling outcome deltas: NECESSARY, UNNECESSARY, or UNKNOWN (flaky).
5. Measuring concordance rate, UNKNOWN share, latency, and cost per label.
6. Freezing the reliability threshold required for P2 training admission.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import time
import subprocess
import shlex
from pathlib import Path
from typing import Callable
from typing import Any

from .tasks import TASKS, ReplayTask


def simulate_agent_execution(task: ReplayTask, available_blocks: list[Any], seed: int) -> dict[str, Any]:
    """Simulate a deterministic agent session using pinned executor logic.
    
    Given the available blocks, the agent generates an investigation trace and conclusion.
    If decisive evidence is absent, the agent fails to find the root cause unless it hits
    a rare nondeterministic lucky guess (modeled with small probability to test R19 detection).
    """
    rng = random.Random(f"{task.executor_id}:{task.task_id}:{seed}")
    has_decisive = any(b.is_decisive for b in available_blocks)
    
    # Controlled nondeterminism / flakiness test:
    # Baseline execution flakiness on task_005 to demonstrate R19 UNKNOWN detection
    is_flaky = (task.task_id == "task_005_ws_leak" and seed == 59)
    
    if has_decisive:
        # Agent has the evidence
        if is_flaky:
            status = "TIMEOUT"
            output = "Agent timed out while traversing heap tree."
        else:
            status = "SUCCESS"
            # Include keywords from decisive block
            decisive_blocks = [b for b in available_blocks if b.is_decisive]
            output = f"Root cause identified: {' '.join(task.required_keywords)}. Evidence: {decisive_blocks[0].content}"
    else:
        # Missing decisive evidence
        if rng.random() < 0.02:  # 2% lucky guess
            status = "SUCCESS"
            output = f"Speculative diagnosis matched: {' '.join(task.required_keywords)}"
        else:
            status = "FAILURE"
            output = "Agent concluded: insufficient logs to isolate root cause; no decisive stack trace found."
            
    tokens_used = sum(len(b.content.split()) for b in available_blocks) + 120
    return {
        "status": status,
        "output": output,
        "tokens_used": tokens_used,
        "seed": seed,
    }


def verify_outcome(task: ReplayTask, exec_result: dict[str, Any]) -> bool:
    """Diagnostic keyword check; does not run code or validate task execution."""
    return exec_result["status"] == "SUCCESS" and all(
        kw in exec_result.get("output", "") for kw in task.required_keywords)


class JsonCommand:
    """A pinned argv command reading JSON stdin and emitting one JSON object."""
    def __init__(self, command: str, timeout: float = 120):
        self.argv = shlex.split(command)
        if not self.argv:
            raise ValueError('Empty command')
        self.timeout = timeout
        self.id = 'json-command@' + hashlib.sha256(json.dumps(self.argv).encode()).hexdigest()
        self.file_hashes = {str(Path(x).resolve()): hashlib.sha256(Path(x).read_bytes()).hexdigest()
                            for x in self.argv if Path(x).is_file()}

    def __call__(self, payload: dict) -> dict:
        for path, expected in self.file_hashes.items():
            if hashlib.sha256(Path(path).read_bytes()).hexdigest() != expected:
                raise ValueError('Pinned executable/script changed: ' + path)
        try:
            proc = subprocess.run(self.argv, input=json.dumps(payload), text=True,
                                  capture_output=True, timeout=self.timeout, check=False)
            if proc.returncode:
                return dict(status='ERROR', output=proc.stdout, error=proc.stderr[-2000:],
                            returncode=proc.returncode, cost_usd=None)
            result = json.loads(proc.stdout)
            if not isinstance(result, dict):
                raise ValueError('Command must emit a JSON object')
            return result
        except subprocess.TimeoutExpired:
            return dict(status='TIMEOUT', output='', cost_usd=None)
        except (ValueError, OSError) as exc:
            return dict(status='ERROR', output='', error=str(exc), cost_usd=None)


def run_single_task_ablation(task: ReplayTask, num_repeats: int = 3, base_seed: int = 42,
                             *, simulation: bool = False,
                             executor: Callable | None = None,
                             verifier: Callable | None = None) -> dict[str, Any]:
    if num_repeats < 2:
        raise ValueError('At least two paired repeats are required')
    if simulation == (executor is not None):
        raise ValueError('Choose explicit simulation or a real executor')
    t0 = time.perf_counter()
    task.candidate_block  # validate ablation ID
    receipts = []
    for blocks in [task.blocks, [b for b in task.blocks if b.block_id != task.candidate_block_id]]:
        runs = []
        for repeat in range(num_repeats):
            seed = base_seed + repeat * 17
            # No candidate ID, expected labels, decisive flag, or answer key reaches the executor.
            payload = dict(objective=task.objective, context=[b.to_executor_dict() for b in blocks], seed=seed)
            raw = simulate_agent_execution(task, blocks, seed) if simulation else executor(payload)
            raw = dict(raw)
            raw.setdefault('status', 'ERROR')
            raw.setdefault('output', '')
            status = raw['status']
            if status in ('ERROR', 'TIMEOUT'):
                passed = None
            elif verifier is None:
                passed = verify_outcome(task, raw)
            else:
                checked = verifier(dict(task_id=task.task_id, objective=task.objective,
                                        expected_keywords=task.required_keywords, result=raw))
                passed = checked.get('passed')
                if not isinstance(passed, bool):
                    passed = None
                raw['verifier_receipt'] = checked
            # Retain complete output and measured billing receipt; never invent API costs.
            raw.update(seed=seed, verified=passed,
                       input_sha256=hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest())
            if simulation:
                raw['estimated_words_plus_constant'] = raw.pop('tokens_used')
                raw['cost_usd'] = 0.0
            runs.append(raw)
        receipts.append(runs)
    baseline, ablation = receipts
    outcomes = [[r['verified'] for r in runs] for runs in receipts]
    concordant = all(None not in values and len(set(values)) == 1 for values in outcomes)
    label = 'UNKNOWN'
    if concordant and all(outcomes[0]):
        label = 'UNNECESSARY' if all(outcomes[1]) else 'NECESSARY'
    executor_id = 'synthetic-oracle@1.0' if simulation else getattr(executor, 'id', 'unversioned-callable')
    verifier_id = getattr(verifier, 'id', 'diagnostic-keywords@1.0')
    return dict(
        schema_version='looka-dataset-record/0.1', task_id=task.task_id,
        task_class=task.task_class, objective=task.objective,
        context=[b.to_dict() for b in task.blocks], candidate_block=task.candidate_block_id,
        baseline=dict(executor=executor_id, verifier=verifier_id,
                      outcome='SUCCESS' if all(outcomes[0]) else 'UNKNOWN' if None in outcomes[0] else 'FAILURE',
                      evaluation=dict(repeats=baseline)),
        ablation=dict(removed_blocks=[task.candidate_block_id], seed=base_seed,
                      outcome='SUCCESS' if all(outcomes[1]) else 'UNKNOWN' if None in outcomes[1] else 'FAILURE',
                      evaluation=dict(repeats=ablation)),
        labels=dict(necessary=label, critical=None, redundant=None, conditional_on=[],
                    label_reason='paired_stable_outcomes' if label != 'UNKNOWN' else 'failed_or_inconsistent_evidence'),
        provenance=dict(dataset_type='SYNTHETIC' if simulation else 'REPLAYED',
                        generator_version='lcc-replay-pilot/1.1', evaluator_version=verifier_id,
                        content_hash=task.content_hash(),
                        harness_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                        suite_sha256=hashlib.sha256(Path(__file__).with_name('tasks.py').read_bytes()).hexdigest(),
                        executor_files=getattr(executor, 'file_hashes', {}),
                        verifier_files=getattr(verifier, 'file_hashes', {})),
        training_eligible=False,
        admission_reason='synthetic_oracle' if simulation else
            'outcome_verifier_and_label_reliability_require_validation_before_P2',
        telemetry=dict(execution_ms=(time.perf_counter()-t0)*1000,
                       num_repeats=num_repeats, concordance=concordant),
    )


def run_pilot(tasks: list[ReplayTask] | None = None, num_repeats: int = 3,
              out_dir: str = 'data/d6_pilot', *, simulation: bool = False,
              executor: Callable | None = None, verifier: Callable | None = None) -> dict[str, Any]:
    tasks = TASKS if tasks is None else tasks
    if not tasks:
        raise ValueError('Empty task suite')
    if simulation == (executor is not None):
        raise ValueError('Choose --simulate or supply --executor-command')
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()
    records = [run_single_task_ablation(task, num_repeats, simulation=simulation,
                                      executor=executor, verifier=verifier) for task in tasks]
    counts = {}
    for record in records:
        label = record['labels']['necessary']
        counts[label] = counts.get(label, 0) + 1
    costs = [run.get('cost_usd') for record in records for condition in ('baseline', 'ablation')
             for run in record[condition]['evaluation']['repeats']]
    cost_known = all(isinstance(cost, (int, float)) and cost >= 0 for cost in costs)
    n = len(records)
    summary = dict(
        total_tasks=n, dataset_type='SYNTHETIC' if simulation else 'REPLAYED',
        status='SMOKE_ONLY' if simulation else 'OUTCOME_VALIDATION_REQUIRED',
        label_counts=counts, concordance_rate=sum(r['telemetry']['concordance'] for r in records)/n,
        unknown_rate=counts.get('UNKNOWN', 0)/n, training_eligible_records=0,
        telemetry=dict(total_time_s=time.perf_counter()-t0,
                       actual_reported_cost_usd=sum(costs) if cost_known else None,
                       cost_per_task_usd=sum(costs)/n if cost_known else None,
                       costs_are_measured=not simulation and cost_known),
        proposed_reliability_threshold=.95,
        reliability_threshold_validated=False,
        verifier_kind='external_command' if verifier else 'diagnostic_keyword_match',
        records_file=str(out/'records.jsonl'),
    )
    (out/'records.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in records))
    (out/'summary.json').write_text(json.dumps(summary, indent=2)+'\n')
    return summary


def main() -> None:
    ap = argparse.ArgumentParser(description='Explicit smoke test or real paired executor pilot')
    ap.add_argument('--out-dir', default='data/d6_pilot')
    ap.add_argument('--repeats', type=int, default=3)
    ap.add_argument('--simulate', action='store_true')
    ap.add_argument('--executor-command', help='JSON stdin -> {status, output, cost_usd, tokens_used}')
    ap.add_argument('--verifier-command', help='JSON stdin -> {passed: boolean, evidence: ...}')
    ap.add_argument('--timeout', type=float, default=120)
    args = ap.parse_args()
    executor = JsonCommand(args.executor_command, args.timeout) if args.executor_command else None
    verifier = JsonCommand(args.verifier_command, args.timeout) if args.verifier_command else None
    summary = run_pilot(num_repeats=args.repeats, out_dir=args.out_dir,
                        simulation=args.simulate, executor=executor, verifier=verifier)
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
