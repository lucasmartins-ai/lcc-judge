"""Sequential split protocol: calibration -> frozen threshold -> held-out eval."""
import argparse
import concurrent.futures
import hashlib
import json
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from replay.real_fixtures import verify_artifact as legacy, ROOT_OPTIONS
from replay.outcome_verifier import verify_artifact as candidate
from replay.tasks import TASKS

OUT=Path(__file__).resolve().parent
TSX='/Users/Master/Downloads/LOOKAORCHESTRATOR/node_modules/.bin/tsx'
QUESTION={'consistent':{'type':'noul','instructions':
    'Is the submitted answer materially consistent with the explicit controlled observations in context? Evaluate the whole submitted_answer, including explanation and claimed mechanism. A correct mechanism key does not excuse an explanation that denies the observed cause or asserts a competing cause explicitly ruled out. For quantitative decisions consider the stated budget. This asks consistency with this supplied fixture, not production health.',
    'criteria':{'true':'Answer agrees with the explicit observations and contains no materially contradictory claim.',
                'false':'Answer denies an explicit observation, asserts a ruled-out cause, or contradicts the stated quantitative constraint.'}}}
THRESHOLDS=[.5,.7,.8,.9,.95,.99]


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def metrics(rows,key,kind=None):
    data=[r for r in rows if kind is None or r['kind']==kind]
    positives=sum(r['expected'] is True for r in data);negatives=len(data)-positives
    fp=sum(r['expected'] is False and r[key] is True for r in data)
    fn=sum(r['expected'] is True and r[key] is False for r in data)
    unknown=sum(r[key] is None for r in data)
    tp=sum(r['expected'] is True and r[key] is True for r in data)
    return dict(n=len(data),positives=positives,negatives=negatives,tp=tp,fp=fp,fn=fn,unknown=unknown,
        fpr=fp/negatives if negatives else None,fnr=fn/positives if positives else None,
        recall=tp/positives if positives else None,unknown_rate=unknown/len(data) if data else None)


def evaluate(row,protocol):
    directory=OUT/'receipts'/row['split']/row['case_id'];directory.mkdir(parents=True,exist_ok=True)
    path=directory/'receipt.json'
    if path.exists():
        receipt=json.loads(path.read_text());assert receipt['protocol_sha256']==protocol['sha256'];return receipt
    start=time.perf_counter();task=TASKS[row['task_number']-1]
    old=legacy(task,row['artifact']);new=candidate(task,row['artifact'],row['contract'])
    receipt={k:row[k] for k in ['case_id','split','task_number','kind','family','expected']}
    receipt.update(protocol_sha256=protocol['sha256'],case_sha256=hashlib.sha256(json.dumps(row,sort_keys=True,ensure_ascii=False).encode()).hexdigest(),
                   legacy_verification=old,candidate_verification=new,legacy=old['passed'],structural=new['passed'],
                   semantic_probability=None,jev_called=False,training_eligible=False)
    if row['kind']=='typed':
        request=dict(feature='lcc_judge_verifier_calibration',state=dict(objective=row['objective'],context=row['context'],
            submitted_answer=row['artifact'],mechanism_meanings=ROOT_OPTIONS),questions=QUESTION)
        encoded=json.dumps(request,ensure_ascii=False,sort_keys=True)
        assert all(k not in request['state'] for k in ['expected','rationale','case_id','contract','split'])
        (directory/'request.json').write_text(encoded+'\n')
        receipt['request_sha256']=sha(directory/'request.json');receipt['jev_called']=True
        try:
            proc=subprocess.run([TSX,str(ROOT/'replay/jev_bridge.ts')],input=encoded,text=True,capture_output=True,timeout=20)
            (directory/'response.json').write_text(proc.stdout);(directory/'stderr.txt').write_text(proc.stderr)
            result=json.loads(proc.stdout);receipt['jev']=result
            if result['status']=='SUCCESS':receipt['semantic_probability']=result['response']['answers']['consistent']['noul']
        except (ValueError,OSError,subprocess.TimeoutExpired) as exc:receipt['jev_error']=str(exc)
    receipt['wall_s']=time.perf_counter()-start
    path.write_text(json.dumps(receipt,indent=2)+'\n')
    return receipt


def score_with_threshold(rows,threshold):
    result=[]
    for row in rows:
        r=dict(row);value=r['structural']
        if r['kind']=='typed' and value is True:
            p=r['semantic_probability'];value=p>=threshold if type(p) in [int,float] else None
        r['combined']=value;result.append(r)
    return result


def run_split(split,protocol):
    cases=[json.loads(line) for line in (OUT/(split+'.jsonl')).read_text().splitlines()]
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        rows=list(pool.map(lambda r:evaluate(r,protocol),cases))
    print(f'{split}: {len(rows)} receipts saved',flush=True)
    return rows


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--phase',choices=['calibration','eval','all'],default='all')
    args=parser.parse_args()
    files=['replay/real_fixtures.py','replay/outcome_verifier.py','replay/jev_bridge.ts',str(Path(__file__).relative_to(ROOT))]
    protocol=dict(version='verifier-calibration/0.1',manifest_sha256=sha(OUT/'cases-manifest.json'),
        case_files={name:sha(OUT/name) for name in ['calibration.jsonl','eval.jsonl']},
        sources={name:sha(ROOT/name) for name in files},jev_model='jev-1.13.0',question=QUESTION,
        thresholds=THRESHOLDS,targets={'fpr_max':.05,'fnr_max':.10,'unknown_max':.05,'code_fp_max':0},
        cutoff_selection='max calibration typed recall among candidates meeting all typed targets; smallest threshold on ties. No eval tuning.',
        scope='single-author curated challenges; no external label independence, no production replay, no P2 admission')
    protocol['sha256']=hashlib.sha256(json.dumps(protocol,sort_keys=True).encode()).hexdigest()
    path=OUT/'protocol.json'
    if path.exists():assert json.loads(path.read_text())==protocol,'Source/protocol changed; cannot resume'
    else:path.write_text(json.dumps(protocol,indent=2)+'\n')
    # Pin the source used for these receipts independently of later code edits.
    snapshot=OUT/'executed-source'
    for name in files:
        dest=snapshot/name
        if not dest.exists():dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes((ROOT/name).read_bytes())
        assert sha(dest)==protocol['sources'][name]
    if args.phase in ['calibration','all']:
        rows=run_split('calibration',protocol)
        grid=[]
        for threshold in THRESHOLDS:
            m=metrics(score_with_threshold(rows,threshold),'combined','typed')
            passed=m['fpr']<=.05 and m['fnr']<=.10 and m['unknown_rate']<=.05
            grid.append(dict(threshold=threshold,metrics=m,provisional_targets_pass=passed))
        eligible=[r for r in grid if r['provisional_targets_pass']]
        chosen=min(eligible,key=lambda r:(-r['metrics']['recall'],r['threshold'])) if eligible else None
        decision=dict(protocol_sha256=protocol['sha256'],threshold=chosen['threshold'] if chosen else None,
            diagnostic_threshold=chosen['threshold'] if chosen else .99,calibration_targets_pass=bool(eligible),
            grid=grid,calibration_legacy={kind:metrics(rows,'legacy',kind) for kind in ['code','typed']},
            calibration_structural={kind:metrics(rows,'structural',kind) for kind in ['code','typed']},training_admission=False)
        decision['sha256']=hashlib.sha256(json.dumps(decision,sort_keys=True).encode()).hexdigest()
        dest=OUT/'frozen-threshold.json'
        if dest.exists():assert json.loads(dest.read_text())==decision,'Cannot tune saved cutoff'
        else:dest.write_text(json.dumps(decision,indent=2)+'\n')
        print(json.dumps({k:v for k,v in decision.items() if k!='grid'},indent=2),flush=True)
    if args.phase in ['eval','all']:
        decision=json.loads((OUT/'frozen-threshold.json').read_text());assert decision['protocol_sha256']==protocol['sha256']
        rows=score_with_threshold(run_split('eval',protocol),decision['diagnostic_threshold'])
        old={kind:metrics(rows,'legacy',kind) for kind in ['code','typed']}
        new={kind:metrics(rows,'combined',kind) for kind in ['code','typed']}
        passed=decision['calibration_targets_pass'] and all(m['fpr']<=.05 and m['fnr']<=.10 and m['unknown_rate']<=.05 for m in new.values()) and new['code']['fp']==0
        typed=[r for r in rows if r['jev_called']];all_receipts=[json.loads(p.read_text()) for p in (OUT/'receipts').glob('*/*/receipt.json')]
        jevs=[r['jev'] for r in all_receipts if r.get('jev',{}).get('status')=='SUCCESS']
        summary=dict(protocol_sha256=protocol['sha256'],threshold_sha256=decision['sha256'],frozen_threshold=decision['threshold'],
            diagnostic_threshold=decision['diagnostic_threshold'],eval_legacy=old,eval_candidate=new,provisional_targets_pass=passed,
            training_eligible_records=0,jev_calls=sum(r['jev_called'] for r in all_receipts),jev_successes=len(jevs),
            jev_input_tokens=sum(j['response']['usage']['input_tokens'] for j in jevs),
            tariff_estimated_cost_usd=sum(j['tariff_estimated_cost_usd'] for j in jevs),actual_billed_cost_usd=None,
            errors=[r for r in rows if r['combined']!=r['expected']],scope=protocol['scope'])
        (OUT/'eval-results.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
        (OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
        print(json.dumps({k:v for k,v in summary.items() if k!='errors'},indent=2),flush=True)


if __name__=='__main__':main()
