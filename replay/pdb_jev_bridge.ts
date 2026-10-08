/** Frozen experiment wrapper; canonical credential resolver and shared ledger. */
import fs from 'node:fs';
import {TypeSafeClient} from '/Users/Master/Downloads/LOOKAORCHESTRATOR/src/intelligence/typesafe_client.ts';

async function main() {
  const request=JSON.parse(fs.readFileSync(0,'utf8'));
  const started=performance.now();
  const response=await new TypeSafeClient().evaluate({state:request.state,questions:request.questions,
    model:'jev-1.13.0',feature:'lcc_judge_pdb_routing'});
  process.stdout.write(JSON.stringify({status:'SUCCESS',response,latency_ms:performance.now()-started,
    cost_usd:null})+'\n');
}
main().catch(error=>{
  process.stdout.write(JSON.stringify({status:'ERROR',error:String(error.message),cost_usd:null})+'\n');
  process.exitCode=1;
});
