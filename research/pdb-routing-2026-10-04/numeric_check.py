"""Compare candidate arithmetic to upstream Go conversion + independent enumeration."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from replay.pdb_verifier import numeric_verdict,scaled_value
OUT=Path(__file__).resolve().parent


def reference_policy(field,scaled,n,q,drain):
    # Enumerate legal removals, rather than using the candidate's derived formula.
    allowed=[d for d in range(n+1) if (n-d>=scaled if field=='min_available' else d<=scaled)]
    return bool(allowed) and drain in allowed and all(n-d>=q for d in allowed)


def main():
    inputs=[]
    for n in range(1,33):
        values=list(range(-1,n+2))+[str(p)+'%' for p in range(102)]+['060%','005%','+20%',' 20%','20%%','20','-1%',True,False,2.0,2147483648]
        for i,value in enumerate(values):inputs.append({'id':f'{n}:{i}','replicas':n,'value':value})
    text=''.join(json.dumps(r)+'\n' for r in inputs)
    (OUT/'oracle-inputs.jsonl').write_text(text)
    proc=subprocess.run([str(OUT/'pdb-oracle')],input=text,text=True,capture_output=True,check=True)
    (OUT/'oracle-output.jsonl').write_text(proc.stdout)
    outputs=[json.loads(l) for l in proc.stdout.splitlines()];assert len(outputs)==len(inputs)
    conversions=0;policies=0;mismatches=[]
    for item,oracle in zip(inputs,outputs):
        assert item['id']==oracle['id'];n=item['replicas'];value=item['value']
        got=scaled_value(value,n);want=oracle['scaled'] if oracle['valid'] else None
        conversions+=1
        if got!=want:mismatches.append({'stage':'conversion','input':item,'oracle':oracle,'candidate':got})
        for field in ['min_available','max_unavailable']:
            for q in range(1,n+1):
                for drain in [1,2]:
                    expected=oracle['valid'] and reference_policy(field,oracle['scaled'],n,q,drain)
                    actual=numeric_verdict({field:value},n,q,drain)['passed']
                    policies+=1
                    if actual is not expected:mismatches.append({'stage':'policy','input':item,'field':field,'quorum':q,'drain':drain,'expected':expected,'actual':actual})
    summary={'conversion_checks':conversions,'policy_checks':policies,'mismatch_count':len(mismatches),'mismatches':mismatches,
        'upstream_module':'k8s.io/apimachinery@v0.36.0','replica_range':[1,32],
        'candidate_sha256':hashlib.sha256((ROOT/'replay/pdb_verifier.py').read_bytes()).hexdigest(),
        'oracle_binary_sha256':hashlib.sha256((OUT/'pdb-oracle').read_bytes()).hexdigest(),
        'oracle_source_sha256':hashlib.sha256((OUT/'oracle/main.go').read_bytes()).hexdigest(),
        'scope':'upstream int32/percentage conversion plus independently enumerated voluntary-removal policy; not Kubernetes server or selector validation'}
    (OUT/'numeric-verification.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps({k:v for k,v in summary.items() if k!='mismatches'},indent=2))
    if mismatches:sys.exit(1)


if __name__=='__main__':main()
