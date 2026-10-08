"""Submit the same narrow claim with raw per-case evidence, preserving first BLOCK."""
import json
import subprocess
from pathlib import Path

OUT=Path(__file__).resolve().parent
claim='No eval curado pdb-routing/0.1 de 112 controles, a receita separada registrou 48 TP, 64 TN, 0 FP, 0 FN e 0 UNKNOWN; a revisão acoplada com o mesmo guard numérico e cutoff .50 registrou 27 FN.'
verification=json.loads((OUT/'verification.json').read_text())
rows=[json.loads(l) for l in (OUT/'eval-results.jsonl').read_text().splitlines()]
evidence={'claim_scope':'Observed raw counts in one curated experiment. No population, production or causal certification.',
    'independent_receipt_audit':{'path':str(OUT/'verify.py'),'imports_candidate_verifier':False,'exit_code':0,
        'counts':verification['eval'],'canonical_ledger_entries':verification['canonical_ledger_entries'],
        'numeric_conversion_checks':verification['numeric_conversion_checks'],'numeric_policy_checks':verification['numeric_policy_checks']},
    'raw_eval_response_table':{'columns':['case_id','curated_label','numeric_guard','routed_noul','coupled_noul','routed_decision','coupled_decision'],
        'rows':[[r['case_id'],r['expected'],r['numeric']['passed'],r['arms']['routed']['probability'],
            r['arms']['coupled']['probability'],r['routed'],r['coupled']] for r in rows]},
    'reproduce_decisions':'If numeric_guard is false, decision=false; else decision=(noul >= .50). Count positives and negatives from curated_label. Unknown only if guard/probability unavailable; all 112 are decidable.',
    'upstream_reference':'Go k8s.io/apimachinery@v0.36.0 conversions, separately enumerated legal voluntary removals, no candidate import in independent receipt audit.',
    'protocol':json.loads((OUT/'pre-dispatch-freeze.json').read_text()),
    'ledger':{'feature':'lcc_judge_pdb_routing','calls':240,'input_tokens':133932,'raw_fingerprint_multiset_matches_receipts':True},
    'labels_limit':'Text controls authored by one author; shared archetype and correlated scales. No external incident labels. No P2 admission.'}
(OUT/'gate-evidence.json').write_text(json.dumps(evidence,indent=2)+'\n')
proc=subprocess.run(['/Users/Master/Downloads/LOOKAORCHESTRATOR/node_modules/.bin/tsx','src/cli/index.ts','intelligence','gate',claim,
    '--evidence',json.dumps(evidence),'--presented-as','MEASURED','--validated','local','--json'],
    cwd='/Users/Master/Downloads/LOOKAORCHESTRATOR',capture_output=True,text=True)
(OUT/'gate-raw-evidence.json').write_text(proc.stdout)
(OUT/'gate-stderr.txt').write_text(proc.stderr)
print(proc.stdout)
raise SystemExit(proc.returncode)
