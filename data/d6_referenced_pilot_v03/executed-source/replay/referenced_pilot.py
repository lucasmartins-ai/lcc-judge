"""Referenced bounded replay with frozen verifier routing; never P2 admission.

Reuse the stateless executor transport, not old receipts. All twenty contracts
have primary references. Quarantined causal contracts stay UNKNOWN, even when
the executor/legacy grader agrees. Semantic review uses the frozen .50 cutoff.
"""
import argparse
import concurrent.futures
import hashlib
import json
from pathlib import Path
import subprocess
import time

from . import real_pilot
from .outcome_verifier import verify_artifact as candidate
from .pdb_verifier import numeric_verdict,prepare_text_review,combine
from .real_fixtures import PUBLIC_INTERFACES,ROOT_OPTIONS,number
from .tasks import TASKS

ROOT=Path(__file__).resolve().parents[1]
REFERENCES=ROOT/'research/goal-engine-2026-10-04/outcome-references.json'
QUESTION={'consistent':{'type':'noul','instructions':
    'Is the submitted answer materially consistent with the explicit controlled observations in context? Evaluate the whole submitted_answer, including explanation and claimed mechanism. A correct mechanism key does not excuse an explanation that denies the observed cause or asserts a competing cause explicitly ruled out. For quantitative decisions consider the stated budget. This asks consistency with this supplied fixture, not production health.',
    'criteria':{'true':'Answer agrees with the explicit observations and contains no materially contradictory claim.',
                'false':'Answer denies an explicit observation, asserts a ruled-out cause, or contradicts the stated quantitative constraint.'}}}
PDB_QUESTION={'text_consistent':{'type':'noul','instructions':
    'Does the explanation agree with the verified_facts, without claiming protection against involuntary failures? Evaluate only consistency of the explanation with supplied verified arithmetic and scope, not production health. Prefer false for a contradiction.',
    'criteria':{'true':'Explanation agrees with supplied facts and voluntary-disruption scope.',
                'false':'Explanation contradicts supplied facts or promises involuntary-failure protection.'}}}


def structural(task,artifact):
    n=number(task.task_id)
    if n in [3,19]:return {'passed':None,'reason':'reference_contract_quarantined'}
    if n==18:
        if not isinstance(artifact,dict) or artifact.get('status')!='ANSWER':
            return {'passed':False,'reason':'invalid_or_abstained_pdb_answer'}
        if artifact.get('mechanism')!='configure_pdb':return {'passed':False,'reason':'wrong_mechanism'}
        return numeric_verdict(artifact.get('parameters'),replicas=5,quorum=3,drain=1,
                               numeric_claims=artifact.get('numeric_claims'))
    return candidate(task,artifact)


def freeze(out):
    refs=json.loads(REFERENCES.read_text())
    assert {r['task_number'] for r in refs['contracts']}==set(range(1,21))
    assert refs['training_admission'] is False
    files=['replay/referenced_pilot.py','replay/real_pilot.py','replay/real_fixtures.py',
           'replay/tasks.py','replay/outcome_verifier.py','replay/pdb_verifier.py',
           'replay/sandbox.py','replay/sandbox_worker.py','replay/jev_bridge.ts',
           str(REFERENCES.relative_to(ROOT))]
    protocol=dict(version='referenced-replay/0.3',provider=real_pilot.PROVIDER,model=real_pilot.MODEL,
        policy=real_pilot.POLICY,requested_seeds=[42,59,76],generation_seed_applied=False,
        jev_model='jev-1.13.0',jev_role='bounded answer consistency after structural verification',
        semantic_threshold=.5,threshold_selected_on='verifier-calibration/0.1 calibration only',
        pdb_threshold_inherited=True,questions=QUESTION,pdb_question=PDB_QUESTION,
        repeats=3,task_ids=[t.task_id for t in TASKS],quarantined_task_numbers=[3,19],
        files={n:real_pilot.sha(ROOT/n) for n in files},
        client_sha256=real_pilot.sha('/Users/Master/Downloads/LOOKAORCHESTRATOR/src/intelligence/typesafe_client.ts'),
        training_admission=False,independent_human_label_review=False,
        passing_pilot_targets=dict(concordance_min=.95,unknown_max=.10),
        interpretation='conditional curated outcome reliability; known suite; no untouched production confirmation',
        sandbox_image=__import__('replay.sandbox',fromlist=['runtime_identity']).runtime_identity())
    protocol=json.loads(json.dumps(protocol))
    protocol['protocol_sha256']=hashlib.sha256(json.dumps(protocol,sort_keys=True).encode()).hexdigest()
    out.mkdir(parents=True,exist_ok=True)
    path=out/'protocol.json'
    if path.exists(): assert json.loads(path.read_text())==protocol,'Frozen protocol changed'
    else:path.write_text(json.dumps(protocol,indent=2)+'\n')
    archive=out/'executed-source'
    for name in files:
        target=archive/name;target.parent.mkdir(parents=True,exist_ok=True)
        if target.exists():assert real_pilot.sha(target)==protocol['files'][name]
        else:target.write_bytes((ROOT/name).read_bytes())
    return protocol


def run_episode(task,condition,repeat,out,protocol):
    receipt=real_pilot.episode(task,condition,repeat,out,protocol,verifier=structural,diagnostics=False)
    if receipt.get('outcome_review_completed'):return receipt
    directory=out/'episodes'/task.task_id/condition/str(repeat)
    (directory/'execution-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    started=time.perf_counter(); n=number(task.task_id)
    if receipt['verification']['passed'] is True and n not in PUBLIC_INTERFACES:
        packet=json.loads((directory/'packet.json').read_text())
        if n==18:
            reviewed=prepare_text_review(receipt['artifact'],dict(replicas=5,quorum=3,drain=1))
            state=reviewed;questions=PDB_QUESTION;key='text_consistent'
        else:
            state=dict(objective=task.objective,context=packet['context'],
                       submitted_answer=receipt['artifact'],mechanism_meanings=ROOT_OPTIONS)
            questions=QUESTION;key='consistent'
        if state is None:
            receipt['verification']={'passed':False,'reason':'missing_explanation'}
        else:
            request=dict(feature='lcc_judge_referenced_replay',state=state,questions=questions)
            (directory/'jev-request.json').write_text(json.dumps(request,indent=2)+'\n')
            probability=None
            try:
                result=subprocess.run([real_pilot.TSX,str(ROOT/'replay/jev_bridge.ts')],
                    input=json.dumps(request),capture_output=True,text=True,timeout=20)
                (directory/'jev-response.json').write_text(result.stdout)
                (directory/'jev-stderr.txt').write_text(result.stderr)
                response=json.loads(result.stdout);receipt['jev_diagnostic']=response
                if response['status']=='SUCCESS':probability=response['response']['answers'][key]['noul']
            except (ValueError,OSError,subprocess.TimeoutExpired) as exc:
                receipt['jev_diagnostic']={'status':'ERROR','error':str(exc)}
            receipt['verification']=combine(receipt['verification'],probability,protocol['semantic_threshold'])
    receipt['wall_time_s']+=time.perf_counter()-started
    receipt['outcome_review_completed']=True
    receipt['training_eligible']=False
    (directory/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    return receipt


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--out-dir',default='data/d6_referenced_pilot_v03')
    parser.add_argument('--workers',type=int,default=3);args=parser.parse_args()
    out=Path(args.out_dir).resolve();protocol=freeze(out)
    jobs=[(t,c,r) for t in TASKS for c in ['baseline','ablation'] for r in range(3)]
    receipts=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures=[pool.submit(run_episode,t,c,r,out,protocol) for t,c,r in jobs]
        for future in concurrent.futures.as_completed(futures):
            receipts.append(future.result())
            if len(receipts)%6==0:print(f'{len(receipts)}/120 receipts',flush=True)
    # Existing reducer requires a verified baseline plus unanimous three-repeat
    # outcomes. A failed baseline and any unknown/discordance yield UNKNOWN.
    summary=real_pilot.summarize(receipts,out,protocol)
    summary['scope']='Referenced bounded curated replay; expanded Docker code checks; typed consistency after structure; two quarantined contracts'
    summary['pilot_targets_pass']=summary['concordance_rate']>=.95 and summary['unknown_rate']<=.10
    summary['reference_contracts']=20;summary['independent_human_label_review']=False
    summary['training_admission']=False
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps({k:v for k,v in summary.items() if k!='protocol'},indent=2))


if __name__=='__main__':main()
