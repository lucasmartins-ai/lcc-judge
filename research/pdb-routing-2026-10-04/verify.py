"""Independent receipt audit; does not import run.py or the candidate verifier."""
import hashlib
import argparse
import json
import math
import subprocess
import sys
import tempfile
from collections import Counter,defaultdict
from pathlib import Path

OUT=Path(__file__).resolve().parent;ROOT=OUT.parents[1]
sys.path.insert(0,str(ROOT))
from research.archives import verified_sources, read_ledger


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False).encode()).hexdigest()


def read_rows(path):return [json.loads(l) for l in Path(path).read_text().splitlines() if l.strip()]


def counts(rows,arm):
    return {'n':len(rows),'positives':sum(r['expected'] for r in rows),'negatives':sum(not r['expected'] for r in rows),
        'tp':sum(r['expected'] and r[arm] is True for r in rows),
        'tn':sum(not r['expected'] and r[arm] is False for r in rows),
        'fp':sum(not r['expected'] and r[arm] is True for r in rows),
        'fn':sum(r['expected'] and r[arm] is False for r in rows),
        'unknown':sum(r[arm] is None for r in rows)}


def wilson(k,n):
    z=1.96;p=k/n;denom=1+z*z/n
    center=(p+z*z/(2*n))/denom
    half=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/denom
    return [max(0,center-half),min(1,center+half)]


def main(reexecute_oracle=False,write_report=False):
    protocol=json.loads((OUT/'protocol.json').read_text());phash=protocol.pop('sha256');assert digest(protocol)==phash
    freeze=json.loads((OUT/'pre-dispatch-freeze.json').read_text())
    assert freeze['receipts_before_dispatch']==0 and freeze['threshold']==protocol['threshold']==.5
    assert freeze['protocol_sha256']==phash and freeze['protocol_file_sha256']==sha(OUT/'protocol.json')
    verified_sources(OUT,protocol['sources'])
    assert sha(OUT/'upstream/source-manifest.json')==protocol['upstream_manifest_sha256']
    for name,record in json.loads((OUT/'upstream/source-manifest.json').read_text()).items():
        assert sha(OUT/'upstream'/name)==record['sha256']
    assert sha(OUT/'numeric-verification.json')==protocol['numeric_verification_sha256']
    numeric=json.loads((OUT/'numeric-verification.json').read_text())
    assert numeric['candidate_sha256']==sha(OUT/'executed-source/replay/pdb_verifier.py')
    assert numeric['mismatch_count']==0 and not numeric['mismatches']
    # Optional native rebuild avoids requiring the original macOS-only executable.
    if reexecute_oracle:
        with tempfile.TemporaryDirectory(prefix='lcc-pdb-oracle-') as tmp:
            binary=Path(tmp)/'pdb-oracle'
            source=OUT/'executed-source/research/pdb-routing-2026-10-04/oracle'
            subprocess.run(['go','build','-mod=readonly','-o',str(binary),'.'],cwd=source,check=True)
            for input_name,output_name in [('oracle-inputs.jsonl','oracle-output.jsonl'),('case-oracle-inputs.jsonl','case-oracle-outputs.jsonl')]:
                result=subprocess.run([str(binary)],input=(OUT/input_name).read_text(),text=True,capture_output=True,check=True)
                assert read_rows(OUT/output_name)==[json.loads(l) for l in result.stdout.splitlines()]
    grid_inputs=read_rows(OUT/'oracle-inputs.jsonl')
    assert len(grid_inputs)==numeric['conversion_checks']==4240
    assert sum(4*r['replicas'] for r in grid_inputs)==numeric['policy_checks']==290752
    manifest=json.loads((OUT/'cases-manifest.json').read_text());assert sha(OUT/'cases-manifest.json')==protocol['manifest_sha256']
    for name,d in manifest['case_oracle_files'].items():assert sha(OUT/name)==d
    oracle={r['id']:r for r in read_rows(OUT/'case-oracle-outputs.jsonl')}
    cases={s:read_rows(OUT/(s+'.jsonl')) for s in ['development','eval']}
    assert not set(manifest['scales']['development'])&set(manifest['scales']['eval'])
    assert not {r['case_id'] for r in cases['development']}&{r['case_id'] for r in cases['eval']}
    prior=[]
    for split in ['calibration','eval']:prior+=read_rows(ROOT/'research/verifier-calibration-2026-10-03'/(split+'.jsonl'))
    # Audit replica scales directly, without depending on task-number conventions.
    prior_scales={r['contract']['replicas'] for r in prior if 'replicas' in r['contract']}
    assert not prior_scales & set(manifest['scales']['development']+manifest['scales']['eval'])
    rows={};call_fingerprints=[];requests=[];family_rows=defaultdict(list)
    for split,data in cases.items():
        assert len(data)==manifest['counts'][split]
        assert sha(OUT/(split+'.jsonl'))==manifest['files'][split+'.jsonl']==protocol['case_files'][split+'.jsonl']
        assert sum(r['expected'] for r in data)==manifest['positives'][split]
        assert len(list((OUT/'receipts'/split).glob('*/receipt.json')))==len(data)
        rows[split]=[]
        for case in data:
            directory=OUT/'receipts'/split/case['case_id']
            r=json.loads((directory/'receipt.json').read_text())
            assert r['case_sha256']==digest(case) and r['protocol_sha256']==phash
            assert not r['training_eligible'] and not case['training_eligible']
            assert all(r[k]==case[k] for k in ['case_id','split','family','expected'])
            c=case['contract'];n=c['replicas'];params=case['artifact']['parameters']
            assert c['controller_supported'] and c['healthy']==n
            allowed=[];valid=len(params)==1
            for key in params:
                ref=oracle[case['case_id']+':'+key];valid=valid and ref['valid']
                if ref['valid']:
                    allowed=[d for d in range(n+1) if (n-d>=ref['scaled'] if key=='min_available' else d<=ref['scaled'])]
            valid=valid and bool(allowed) and c['drain'] in allowed and all(n-d>=c['quorum'] for d in allowed)
            facts=None
            if valid:
                facts={'min_remaining':n-max(allowed),'max_disruptions':max(allowed)}
                for key,value in case['artifact'].get('numeric_claims',{}).items():valid=valid and type(value) is int and value==facts[key]
            assert valid is case['reference_numeric_pass'] and valid is r['numeric']['passed']
            if valid:
                assert facts==case['reference_counts']
                expected_facts=dict(facts,quorum=c['quorum'],requested_maintenance=c['drain'],
                    quorum_preserved=True,requested_maintenance_permitted=True,supported_controller=True,
                    all_desired_replicas_healthy=True,applies_to_voluntary_evictions=True,
                    prevents_involuntary_node_failures=False,maximal_disruption_required=False)
                assert r['numeric']['facts']==expected_facts
            for arm,a in r['arms'].items():
                assert a==json.loads((directory/(arm+'-receipt.json')).read_text())
                assert a['called'] is valid
                value=valid
                if a['called']:
                    adir=directory/arm;request=json.loads((adir/'request.json').read_text());api=json.loads((adir/'response.json').read_text())
                    assert sha(adir/'request.json')==a['request_sha256']
                    dispatch=json.loads((adir/'dispatch.json').read_text());assert dispatch['request_sha256']==a['request_sha256']
                    assert request['questions']==protocol['questions'][arm] and request['feature']==protocol['feature']
                    state=request['state']
                    assert not set(state)&{'expected','rationale','case_id','split','text_expected','reference_numeric_pass'}
                    if arm=='routed':assert state=={'verified_facts':expected_facts,'explanation':case['artifact']['answer']}
                    else:assert state=={'objective':case['objective'],'context':case['context'],'submitted_answer':case['artifact']}
                    assert api==a['jev'] and api['status']=='SUCCESS' and api['response']['model']==protocol['model']
                    p=api['response']['answers']['consistent']['noul'];assert p==a['probability'] and type(p) in [int,float] and math.isfinite(p) and 0<=p<=1
                    value=p>=protocol['threshold']
                    call_fingerprints.append((api['response']['usage']['input_tokens'],api['response']['usage']['output_tokens'],p))
                    requests.append(digest(request))
                assert value is a['decision']['passed'] and value is r[arm]
            rows[split].append(r)
            if split=='eval':family_rows[r['family']].append(r)
        assert rows[split]==read_rows(OUT/(split+'-results.jsonl'))
    assert len(requests)==len(set(requests)),'Duplicate scoring payload'
    summary=json.loads((OUT/'summary.json').read_text())
    computed={arm:counts(rows['eval'],arm) for arm in ['routed','coupled']}
    development={arm:counts(rows['development'],arm) for arm in ['routed','coupled']}
    assert computed==summary['eval'] and development==summary['development']
    assert all(computed['routed'][k]==0 for k in ['fp','fn','unknown']) is summary['target_pass']
    assert summary['protocol_sha256']==phash and summary['threshold']==.5
    ledger=read_ledger(OUT)
    assert all(r['feature']==protocol['feature'] for r in ledger)
    assert all(r['status']=='ok' and r['model']==protocol['model'] for r in ledger)
    raw_fingerprints=Counter((r['input_tokens'],r['output_tokens'],r['answers']['consistent']['noul']) for r in ledger)
    assert raw_fingerprints==Counter(call_fingerprints)
    tokens=sum(t for t,_,_ in call_fingerprints)
    assert len(ledger)==len(call_fingerprints)==summary['jev_calls']==summary['jev_successes']==240
    assert tokens==summary['jev_input_tokens']==133932
    assert math.isclose(tokens*.042/1e6,summary['tariff_estimated_cost_usd'])
    assert summary['actual_billed_cost_usd'] is None and summary['training_eligible_records']==0
    per_family={f:{a:counts(data,a) for a in ['routed','coupled']} for f,data in family_rows.items()}
    mismatches={a:[dict(case_id=r['case_id'],expected=r['expected'],observed=r[a],probability=r['arms'][a]['probability']) for r in rows['eval'] if r[a] is not r['expected']] for a in ['routed','coupled']}
    assert mismatches==summary['errors']
    output={'sources_hash_verified':True,'pre_dispatch_freeze_verified':True,'threshold':.5,
        'development_scales':manifest['scales']['development'],'eval_scales':manifest['scales']['eval'],
        'prior_pdb_scales':sorted(prior_scales),'shared_archetype_and_wording':True,
        'receipts':sum(len(r) for r in rows.values()),'development':development,'eval':computed,
        'per_family':per_family,'target_pass':summary['target_pass'],
        'upstream_reference_reexecuted':reexecute_oracle,'numeric_conversion_checks':numeric['conversion_checks'],
        'numeric_policy_checks':numeric['policy_checks'],'numeric_mismatches':0,
        'jev_calls':len(call_fingerprints),'canonical_ledger_entries':len(ledger),'input_tokens':tokens,
        'duplicate_scoring_payloads':0,'training_eligible_records':0,
        'tariff_estimate_usd':tokens*.042/1e6,'actual_billed_cost_usd':None,
        'descriptive_wilson95':{'routed_fpr':wilson(computed['routed']['fp'],computed['routed']['negatives']),
            'routed_fnr':wilson(computed['routed']['fn'],computed['routed']['positives'])},
        'population_error_certified':False,'production_ground_truth':False,
        'comparison_causal_certification':False}
    output.update(source_verification_mode='archived',canonical_ledger_scope='run-local-export',
                  temporal_preregistration_certified=False)
    if write_report:
        (OUT/'verification.json').write_text(json.dumps(output,indent=2)+'\n')
    print(json.dumps({k:v for k,v in output.items() if k not in ['per_family']},indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--reexecute-oracle',action='store_true')
    parser.add_argument('--write-report',action='store_true')
    args=parser.parse_args()
    main(args.reexecute_oracle,args.write_report)
