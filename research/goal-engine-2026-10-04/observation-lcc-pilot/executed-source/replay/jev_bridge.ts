/** Reuse the canonical client/key resolver/ledger; never print credentials. */
import fs from 'node:fs';
import { TypeSafeClient } from '/Users/Master/Downloads/LOOKAORCHESTRATOR/src/intelligence/typesafe_client.ts';

async function main() {
  const request = JSON.parse(fs.readFileSync(0, 'utf8'));
  const client = new TypeSafeClient();
  const started = performance.now();
  const response = await client.evaluate({
    state: request.state,
    questions: request.questions,
    model: 'jev-1.13.0',
    feature: ['lcc_judge_verifier_calibration', 'lcc_judge_referenced_replay', 'lcc_judge_pareto', 'lcc_judge_observation_pilot'].includes(request.feature)
      ? request.feature : 'lcc_judge_replay_real',
  });
  process.stdout.write(JSON.stringify({
    status: 'SUCCESS', response, latency_ms: performance.now()-started,
    cost_usd: null,
    tariff_estimated_cost_usd: (response.usage?.input_tokens ?? 0) * .042 / 1_000_000,
    tariff_source: 'https://docs.typesafe.ai/models',
  })+'\n');
}

main().catch(error => {
  process.stdout.write(JSON.stringify({status:'ERROR', output:'', error:String(error.message), cost_usd:null})+'\n');
  process.exitCode = 1;
});
