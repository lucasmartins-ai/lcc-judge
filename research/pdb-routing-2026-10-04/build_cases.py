"""New curated text controls; numeric labels use upstream conversion + enumeration."""
import hashlib
import json
import subprocess
from pathlib import Path

OUT=Path(__file__).resolve().parent
SCALES={'development':[4,6,8,10],'eval':[9,11,13,15,17,19,23,29]}


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    cases=[];inputs=[]
    for split,scales in SCALES.items():
        for i,n in enumerate(scales):
            q=n//2+1;drain=1 if i%2==0 else 2;cap=n-q
            context=f'A supported controller has {n} desired replicas, all healthy. Preserve at least {q} replicas while permitting at least {drain} voluntary eviction(s). Percentages round upwards. Maximizing disruptions is not required. A PDB does not prevent involuntary node failures.'
            objective=f'Configure a PDB that preserves quorum ({q}) and permits {drain} voluntary eviction(s).'
            percent=100*cap//n;min_percent=100*q//n
            variants=[
                ('min_quorum',{'min_available':q},f'This budget keeps at least {q} replicas available and permits the requested voluntary maintenance.',True,None),
                ('conservative_max',{'max_unavailable':drain},f'At most {drain} voluntary evictions are allowed, leaving at least {n-drain} healthy replicas. This conservative budget meets the objective; no maximum disruption allowance is required.',True,None),
                ('max_percent',{'max_unavailable':f'{percent}%'},'Rounding up is accounted for in the budget. The required voluntary maintenance is permitted while quorum remains protected.',True,None),
                ('leading_zero_percent',{'max_unavailable':f'{percent:03d}%'},'The percentage is a valid budget representation. It allows the requested eviction count and keeps the quorum intact; it does not guarantee protection against node failure.',True,None),
                ('min_percent',{'min_available':f'{min_percent}%'},f'The rounded minimum keeps at least the required {q} replicas available. Voluntary maintenance remains possible.',True,None),
                ('equivalent_integer',{'max_unavailable':cap},f'The maximum voluntary eviction count is {cap}, with at least {q} replicas remaining. This satisfies both constraints.',True,{'max_disruptions':cap,'min_remaining':q}),
                ('unsafe_quorum',{'max_unavailable':cap+1},'The configuration meets the quorum and maintenance objectives.',False,None),
                ('blocks_maintenance',{'min_available':n},'The configuration permits the requested voluntary maintenance.',False,None),
                ('two_budget_fields',{'min_available':q,'max_unavailable':cap},'Both fields should be set together to meet the objective.',False,None),
                ('wrong_structured_claim',{'max_unavailable':drain},'This is a conservative budget for voluntary maintenance.',False,{'min_remaining':n-drain+1}),
                ('false_numeric_prose',{'max_unavailable':drain},f'This budget allows {drain+1} simultaneous voluntary evictions and guarantees only {n-drain-1} replicas will remain.',False,None),
                ('false_involuntary_guarantee',{'max_unavailable':f'{percent}%'},'This PDB guarantees that involuntary node failures cannot reduce the number of healthy replicas below quorum.',False,None),
                ('denies_quorum_protection',{'min_available':q},f'The requested maintenance is allowed, but this budget permits healthy replicas to fall below {q} during allowed voluntary evictions.',False,None),
                ('denies_maintenance',{'max_unavailable':drain},f'This budget forbids the requested {drain} voluntary eviction(s); maintenance cannot proceed under it.',False,None),
            ]
            for family,parameters,answer,expected,claims in variants:
                cid=f'pdb-{split}-n{n:02d}-{family}'
                artifact={'status':'ANSWER','mechanism':'configure_pdb','parameters':parameters,'answer':answer}
                if claims is not None:artifact['numeric_claims']=claims
                row=dict(case_id=cid,split=split,family=family,expected=expected,objective=objective,context=context,
                    contract=dict(replicas=n,quorum=q,drain=drain,controller_supported=True,healthy=n),artifact=artifact,
                    label_source='upstream conversion + enumerated policy for math; single-author curated contradiction for text',training_eligible=False)
                cases.append(row)
                for key,value in parameters.items():inputs.append(dict(id=cid+':'+key,replicas=n,value=value))
    proc=subprocess.run([str(OUT/'pdb-oracle')],input=''.join(json.dumps(r)+'\n' for r in inputs),text=True,capture_output=True,check=True)
    outputs=[json.loads(l) for l in proc.stdout.splitlines()];assert len(inputs)==len(outputs)
    oracle={r['id']:r for r in outputs}
    for row in cases:
        c=row['contract'];n=c['replicas'];parameters=row['artifact']['parameters']
        valid=len(parameters)==1
        permitted=[]
        for key in parameters:
            response=oracle[row['case_id']+':'+key]
            valid=valid and response['valid']
            if response['valid']:
                s=response['scaled']
                permitted=[d for d in range(n+1) if (n-d>=s if key=='min_available' else d<=s)]
        valid=valid and bool(permitted) and c['drain'] in permitted and all(n-d>=c['quorum'] for d in permitted)
        facts=None
        if valid:
            facts={'min_remaining':n-max(permitted),'max_disruptions':max(permitted)}
            for k,v in row['artifact'].get('numeric_claims',{}).items():valid=valid and type(v) is int and v==facts[k]
        row['reference_numeric_pass']=valid
        row['reference_counts']=facts
        row['text_expected']=row['expected'] if valid else None
        assert valid if row['expected'] else True
        assert valid or row['family'] in ['unsafe_quorum','blocks_maintenance','two_budget_fields','wrong_structured_claim']
    (OUT/'case-oracle-inputs.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in inputs))
    (OUT/'case-oracle-outputs.jsonl').write_text(proc.stdout)
    for split in SCALES:
        path=OUT/(split+'.jsonl');assert not path.exists(),'Cannot overwrite frozen cases'
        path.write_text(''.join(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n' for r in cases if r['split']==split))
    manifest=dict(version='pdb-routing-controls/0.1',scales=SCALES,
        counts={s:sum(r['split']==s for r in cases) for s in SCALES},
        positives={s:sum(r['split']==s and r['expected'] for r in cases) for s in SCALES},
        files={s+'.jsonl':sha(OUT/(s+'.jsonl')) for s in SCALES},
        numeric_reference='k8s.io/apimachinery@v0.36.0 conversion + enumeration of legal removals',
        case_oracle_files={p:sha(OUT/p) for p in ['case-oracle-inputs.jsonl','case-oracle-outputs.jsonl']},
        text_labels='single-author curated; no external annotator or production ground truth',
        disclosure='Shared PDB archetype and wording patterns across scales; eval scales are disjoint. Not IID or novel-archetype certification.')
    (OUT/'cases-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps(manifest,indent=2))


if __name__=='__main__':main()
