"""Offline receipt checks for native HF coverage and the bounded LCC diagnostic."""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import statistics

from research.archives import verified_sources, read_ledger

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'research/goal-engine-2026-10-04'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def strict_auc(pos,neg):
    return sum(p>n for p in pos for n in neg)/(len(pos)*len(neg))


def protocol_checked(directory,key):
    protocol=json.loads((directory/'protocol.json').read_text())
    digest=protocol.pop(key)
    assert hashlib.sha256(json.dumps(protocol,sort_keys=True).encode()).hexdigest()==digest
    verified_sources(directory,protocol['sources'])
    grid=json.loads((directory/'grid.json').read_text())
    assert hashlib.sha256(json.dumps(grid,sort_keys=True).encode()).hexdigest()==protocol['grid_sha256']
    return protocol,digest,grid


def seal(directory):
    path=directory/'preservation-manifest.json';assert not path.exists(),'Preserve existing seal'
    files={str(p.relative_to(directory)):sha(p) for p in sorted(directory.rglob('*'))
           if p.is_file() and '__pycache__' not in p.parts and p.name not in ['audit.json','preservation-manifest.json']}
    path.write_text(json.dumps(dict(files=files,exported_after_execution=True,externally_attested=False),indent=2)+'\n')


def check_seal(directory):
    manifest=json.loads((directory/'preservation-manifest.json').read_text())
    for name,expected in manifest['files'].items():assert sha(directory/name)==expected,f'Evidence changed: {name}'


def frontier():
    directory=OUT/'hf-frontier';check_seal(directory)
    protocol,digest,grid=protocol_checked(directory,'sha256')
    rows=[json.loads(s) for s in (directory/'scores.jsonl').read_text().splitlines()]
    assert len(grid)==len(rows)==744
    for item,row in zip(grid,rows):
        assert row['input_sha256']==item['input_sha256'] and row['protocol_sha256']==digest
        assert row['actual_tokens']==item['actual_pair_tokens']<=item['pair_budget_hf']<=8192
        assert row['forwarded'] is True and row['truncated'] is False and row['error'] is None
        assert math.isfinite(row['logit'])
    result=[]
    for budget in protocol['pair_budgets_hf']:
        selected=[r for r in rows if r['pair_budget_hf']==budget]
        assert len(selected)==186
        groups={k:[r for r in selected if r['kind']==k] for k in ['fact','noise_decoy','noise_unrelated']}
        assert all(len(v)==62 and len({r['case_id'] for r in v})==62 for v in groups.values())
        scores={k:[r['logit'] for r in v] for k,v in groups.items()}
        j=strict_auc(scores['fact'],scores['noise_decoy']);d=strict_auc(scores['fact'],scores['noise_unrelated'])
        result.append(dict(pair_budget_hf=budget,n_cases=62,J=j,D=d,
            actual_pair_tokens_min=min(r['actual_tokens'] for r in selected),actual_pair_tokens_max=max(r['actual_tokens'] for r in selected),
            late_prefix_hf_min=min(r['prefix_tokens_hf'] for r in selected),late_prefix_hf_max=max(r['prefix_tokens_hf'] for r in selected),
            p50_latency_ms=statistics.median(r['latency_ms'] for r in selected),truncated=0,
            passing_J=j>=.90,passing_D=d>=.90))
    return dict(episodes=744,rows=result,passing_budgets_J=[r['pair_budget_hf'] for r in result if r['passing_J']],
        passing_budgets_D=[r['pair_budget_hf'] for r in result if r['passing_D']],
        exploratory=True,whole_evidence_preserved=True,model_window_hf=8192,
        useful_dossier_coverage_established=False,source_verification_mode='archived',temporal_preregistration_certified=False)


def fingerprint(response):
    return (response['usage']['input_tokens'],response['usage']['output_tokens'],
            tuple(sorted((k,v['noul']) for k,v in response['answers'].items())))


def pareto():
    directory=OUT/'lcc-pareto';check_seal(directory)
    protocol,digest,grid=protocol_checked(directory,'protocol_sha256')
    verified_sources(directory,{'lcc/'+n:v for n,v in protocol['lcc_sources'].items()})
    rows=[];sessions=[];semantic_calls=[];compilations=[]
    expected={(item['task_id'],item['budget_hf'],p,r) for item in grid for p in protocol['profiles'] for r in range(3)}
    for item in grid:
        for profile in protocol['profiles']:
            cell=directory/profile/item['task_id']/str(item['budget_hf'])
            compilation=json.loads((cell/'compilation.json').read_text())
            assert compilation['protocol_sha256']==digest and compilation['input_sha256']==item['input_sha256']
            assert sha(cell/'compiled.txt')==compilation['output_sha256']
            if profile in ['full','specialist']:assert compilation['same_bytes'] and compilation['output_sha256']==item['input_sha256']
            if profile=='specialist':
                ranking=compilation['report']['specialist_ranking']
                assert ranking['mode']=='shadow' and all(r['decision']=='KEEP' for r in ranking['items'])
            compilations.append(compilation)
            semantic_calls.extend(j['response'] for j in compilation['jev_receipts'] if j['status']=='SUCCESS')
            prompt_hashes=[]
            for repeat in range(3):
                path=cell/'episodes'/item['task_id']/'baseline'/str(repeat)/'receipt.json'
                receipt=json.loads(path.read_text())
                assert receipt['protocol_sha256']==digest and receipt['outcome_review_completed']
                assert receipt['training_eligible'] is False
                assert sha(path.parent/'query.txt')==receipt['input_sha256']
                prompt_hashes.append(receipt['input_sha256'])
                packet=json.loads((path.parent/'packet.json').read_text())
                assert packet['context'][0]['content']==(cell/'compiled.txt').read_text()
                if receipt['status']=='SUCCESS':
                    terminal=[json.loads(s) for s in (path.parent/'stdout.jsonl').read_text().splitlines()
                              if s.startswith('{') and json.loads(s).get('type')=='result']
                    assert len(terminal)==1 and terminal[0]==receipt['hermes_receipt'] and receipt['tool_events']==0
                    sessions.append(terminal[0]['session_id'])
                else:assert receipt['verification']['passed'] is None
                original=json.loads((path.parent/'execution-receipt.json').read_text())
                reviewed=receipt.get('outcome_jev')
                if reviewed and reviewed['status']=='SUCCESS':
                    assert original['verification']['passed'] is True
                    saved=json.loads((path.parent/'jev/0001/response.json').read_text())
                    assert saved==reviewed
                    key='text_consistent' if item['task_id'].startswith('task_018_') else 'consistent'
                    assert receipt['verification']['passed'] is (reviewed['response']['answers'][key]['noul']>=.50)
                    semantic_calls.append(reviewed['response'])
                elif not reviewed:assert receipt['verification']==original['verification']
                rows.append(dict(task_id=item['task_id'],budget_hf=item['budget_hf'],profile=profile,repeat=repeat,receipt=receipt))
            assert len(set(prompt_hashes))==1,'Repeated input changed'
    assert {(r['task_id'],r['budget_hf'],r['profile'],r['repeat']) for r in rows}==expected and len(rows)==96
    assert len(set(sessions))==len(sessions),'Reused executor session'
    ledger=read_ledger(directory/'ledger')
    actual=Counter((r['input_tokens'],r['output_tokens'],tuple(sorted((k,v['noul']) for k,v in r['answers'].items()))) for r in ledger)
    assert actual==Counter(fingerprint(r) for r in semantic_calls)
    summaries=[]
    for budget in protocol['budgets_hf']:
        full=[r['receipt'] for r in rows if r['budget_hf']==budget and r['profile']=='full']
        base=sum(r['verification']['passed'] is True for r in full)/len(full)
        for profile in protocol['profiles']:
            chosen=[r['receipt'] for r in rows if r['budget_hf']==budget and r['profile']==profile]
            cells=[c for c in compilations if c['budget_hf']==budget and c['profile']==profile]
            success=sum(r['verification']['passed'] is True for r in chosen)/len(chosen)
            reductions=[c['report']['reduction_ratio'] if c['report'] else 0. for c in cells]
            reduced=statistics.mean(reductions)
            costs=[c['compilation_wall_s']+c['additional_load_s'] for c in cells]
            summaries.append(dict(profile=profile,budget_hf=budget,episodes=len(chosen),success_rate=success,
                errors=sum(r['status']=='ERROR' for r in chosen),unknown=sum(r['verification']['passed'] is None for r in chosen),
                delta_success_vs_full=success-base,mean_char_reduction=reduced,
                median_compilation_s=statistics.median(costs),median_executor_s=statistics.median(r['wall_time_s'] for r in chosen),
                cold_load_included_in_first_cell=True,
                cell_compilation_seconds=costs,
                adoption_criteria_pass=success>=.90 and success-base>=-.02 and reduced>=.25))
    successful=[r['receipt']['hermes_receipt'] for r in rows if 'hermes_receipt' in r['receipt']]
    return dict(episodes=96,unique_successful_sessions=len(sessions),rows=summaries,
        canonical_ledger_entries=len(ledger),jev_input_tokens=sum(r['usage']['input_tokens'] for r in semantic_calls),
        hermes_observed_input_tokens=sum(r['tokens']['input'] for r in successful),
        hermes_observed_output_tokens=sum(r['tokens']['output'] for r in successful),
        invoice_cost_known=False,training_eligible_records=0,
        outcome_scope='Four known curated contracts, synthetic late-evidence fillers, three unseeded repeats per cell',
        current_model_identity_mutable=True,
        compilation_cost_scope='One observed pass per cell; includes TSX process startup per Jev call; shared-host concurrent MPS diagnostic',
        review_cost_scope='Semantic oracle is evaluation overhead; executor wall excludes semantic-review latency',
        no_isolated_latency_superiority_claim=True,
        production_replacement_validated=False,temporal_preregistration_certified=False)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--scope',choices=['frontier','pareto','all'],default='all')
    parser.add_argument('--seal',action='store_true');args=parser.parse_args()
    for name,fn,folder in [('frontier',frontier,'hf-frontier'),('pareto',pareto,'lcc-pareto')]:
        if args.scope not in ['all',name]:continue
        if args.seal:seal(OUT/folder)
        result=fn();(OUT/folder/'audit.json').write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(result,indent=2))
