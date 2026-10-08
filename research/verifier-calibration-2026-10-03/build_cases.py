"""Curated challenge controls; expected labels never sent to Jev.

New responses/inputs, not a novel production population or external human labels.
Positive algorithms share underlying contracts across splits; disclose this dependence.
"""
import hashlib
import ast
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from replay.real_fixtures import EXPECTED_MECHANISMS,ROOT_OPTIONS,PUBLIC_INTERFACES
from replay.tasks import TASKS
OUT=Path(__file__).resolve().parent

GOOD={
3:'''def reserve_items(items):
    ordered=sorted(items,key=lambda item:item.id)
    for item in ordered:
        with lock_item(item.id):
            decrement_stock(item)
''',
6:'''def search_users(tenant_id,query):
    statement='SELECT * FROM users WHERE tenant_id=? AND name LIKE?'
    values=(tenant_id,'%'+query+'%')
    return list(db.execute(statement,values))
''',
10:'''import json
def process_payment(idempotency_key,amount):
    key='idemp:'+idempotency_key
    cached=redis.get(key)
    if cached is not None:return json.loads(cached)
    if not redis.set(key,'pending',nx=True,ex=120):return json.loads(redis.get(key))
    receipt=stripe.Charge.create(amount=amount)
    redis.set(key,json.dumps(receipt),ex=120)
    return receipt
''',
13:'''def transfer(from_acc,to_acc,amount):
    with db.transaction():
        balance=db.query('SELECT balance FROM accounts WHERE id=? FOR UPDATE',from_acc)
        if balance<amount:return False
        db.execute('UPDATE accounts SET balance = balance - ? WHERE id = ?',amount,from_acc)
        db.execute('UPDATE accounts SET balance = balance + ? WHERE id = ?',amount,to_acc)
        return True
''',
16:'''def rate_limit(leak_rate,capacity,clock):
    def decorate(fn):
        tokens=float(capacity)
        last=clock()
        def limited(*args,**kwargs):
            nonlocal tokens,last
            now=clock()
            tokens=min(capacity,tokens+(now-last)*leak_rate)
            last=now
            if tokens<1:return False
            tokens-=1
            return fn(*args,**kwargs)
        return limited
    return decorate
''',
20:'''def test_burst(TokenBucket):
    time=[0.0]
    subject=TokenBucket(4,2,lambda:time[0])
    assert [subject.allow() for _ in range(5)]==[True,True,True,True,False]
    time[0]=0.5
    assert subject.allow()
    assert not subject.allow()
''',
}
ALTERNATE={
3:'''from contextlib import ExitStack
def reserve_items(items):
    items=sorted(items,key=lambda x:x.id)
    with ExitStack() as stack:
        for item in items:stack.enter_context(lock_item(item.id))
        for item in items:decrement_stock(item)
''',
6:'''def search_users(tenant_id,query):
    return db.execute('SELECT * FROM users WHERE tenant_id=:tenant AND name LIKE :pattern',{'tenant':tenant_id,'pattern':'%{}%'.format(query)})
''',
10:'''import json
def process_payment(idempotency_key,amount):
    key='idemp:{}'.format(idempotency_key)
    if redis.set(key,'pending',nx=True,ex=120):
        output=stripe.Charge.create(amount=amount)
        redis.set(key,json.dumps(output),ex=120)
        return output
    return json.loads(redis.get(key))
''',
13:'''def transfer(from_acc,to_acc,amount):
    with db.transaction():
        funds=db.query('SELECT balance FROM accounts WHERE id=? FOR UPDATE',from_acc)
        if funds>=amount:
            db.execute('UPDATE accounts SET balance=balance-? WHERE id=?',amount,from_acc)
            db.execute('UPDATE accounts SET balance=balance+? WHERE id=?',amount,to_acc)
            return True
        return False
''',
16:'''def rate_limit(leak_rate,capacity,clock):
    def decorate(function):
        water=0.0
        previous=clock()
        def wrapper(*args,**kwargs):
            nonlocal water,previous
            current=clock()
            water=max(0,water-(current-previous)*leak_rate)
            previous=current
            if water+1>capacity:return False
            water+=1
            return function(*args,**kwargs)
        return wrapper
    return decorate
''',
20:'''def test_burst(TokenBucket):
    clock=[0.0]
    instance=TokenBucket(capacity=2,refill_rate=4,clock=lambda:clock[0])
    assert instance.allow() and instance.allow()
    assert instance.allow() is False
    clock[0]=0.25
    assert instance.allow() is True
    assert instance.allow() is False
''',
}

CAL_BAD={
3:[('hardcoded_ids','def reserve_items(items):\n    table={x.id:x for x in items}\n    for key in [2,5,7]:\n        with lock_item(key):decrement_stock(table[key])\n','Fails unseen item IDs.'),('no_reservation','def reserve_items(items):\n    return None\n','Never reserves stock.')],
6:[('all_rows','def search_users(tenant_id,query):\n    return db.execute("SELECT * FROM users")\n','Returns other tenants.'),('raw_interpolation',"def search_users(tenant_id,query):\n    return db.execute(f\"SELECT * FROM users WHERE tenant_id='{tenant_id}' AND name LIKE '%{query}%'\")\n",'SQL injection.')],
10:[('no_idempotency','def process_payment(idempotency_key,amount):\n    return stripe.Charge.create(amount=amount)\n','Repeated charge.'),('ignore_lost_nx',GOOD[10].replace("if not redis.set(key,'pending',nx=True,ex=120):return json.loads(redis.get(key))","redis.set(key,'pending',nx=True,ex=120)"),'Charges after losing atomic reservation.')],
13:[('no_transaction',GOOD[13].replace('    with db.transaction():\n','').replace('        ','    '),'Reads/writes without isolation.'),('no_credit',GOOD[13].replace("        db.execute('UPDATE accounts SET balance = balance + ? WHERE id = ?',amount,to_acc)\n",''),'Money disappears.')],
16:[('always_allow','def rate_limit(leak_rate,capacity,clock):\n    return lambda fn:fn\n','Never limits requests.'),('fixed_rate',GOOD[16].replace('(now-last)*leak_rate','(now-last)*2'),'Wrong refill outside rate2.')],
20:[('vacuous_test','def test_burst(TokenBucket):\n    assert True\n','Accepts every mutant.'),('runtime_not_assertion',GOOD[20].replace('    assert [subject.allow() for _ in range(5)]==[True,True,True,True,False]',"    if [subject.allow() for _ in range(5)]!=[True,True,True,True,False]:raise RuntimeError('burst')").replace('    assert subject.allow()',"    if not subject.allow():raise RuntimeError('refill')"),'Fails with RuntimeError instead of asserted behavior.')],
}
EVAL_GOOD={
3:['''def reserve_items(items):
    pending=sorted(items,key=lambda x:x.id,reverse=True)
    while pending:
        item=pending.pop()
        with lock_item(item.id):decrement_stock(item)
''','''def reserve_items(items):
    by_id=dict((element.id,element) for element in items)
    for identifier in sorted(by_id):
        with lock_item(identifier):decrement_stock(by_id[identifier])
'''],
6:['''def search_users(tenant_id,query):
    cursor=db.execute("SELECT * FROM users WHERE tenant_id=? AND name LIKE '%' || ? || '%'",[tenant_id,query])
    return cursor.fetchall()
''','''def search_users(tenant_id,query):
    bindings={'t':tenant_id,'q':query}
    rows=db.execute("SELECT id,tenant_id,name FROM users WHERE tenant_id=:t AND name LIKE '%' || :q || '%'",bindings)
    return tuple(rows)
'''],
10:['''import json
def process_payment(idempotency_key,amount):
    cache_key='idemp:%s'%idempotency_key
    def saved():return json.loads(redis.get(cache_key))
    if redis.get(cache_key) is not None:return saved()
    won=redis.set(cache_key,'pending',ex=120,nx=True)
    if won:
        payment=stripe.Charge.create(amount=amount)
        redis.set(cache_key,json.dumps(payment),ex=120)
        return payment
    return saved()
''','''import json
def process_payment(idempotency_key,amount):
    name='idemp:'+idempotency_key
    reserved=redis.set(name,'pending',ex=120,nx=True)
    if not reserved:
        stored=redis.get(name)
        return json.loads(stored)
    finished=stripe.Charge.create(amount=amount)
    encoded=json.dumps(finished)
    redis.set(name,encoded,ex=120)
    return finished
'''],
13:['''def transfer(from_acc,to_acc,amount):
    with db.transaction():
        current=db.query('SELECT balance FROM accounts WHERE id=? FOR UPDATE',from_acc)
        if amount>current:raise ValueError('insufficient')
        updates=[('UPDATE accounts SET balance=balance-? WHERE id=?',from_acc),('UPDATE accounts SET balance=balance+? WHERE id=?',to_acc)]
        for sql,account in updates:db.execute(sql,amount,account)
        return True
''','''def transfer(from_acc,to_acc,amount):
    def apply():
        if db.query('SELECT balance FROM accounts WHERE id=? FOR UPDATE',from_acc)<amount:return False
        db.execute('UPDATE accounts SET balance = balance - ? WHERE id=?',amount,from_acc)
        db.execute('UPDATE accounts SET balance = balance + ? WHERE id=?',amount,to_acc)
        return True
    with db.transaction():return apply()
'''],
16:['''def rate_limit(leak_rate,capacity,clock):
    def decorator(fn):
        state={'tokens':float(capacity),'at':clock()}
        def decorated(*args,**kwargs):
            at=clock()
            state['tokens']=min(capacity,state['tokens']+(at-state['at'])*leak_rate)
            state['at']=at
            if state['tokens']>=1:
                state['tokens']-=1
                return fn(*args,**kwargs)
            return False
        return decorated
    return decorator
''','''def rate_limit(leak_rate,capacity,clock):
    def install(fn):
        state=[0.0,clock()]
        def run(*args,**kwargs):
            now=clock()
            state[0]=max(0.0,state[0]-(now-state[1])*leak_rate)
            state[1]=now
            allowed=state[0]+1<=capacity
            if not allowed:return False
            state[0]+=1
            return fn(*args,**kwargs)
        return run
    return install
'''],
20:['''def test_burst(TokenBucket):
    timer={'now':0.0}
    bucket=TokenBucket(5,2,lambda:timer['now'])
    for _ in range(5):assert bucket.allow() is True
    assert bucket.allow() is False
    timer['now']=0.5
    assert bucket.allow() is True
    assert bucket.allow() is False
''','''def test_burst(TokenBucket):
    ticks=[0.0]
    tested=TokenBucket(3,4,lambda:ticks[0])
    results=[tested.allow() for _ in range(4)]
    assert results==[True]*3+[False]
    ticks[0]+=0.25
    recovered=[tested.allow(),tested.allow()]
    assert recovered==[True,False]
'''],
}
EVAL_BAD={
3:[('duplicate_reservation',GOOD[3]+'    for item in ordered:\n        with lock_item(item.id):decrement_stock(item)\n','Reserves each item twice.'),('unprotected_decrement','def reserve_items(items):\n    for item in sorted(items,key=lambda x:x.id):decrement_stock(item)\n','No lock held.')],
6:[('bound_but_wrong_tenant',ALTERNATE[6].replace("'tenant':tenant_id","'tenant':'A'"),'Uses fixed tenant.'),('double_escape',GOOD[6].replace("values=(tenant_id,'%'+query+'%')","values=(tenant_id,'%'+query.replace(\"'\",\"''\")+'%')"),'Corrupts apostrophe query despite safe binding.')],
10:[('wrong_amount',ALTERNATE[10].replace('create(amount=amount)','create(amount=100)'),'Charges wrong amount for unseen input.'),('cached_raw_string',ALTERNATE[10].replace('return json.loads(redis.get(key))','return redis.get(key)'),'Returns encoded cache rather than receipt.')],
13:[('fixed_amount',ALTERNATE[13].replace('    with db.transaction():','    amount=100\n    with db.transaction():'),'Transfers wrong amount.'),('allow_overdraft',ALTERNATE[13].replace('if funds>=amount:','if True:'),'Transfers when funds insufficient.')],
16:[('denied_side_effect',ALTERNATE[16].replace('if water+1>capacity:return False','if water+1>capacity:\n                function(*args,**kwargs)\n                return False'),'Invokes denied request.'),('no_cap',GOOD[16].replace('min(capacity,tokens+(now-last)*leak_rate)','tokens+(now-last)*leak_rate'),'Unlimited accumulation after long wait.')],
20:[('no_refill_assertion',ALTERNATE[20].split('    clock[0]=0.25')[0],'No test of regeneration.'),('incorrect_good_bucket_expectation',ALTERNATE[20].replace('assert instance.allow() is False','assert instance.allow() is True'),'Rejects a correct token bucket.')],
}


def case(n,split,family,expected,artifact,rationale,context,contract=None):
    key=hashlib.sha256(json.dumps([n,split,family,artifact],sort_keys=True).encode()).hexdigest()[:16]
    return dict(case_id='c_'+key,split=split,task_number=n,kind='code' if n in PUBLIC_INTERFACES else 'typed',
        family=family,expected=expected,artifact=artifact,rationale=rationale,
        context=context,objective=TASKS[n-1].objective,contract=contract or {},training_eligible=False)


def build():
    result=[]
    for n in GOOD:
        for split in ['calibration','eval']:
            # Distinct ASTs and responses; underlying algorithmic dependence is disclosed.
            positives=[GOOD[n],ALTERNATE[n]] if split=='calibration' else EVAL_GOOD[n]
            for i,source in enumerate(positives):
                result.append(case(n,split,f'{split}_valid_implementation_{i}',True,dict(status='ANSWER',python=source),
                    'Curated implementation of the public behavioral contract.',PUBLIC_INTERFACES[n]))
            for family,source,why in (CAL_BAD if split=='calibration' else EVAL_BAD)[n]:
                result.append(case(n,split,family,False,dict(status='ANSWER',python=source),why,PUBLIC_INTERFACES[n]))
    for n,mechanism in EXPECTED_MECHANISMS.items():
        for split in ['calibration','eval']:
            explanation=ROOT_OPTIONS[mechanism]
            evidence=f'Incident reference {n}-{split}: controlled observations directly establish: {explanation} Independent competing checks rule out gc_pressure and dns_server_down. No production state is claimed.'
            contract={'mechanism':mechanism};positives=[];negatives=[]
            if n==18:
                contract.update(replicas=5 if split=='calibration' else 7,quorum=3 if split=='calibration' else 4,drain=1)
                evidence+=f' Workload has a supported controller, desired replicas={contract["replicas"]}, all healthy; preserve at least{contract["quorum"]} and allow one voluntary eviction. PDB percentages round upwards.'
                positives=[{'min_available':3},{'min_available':'60%'}] if split=='calibration' else [{'max_unavailable':'40%'},{'min_available':4},{'max_unavailable':2}]
                negatives=[('boolean_budget',{'max_unavailable':True}),('too_few_quorum',{'min_available':2})] if split=='calibration' else [('floating_budget',{'max_unavailable':3.0}),('percentage_below_quorum',{'min_available':'40%'}),('no_maintenance',{'max_unavailable':0})]
            elif n==8:
                contract['timeout_budget_ms']=750 if split=='calibration' else 1100
                evidence+=f' Explicit latency trip budget: positive timeout_ms at most {contract["timeout_budget_ms"]}; this does not evaluate a failure-rate circuit policy.'
                positives=[{'timeout_ms':500},{'timeout_ms':750}] if split=='calibration' else [{'timeout_ms':1},{'timeout_ms':1100},{'timeout_ms':900.5}]
                negatives=[('exceeds_new_budget',{'timeout_ms':1000}),('boolean_timeout',{'timeout_ms':True})] if split=='calibration' else [('boundary_excess',{'timeout_ms':1101}),('wrong_timeout_unit',{'timeout_ms':'1s'}),('zero_timeout',{'timeout_ms':0})]
            else:
                positives=[{},{}] if split=='calibration' else [{},{},{}]
                negatives=[('wrong_mechanism',{'mechanism':'gc_pressure'}),('wrong_explanation',{'answer':'The mechanism label is only a placeholder; the actual cause was DNS server outage, and there was no '+explanation})] if split=='calibration' else [
                    ('denies_observed_cause',{'answer':'There is no evidence of '+explanation+' It definitely did not cause the incident.'}),
                    ('adds_false_independent_claim',{'answer':explanation+' Also, DNS server outage was proven to be the cause, despite the independent check showing DNS healthy.'}),
                    ('unsafe_recommendation',{'answer':'Ignore the established diagnosis '+explanation+' The only correct explanation is garbage collection.'})]
            for i,params in enumerate(positives):
                answer=explanation if split=='calibration' else ['Observed cause: '+explanation,'The supplied controlled observations support '+explanation,'Diagnosis: '+explanation][i]
                result.append(case(n,split,f'{split}_valid_answer_{i}',True,dict(status='ANSWER',mechanism=mechanism,parameters=params,answer=answer),
                    'Explicit curated reference and valid quantitative constraints.',evidence,contract))
            for family,details in negatives:
                a=dict(status='ANSWER',mechanism=mechanism,parameters={},answer=explanation)
                if n in [8,18]:a['parameters']=details
                else:a.update(details)
                result.append(case(n,split,family,False,a,'Incorrect according to explicit reference: '+family,evidence,contract))
    return result


if __name__=='__main__':
    rows=build()
    cal=[r for r in rows if r['split']=='calibration'];ev=[r for r in rows if r['split']=='eval']
    assert len(cal)==80 and len(ev)==108
    # Split isolation is exact at source/response level; conceptual dependence remains.
    assert not {json.dumps(r['artifact'],sort_keys=True) for r in cal if r['kind']=='code'} & {json.dumps(r['artifact'],sort_keys=True) for r in ev if r['kind']=='code'}
    def trees(data):return {ast.dump(ast.parse(r['artifact']['python']),include_attributes=False) for r in data if r['kind']=='code'}
    assert not trees(cal)&trees(ev),'Shared program AST across splits'
    for name,data in [('calibration',cal),('eval',ev)]:
        path=OUT/(name+'.jsonl')
        text=''.join(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n' for r in data)
        if path.exists() and path.read_text()!=text:raise ValueError('Frozen cases changed')
        path.write_text(text)
    manifest=dict(counts={'calibration':len(cal),'eval':len(ev)},files={name:hashlib.sha256((OUT/name).read_bytes()).hexdigest() for name in ['calibration.jsonl','eval.jsonl']},
        curation='single-author challenge controls; no independent human annotation',conceptual_algorithm_overlap=True,
        code_ast_split_intersections=0,eval_not_model_queried_before_freeze=True,production_ground_truth=False,training_admission=False)
    (OUT/'cases-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps(manifest,indent=2))
