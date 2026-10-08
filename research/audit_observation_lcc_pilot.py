"""Independent stdlib audit of frozen LCC observation workflow outcome receipts."""
from __future__ import annotations
from collections import Counter
import hashlib
import json
from pathlib import Path
import random
import statistics

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'research/goal-engine-2026-10-04/observation-lcc-pilot'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _strict_object(pairs):
    result = {}
    for key,value in pairs:
        if key in result:raise ValueError('Duplicate key')
        result[key]=value
    return result


def reduce_answer(expected,text):
    def reject(v):raise ValueError('Non-finite number')
    try:
        answer=json.loads(text,object_pairs_hook=_strict_object,parse_constant=reject)
        if set(answer)!={'status','observations','unresolved'} or answer['status']!='ANSWER':return False
        if not isinstance(answer['observations'],list) or not isinstance(answer['unresolved'],list):return False
        obs=[]
        for row in answer['observations']:
            if not isinstance(row,dict) or set(row)!={'time','value','unit'}:return False
            if type(row['value']) not in [int,float] or type(row['time']) is not str or type(row['unit']) is not str:return False
            # Expected finite fixture values make extra/nonfinite values fail set equality.
            obs.append((row['time'],row['value'],row['unit']))
        wanted={(r['time'],r['value'],r['unit']) for r in expected['observations']}
        flags=answer['unresolved']
        if any(type(f) is not str for f in flags):return False
        return set(obs)==wanted and len(obs)==len(set(obs)) and set(flags)==set(expected['unresolved']) and len(flags)==len(set(flags))
    except (ValueError,TypeError,KeyError,OverflowError):return False


def percentile(values,p):
    values=sorted(values)
    position=(len(values)-1)*p
    low=int(position);high=min(low+1,len(values)-1)
    return values[low]+(values[high]-values[low])*(position-low)


def intervals(per_task,seed=442405):
    rng=random.Random(seed);domains=sorted(per_task);samples=[]
    for _ in range(2000):
        picked=rng.choices(domains,k=len(domains))
        samples.append([statistics.mean(per_task[d][i] for d in picked) for i in [0,1]])
    return dict(success_95=[percentile([r[0] for r in samples],.025),percentile([r[0] for r in samples],.975)],
                paired_loss_95=[percentile([r[1] for r in samples],.025),percentile([r[1] for r in samples],.975)])


def audit():
    protocol=json.loads((OUT/'protocol.json').read_text())
    unsigned={k:v for k,v in protocol.items() if k!='protocol_sha256'}
    assert hashlib.sha256(json.dumps(unsigned,sort_keys=True).encode()).hexdigest()==protocol['protocol_sha256']
    for mapping,prefix in [(protocol['sources'],''),(protocol['lcc_sources'],'lcc/')]:
        for name,expected in mapping.items():assert sha(OUT/'executed-source'/prefix/name)==expected
    assert sha(OUT/'final-data.jsonl')==protocol['reference_data_sha256']
    data=[json.loads(line) for line in (OUT/'final-data.jsonl').read_text().splitlines()]
    grid=json.loads((OUT/'grid.json').read_text())
    assert hashlib.sha256(json.dumps(grid,sort_keys=True).encode()).hexdigest()==protocol['grid_sha256']
    order=json.loads((OUT/'execution-order.json').read_text())
    assert len(order)==144 and len({(r['task_id'],r['budget'],r['profile'],r['repeat']) for r in order})==144
    summary=json.loads((OUT/'summary.json').read_text())
    compiled={};graded={};episode_count=0;jev=[];executor_tokens=Counter();tokens_by_cell={}
    for cell in grid:
        assert hashlib.sha256(cell['text'].encode()).hexdigest()==cell['input_sha256']
        originals=[r for r in data if r['request']==cell['request']]
        assert originals and {r['domain'] for r in originals}=={cell['domain']}
        present=[r for r in originals if r['text'] in cell['text']]
        expected=[r['observations'][0] for r in present if r['label']==1]
        assert {(r['time'],r['value'],r['unit']) for r in expected}=={(r['time'],r['value'],r['unit']) for r in cell['expected']['observations']}
        flags=[]
        if any(r['observations'][0].get('entity_candidates') for r in present):flags.append('entity')
        if any(r['observations'][0]['time'] is None for r in present):flags.append('time')
        assert flags==cell['expected']['unresolved']
        assert cell['critical_texts']==[r['text'] for r in present if r['label']!=0]
        assert cell['unknown_texts']==[r['text'] for r in present if r['label'] is None]
        for profile in protocol['profiles']:
            target=OUT/profile/cell['task_id']/str(cell['budget_cl100k'])
            saved=json.loads((target/'compilation.json').read_text())
            output=(target/'compiled.txt').read_text()
            assert saved['protocol_sha256']==protocol['protocol_sha256'] and saved['input_sha256']==cell['input_sha256']
            assert hashlib.sha256(output.encode()).hexdigest()==saved['output_sha256']
            assert len(output.encode())==saved['output_bytes'] and len(cell['text'].encode())==saved['input_bytes']
            assert abs(saved['removed_bytes_fraction']-(1-len(output.encode())/len(cell['text'].encode())))<1e-12
            critical=sum(text in output for text in cell['critical_texts'])/len(cell['critical_texts'])
            unknown=sum(text in output for text in cell['unknown_texts'])/len(cell['unknown_texts']) if cell['unknown_texts'] else 1.
            assert saved['critical_coverage']==critical and saved['unknown_retention']==unknown
            if profile=='full':assert output==cell['text']
            if profile=='observations':
                cuts=[]
                for item in saved['report']['decisions']:
                    fragment=cell['text'][item['character_start']:item['character_end']]
                    assert hashlib.sha256(fragment.encode()).hexdigest()==item['text_sha256']
                    assert item['decision']==('DROP' if item['status']=='NO_MATCH' else 'KEEP')
                    if item['decision']=='DROP':cuts.append((item['character_start'],item['character_end']))
                cursor=0;kept=[]
                for a,b in sorted(cuts):
                    assert a>=cursor
                    kept.append(cell['text'][cursor:a]);cursor=b
                kept.append(cell['text'][cursor:]);assert ''.join(kept)==output
            if profile=='jev':
                responses=[]
                for path in sorted((target/'jev').glob('*/response.json')):
                    response=json.loads(path.read_text())
                    request=json.loads(path.with_name('request.json').read_text())
                    assert request['feature']==protocol['jev_feature']
                    if response.get('status')=='SUCCESS':responses.append(response)
                assert responses==saved['jev_receipts']
                jev.extend(responses)
            compiled[(cell['budget_cl100k'],profile,cell['task_id'])]=saved
            for repeat in range(protocol['repeats']):
                directory=target/'episodes'/str(repeat)
                receipt=json.loads((directory/'receipt.json').read_text())
                assert receipt['protocol_sha256']==protocol['protocol_sha256'] and receipt['training_admission'] is False
                packet=json.loads((directory/'packet.json').read_text())
                assert packet==dict(request=cell['request'],context=output)
                query=(directory/'query.txt').read_text()
                assert query==protocol['policy']+'\nTASK DATA:\n'+json.dumps(packet)
                assert hashlib.sha256(query.encode()).hexdigest()==receipt['input_sha256']
                events=[]
                for line in (directory/'stdout.jsonl').read_text().splitlines():
                    try:events.append(json.loads(line))
                    except ValueError:pass
                finals=[e for e in events if e.get('type')=='result']
                if receipt['status']=='SUCCESS':
                    assert len(finals)==1 and receipt['returncode']==0 and not any(e.get('type')=='tool_use' for e in events)
                    assert receipt['hermes_receipt']==finals[0]
                    passed=reduce_answer(cell['expected'],finals[0]['text'])
                    assert passed==receipt['verification']['passed']
                    usage=finals[0].get('tokens',{})
                    assert all(type(usage.get(k)) is int and usage[k]>=0 for k in ['input','output','cache_read','cache_write','total'])
                    assert usage['total']==sum(usage[k] for k in ['input','output','cache_read','cache_write'])
                    executor_tokens.update(usage)
                    tokens_by_cell.setdefault((cell['budget_cl100k'],profile),Counter()).update(usage)
                else:
                    assert receipt['verification']['passed'] is None
                    passed=False
                graded[(cell['budget_cl100k'],profile,cell['task_id'],repeat)]=passed
                episode_count+=1
    assert episode_count==144
    computed={}
    for budget in protocol['budgets_cl100k']:
        computed[budget]={}
        tasks=[c['task_id'] for c in grid if c['budget_cl100k']==budget]
        for profile in protocol['profiles']:
            values=[graded[(budget,profile,t,r)] for t in tasks for r in range(3)]
            full=[graded[(budget,'full',t,r)] for t in tasks for r in range(3)]
            success=statistics.mean(values);loss=statistics.mean(full)-success
            stats=summary['by_budget'][str(budget)][profile]
            assert abs(success-stats['success_rate'])<1e-12 and abs(loss-stats['loss_vs_full'])<1e-12
            cs=[compiled[(budget,profile,t)] for t in tasks]
            removal=statistics.mean(c['removed_bytes_fraction'] for c in cs)
            assert abs(removal-stats['removed_bytes_mean'])<1e-12
            criterion=protocol['criteria']
            gate=(success>=criterion['outcome_success_min'] and loss<=criterion['loss_vs_full_max'] and
                  removal>=criterion['removed_bytes_min'] and min(c['critical_coverage'] for c in cs)==1. and min(c['unknown_retention'] for c in cs)==1.)
            assert gate==stats['provisional_point_gate']
            per_task={t:(statistics.mean(graded[(budget,profile,t,r)] for r in range(3)),
                         statistics.mean(int(graded[(budget,'full',t,r)])-int(graded[(budget,profile,t,r)]) for r in range(3))) for t in tasks}
            computed[budget][profile]=dict(success_rate=success,loss_vs_full=loss,point_gate=gate,**intervals(per_task))
    ledger=[json.loads(line) for line in (OUT/'ledger/canonical-ledger.jsonl').read_text().splitlines()]
    def fingerprint(model,tokens,answers):
        return json.dumps(dict(model=model,input_tokens=tokens,answers=answers),sort_keys=True)
    expected=Counter(fingerprint(r['response']['model'],r['response']['usage']['input_tokens'],
                                {q:{'noul':v['noul']} for q,v in r['response']['answers'].items()}) for r in jev)
    actual=Counter(fingerprint(r['model'],r['input_tokens'],r['answers']) for r in ledger)
    assert expected==actual
    manifest=json.loads((OUT/'ledger/ledger-manifest.json').read_text())
    assert sha(OUT/'ledger/canonical-ledger.jsonl')==manifest['export_sha256']
    return dict(schema='observation-lcc-outcome-audit/0.1',all_sources_and_raw_outcomes_verified=True,episodes=144,
                successful_jev_calls=len(jev),jev_input_tokens=sum(r['input_tokens'] for r in ledger),
                observed_executor_tokens=dict(executor_tokens),
                executor_input_including_cache=executor_tokens['input']+executor_tokens['cache_read']+executor_tokens['cache_write'],
                usage_by_budget_profile={str(b):{p:dict(tokens_by_cell[(b,p)]) for p in protocol['profiles']} for b in protocol['budgets_cl100k']},
                token_accounting='Hermes input is uncached input; cache_read/cache_write are reported separately. No invoice or token-rate assumptions.',
                intervals=computed,
                interval_scope='2000 task-cluster percentile draws, seed442405; six exposed synthetic tasks and mutable executor; descriptive only',
                ground_truth='exact declared P1 observations/unknown flags; no human/production/P2 labels',
                API_calls_during_audit=0)


if __name__=='__main__':
    result=audit();(OUT/'audit.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
