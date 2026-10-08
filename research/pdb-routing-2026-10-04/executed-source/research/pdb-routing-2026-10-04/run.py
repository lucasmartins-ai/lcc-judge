"""Frozen arithmetic/text routing vs coupled whole-answer review on fresh controls."""
import concurrent.futures
import hashlib
import json
import subprocess
import sys
import time
from datetime import datetime,timezone
from pathlib import Path

OUT=Path(__file__).resolve().parent;ROOT=OUT.parents[1];sys.path.insert(0,str(ROOT))
from replay.pdb_verifier import numeric_verdict,prepare_text_review,combine

TSX='/Users/Master/Downloads/LOOKAORCHESTRATOR/node_modules/.bin/tsx'
ROUTED={'consistent':{'type':'noul','instructions':
    'Is explanation factually consistent with verified_facts? The facts are authoritative results of an exact PDB checker for a supported controller with all desired replicas healthy. Judge only the explanation against these facts; do not recompute a budget or require a maximal disruption allowance. A conservative budget is acceptable. Reject a materially contradictory claim, including an incorrect eviction count, denial of permitted maintenance, denial of quorum protection, or a guarantee against involuntary node failures. An omission alone is not a contradiction.',
    'criteria':{'true':'The explanation contains no material contradiction with the supplied verified facts.',
                'false':'The explanation contradicts one or more supplied verified facts.'}}}
COUPLED={'consistent':{'type':'noul','instructions':
    'Is the submitted answer materially consistent with the explicit controlled observations in context? Evaluate the whole submitted_answer, including explanation and claimed mechanism. A correct mechanism key does not excuse an explanation that denies the observed cause or asserts a competing cause explicitly ruled out. For quantitative decisions consider the stated budget. This asks consistency with this supplied fixture, not production health.',
    'criteria':{'true':'Answer agrees with the explicit observations and contains no materially contradictory claim.',
                'false':'Answer denies an explicit observation, asserts a ruled-out cause, or contradicts the stated quantitative constraint.'}}}


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False).encode()).hexdigest()


def counts(rows,key):
    positives=sum(r['expected'] for r in rows);negatives=len(rows)-positives
    return dict(n=len(rows),positives=positives,negatives=negatives,
        tp=sum(r['expected'] and r[key] is True for r in rows),
        tn=sum(not r['expected'] and r[key] is False for r in rows),
        fp=sum(not r['expected'] and r[key] is True for r in rows),
        fn=sum(r['expected'] and r[key] is False for r in rows),
        unknown=sum(r[key] is None for r in rows))


def freeze():
    prefix=str(OUT.relative_to(ROOT))
    source_names=['replay/pdb_verifier.py','replay/pdb_jev_bridge.ts',prefix+'/build_cases.py',prefix+'/run.py',
        prefix+'/numeric_check.py',prefix+'/oracle/main.go',prefix+'/oracle/go.mod',prefix+'/oracle/go.sum']
    protocol=dict(version='pdb-routing/0.1',model='jev-1.13.0',feature='lcc_judge_pdb_routing',threshold=.5,
        threshold_policy='Inherited .50, fixed before development and eval dispatch; no fitting or tuning.',
        targets={'eval_fp':0,'eval_fn':0,'eval_unknown':0},
        manifest_sha256=sha(OUT/'cases-manifest.json'),
        case_files={s+'.jsonl':sha(OUT/(s+'.jsonl')) for s in ['development','eval']},
        sources={p:sha(ROOT/p) for p in source_names},oracle_binary_sha256=sha(OUT/'pdb-oracle'),
        upstream_manifest_sha256=sha(OUT/'upstream/source-manifest.json'),
        numeric_verification_sha256=sha(OUT/'numeric-verification.json'),
        questions={'routed':ROUTED,'coupled':COUPLED},
        comparison='Same numeric guard and cutoff; different state representation and semantic question. One API judgment per arm per eligible case. Not a causal or repeated-production estimate.',
        scope='Curated PDB controls only; all replicas healthy and supported controller; voluntary evictions. No full manifest, selectors, production ground truth or P2 admission.')
    protocol['sha256']=digest(protocol)
    path=OUT/'protocol.json'
    if path.exists():assert json.loads(path.read_text())==protocol,'Frozen protocol changed'
    else:
        assert not list((OUT/'receipts').glob('*/*/receipt.json'))
        path.write_text(json.dumps(protocol,indent=2)+'\n')
        freeze={'timestamp_utc':datetime.now(timezone.utc).isoformat(),'protocol_sha256':protocol['sha256'],
            'protocol_file_sha256':sha(path),'receipts_before_dispatch':0,'threshold':.5,'targets':protocol['targets']}
        (OUT/'pre-dispatch-freeze.json').write_text(json.dumps(freeze,indent=2)+'\n')
    for name in source_names:
        dest=OUT/'executed-source'/name
        if not dest.exists():dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes((ROOT/name).read_bytes())
        assert sha(dest)==protocol['sources'][name]
    return protocol


def evaluate(row,protocol):
    directory=OUT/'receipts'/row['split']/row['case_id'];directory.mkdir(parents=True,exist_ok=True)
    path=directory/'receipt.json'
    if path.exists():
        saved=json.loads(path.read_text());assert saved['protocol_sha256']==protocol['sha256'];return saved
    numeric=numeric_verdict(row['artifact']['parameters'],numeric_claims=row['artifact'].get('numeric_claims'),**row['contract'])
    assert numeric['passed']==row['reference_numeric_pass']
    receipt={k:row[k] for k in ['case_id','split','family','expected']}
    receipt.update(case_sha256=digest(row),protocol_sha256=protocol['sha256'],numeric=numeric,
        training_eligible=False,arms={})
    for arm in ['routed','coupled']:
        record={'called':False,'probability':None}
        if numeric['passed'] is True:
            state=prepare_text_review(row['artifact'],row['contract']) if arm=='routed' else {
                'objective':row['objective'],'context':row['context'],'submitted_answer':row['artifact']}
            request={'state':state,'questions':protocol['questions'][arm],'feature':protocol['feature']}
            assert not set(state)&{'expected','rationale','case_id','split','reference_numeric_pass','text_expected'}
            if arm=='routed':assert set(state)=={'verified_facts','explanation'}
            adir=directory/arm;adir.mkdir(exist_ok=True)
            text=json.dumps(request,sort_keys=True,ensure_ascii=False)
            (adir/'request.json').write_text(text+'\n')
            record.update(called=True,request_sha256=sha(adir/'request.json'))
            # Dispatch marker survives a process interruption, prohibiting hidden repeats.
            assert not (adir/'dispatch.json').exists(),'Dispatch already happened without final receipt; audit it instead of repeating'
            (adir/'dispatch.json').write_text(json.dumps({'at_utc':datetime.now(timezone.utc).isoformat(),'request_sha256':record['request_sha256']})+'\n')
            try:
                proc=subprocess.run([TSX,str(ROOT/'replay/pdb_jev_bridge.ts')],input=text,text=True,capture_output=True,timeout=20)
                (adir/'response.json').write_text(proc.stdout);(adir/'stderr.txt').write_text(proc.stderr)
                response=json.loads(proc.stdout);record['jev']=response
                if response['status']=='SUCCESS':record['probability']=response['response']['answers']['consistent']['noul']
                else:record['error']=response.get('error','API status error')
            except (ValueError,OSError,subprocess.TimeoutExpired) as exc:record['error']=str(exc)
        record['decision']=combine(numeric,record['probability'],protocol['threshold'])
        receipt['arms'][arm]=record;receipt[arm]=record['decision']['passed']
        (directory/(arm+'-receipt.json')).write_text(json.dumps(record,indent=2)+'\n')
    path.write_text(json.dumps(receipt,indent=2)+'\n')
    return receipt


def main():
    protocol=freeze();all_rows=[]
    for split in ['development','eval']:
        cases=[json.loads(l) for l in (OUT/(split+'.jsonl')).read_text().splitlines()]
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            rows=list(pool.map(lambda row:evaluate(row,protocol),cases))
        all_rows.extend(rows)
        (OUT/(split+'-results.jsonl')).write_text(''.join(json.dumps(r)+'\n' for r in rows))
        print(json.dumps({'split':split,'routed':counts(rows,'routed'),'coupled':counts(rows,'coupled')}) ,flush=True)
    evaluation=[r for r in all_rows if r['split']=='eval']
    calls=[a for r in all_rows for a in r['arms'].values() if a['called']]
    successful=[a['jev'] for a in calls if a.get('jev',{}).get('status')=='SUCCESS']
    metrics={a:counts(evaluation,a) for a in ['routed','coupled']}
    tokens=sum(j['response']['usage']['input_tokens'] for j in successful)
    summary=dict(protocol_sha256=protocol['sha256'],threshold=protocol['threshold'],eval=metrics,
        target_pass=all(metrics['routed'][k]==0 for k in ['fp','fn','unknown']),
        development={a:counts([r for r in all_rows if r['split']=='development'],a) for a in ['routed','coupled']},
        jev_calls=len(calls),jev_successes=len(successful),jev_input_tokens=tokens,
        tariff_estimated_cost_usd=tokens*.042/1e6,actual_billed_cost_usd=None,
        training_eligible_records=0,scope=protocol['scope'],
        errors={a:[{'case_id':r['case_id'],'expected':r['expected'],'observed':r[a],
            'probability':r['arms'][a]['probability']} for r in evaluation if r[a] is not r['expected']] for a in ['routed','coupled']})
    (OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps({k:v for k,v in summary.items() if k!='errors'},indent=2),flush=True)


if __name__=='__main__':main()
