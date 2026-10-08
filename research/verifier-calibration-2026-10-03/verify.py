"""Independent stdlib audit of hashes, split isolation, scoring and call receipts."""
import ast
import argparse
import hashlib
import json
import math
import sys
from collections import Counter,defaultdict
from pathlib import Path

OUT=Path(__file__).resolve().parent;ROOT=OUT.parents[1]
sys.path.insert(0,str(ROOT))
from research.archives import verified_sources, read_ledger


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def counts(rows,key,kind):
    subset=[r for r in rows if r['kind']==kind]
    p=sum(r['expected'] for r in subset);n=len(subset)-p
    tp=sum(r['expected'] and r[key] is True for r in subset)
    fp=sum(not r['expected'] and r[key] is True for r in subset)
    fn=sum(r['expected'] and r[key] is False for r in subset)
    u=sum(r[key] is None for r in subset)
    return dict(n=len(subset),positives=p,negatives=n,tp=tp,fp=fp,fn=fn,unknown=u,
        fpr=fp/n,fnr=fn/p,recall=tp/p,unknown_rate=u/len(subset))


def interval(wins,n):
    p=wins/n;z=1.96;denom=1+z*z/n
    c=(p+z*z/(2*n))/denom
    h=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/denom
    return [max(0,c-h),min(1,c+h)]


def main(write_report=False):
    protocol=json.loads((OUT/'protocol.json').read_text());phash=protocol.pop('sha256')
    assert hashlib.sha256(json.dumps(protocol,sort_keys=True).encode()).hexdigest()==phash
    verified_sources(OUT,protocol['sources'])
    assert sha(OUT/'cases-manifest.json')==protocol['manifest_sha256']
    manifest=json.loads((OUT/'cases-manifest.json').read_text())
    cases={}
    for split in ['calibration','eval']:
        path=OUT/(split+'.jsonl')
        assert sha(path)==protocol['case_files'][path.name]==manifest['files'][path.name]
        cases[split]=[json.loads(l) for l in path.read_text().splitlines()]
        assert len(cases[split])==manifest['counts'][split]
    asts={split:{ast.dump(ast.parse(r['artifact']['python']),include_attributes=False) for r in data if r['kind']=='code'} for split,data in cases.items()}
    assert not asts['calibration']&asts['eval']
    ids={split:{r['case_id'] for r in data} for split,data in cases.items()}
    assert not ids['calibration']&ids['eval']
    old_programs=[]
    for p in (ROOT/'data/d6_real_pilot/episodes').glob('*/*/*/receipt.json'):
        r=json.loads(p.read_text());source=(r.get('artifact') or {}).get('python')
        if source:
            try:old_programs.append(ast.dump(ast.parse(source),include_attributes=False))
            except SyntaxError:pass
    overlap={split:len(data&set(old_programs)) for split,data in asts.items()}
    decision=json.loads((OUT/'frozen-threshold.json').read_text());dhash=decision.pop('sha256')
    assert hashlib.sha256(json.dumps(decision,sort_keys=True).encode()).hexdigest()==dhash
    freeze=json.loads((OUT/'pre-eval-freeze.json').read_text())
    assert freeze['eval_receipts_before_dispatch']==0
    assert freeze['frozen_threshold_file_sha256']==sha(OUT/'frozen-threshold.json')
    assert freeze['decision_sha256']==dhash
    rows={};calls=0;tokens=0;ledger_match=[]
    for split,data in cases.items():
        rows[split]=[]
        files=list((OUT/'receipts'/split).glob('*/receipt.json'));assert len(files)==len(data)
        for case in data:
            directory=OUT/'receipts'/split/case['case_id']
            r=json.loads((directory/'receipt.json').read_text())
            assert r['protocol_sha256']==phash and r['training_eligible'] is False
            assert r['case_sha256']==hashlib.sha256(json.dumps(case,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
            assert r['expected']==case['expected'] and r['case_id']==case['case_id']
            assert r['legacy']==r['legacy_verification']['passed'] and r['structural']==r['candidate_verification']['passed']
            value=r['structural']
            if case['kind']=='typed':
                assert r['jev_called'] and sha(directory/'request.json')==r['request_sha256']
                request=json.loads((directory/'request.json').read_text())
                assert request['feature']=='lcc_judge_verifier_calibration'
                assert request['questions']==protocol['question']
                assert request['state']['context']==case['context'] and request['state']['submitted_answer']==case['artifact']
                assert not set(request['state'])&{'expected','rationale','contract','case_id','split','family'}
                api=json.loads((directory/'response.json').read_text())
                assert api==r['jev'] and api['status']=='SUCCESS' and api['response']['model']=='jev-1.13.0'
                assert r['semantic_probability']==api['response']['answers']['consistent']['noul']
                calls+=1;tokens+=api['response']['usage']['input_tokens']
                ledger_match.append((api['response']['usage']['input_tokens'],api['response']['answers']['consistent']['noul']))
                if value is True:value=r['semantic_probability']>=decision['diagnostic_threshold']
            else:assert not r['jev_called']
            r['combined']=value;rows[split].append(r)
    for item in decision['grid']:
        scored=[]
        for r in rows['calibration']:
            c=dict(r);value=c['structural']
            if c['kind']=='typed' and value is True:value=c['semantic_probability']>=item['threshold']
            c['combined']=value;scored.append(c)
        assert counts(scored,'combined','typed')==item['metrics']
    eligible=[r for r in decision['grid'] if r['metrics']['fpr']<=.05 and r['metrics']['fnr']<=.1 and r['metrics']['unknown_rate']<=.05]
    assert decision['threshold']==min(eligible,key=lambda x:(-x['metrics']['recall'],x['threshold']))['threshold']
    summary=json.loads((OUT/'summary.json').read_text())
    computed={kind:counts(rows['eval'],'combined',kind) for kind in ['code','typed']}
    previous={kind:counts(rows['eval'],'legacy',kind) for kind in ['code','typed']}
    assert computed==summary['eval_candidate'] and previous==summary['eval_legacy']
    assert calls==summary['jev_calls']==summary['jev_successes']==140
    assert tokens==summary['jev_input_tokens']==140995
    assert math.isclose(tokens*.042/1e6,summary['tariff_estimated_cost_usd'])
    assert summary['threshold_sha256']==dhash and summary['protocol_sha256']==phash
    results=[json.loads(l) for l in (OUT/'eval-results.jsonl').read_text().splitlines()]
    assert results==rows['eval']
    families=defaultdict(list)
    for r in rows['eval']:families[r['task_number']].append(r)
    per_task={str(n):dict(n=len(data),fp=sum(not r['expected'] and r['combined'] is True for r in data),fn=sum(r['expected'] and r['combined'] is False for r in data),unknown=sum(r['combined'] is None for r in data)) for n,data in families.items()}
    descriptive={kind:dict(fpr_wilson95=interval(m['fp'],m['negatives']),fnr_wilson95=interval(m['fn'],m['positives'])) for kind,m in computed.items()}
    # Ledger audit uses the canonical client side-effect independently of run.py.
    entries=read_ledger(OUT)
    assert all(r['feature']=='lcc_judge_verifier_calibration' and r['model']=='jev-1.13.0' for r in entries)
    assert len(entries)==140 and all(r['status']=='ok' for r in entries)
    assert sum(r['input_tokens'] for r in entries)==tokens
    assert Counter((r['input_tokens'],r['answers']['consistent']['noul']) for r in entries)==Counter(ledger_match)
    output=dict(calibration_cases=len(rows['calibration']),eval_cases=len(rows['eval']),calibration_eval_ast_intersections=0,
        prior_pilot_program_ast_intersections=overlap,frozen_threshold=decision['threshold'],threshold_unchanged_before_eval=True,
        eval_candidate=computed,eval_legacy=previous,per_task=per_task,descriptive_intervals=descriptive,
        jev_calls=calls,jev_input_tokens=tokens,canonical_ledger_entries=len(entries),tariff_estimate_usd=tokens*.042/1e6,
        sources_hash_verified=True,all_training_ineligible=True,
        source_verification_mode='archived',canonical_ledger_scope='run-local-export',
        temporal_preregistration_certified=False,
        population_error_certified=False,production_ground_truth=False)
    if write_report:
        (OUT/'verification.json').write_text(json.dumps(output,indent=2)+'\n')
    print(json.dumps({k:v for k,v in output.items() if k not in ['per_task','descriptive_intervals']},indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--write-report',action='store_true')
    main(parser.parse_args().write_report)
