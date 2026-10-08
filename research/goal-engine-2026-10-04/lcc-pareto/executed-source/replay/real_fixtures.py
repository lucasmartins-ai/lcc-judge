"""Frozen curated outcome contracts, independent of executor and keyword annotations.

These are bounded fixture outcomes, not restored production services. Six coding
cases execute generated Python; fourteen others check typed diagnoses/decisions.
Jev checks are supplementary diagnostics and never decide these outcome labels.
"""
from __future__ import annotations
import ast
import contextlib
import hashlib
import io
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
from types import SimpleNamespace

ROOT_OPTIONS = {
    'pool_connection_leak': 'Connections acquired by a handler are not released.',
    'cache_expiry_stampede': 'Synchronized cache expiration without jitter causes a stampede.',
    'disable_feature_flag': 'Disable the dynamic feature flag rather than roll back the binary.',
    'unclosed_client_session': 'Unclosed client sessions retained by an event listener.',
    'blocked_external_http_no_timeout': 'Consumer thread blocked on an external HTTP call without timeout.',
    'circuit_breaker_timeout': 'Choose a latency trip timeout within the downstream latency budget.',
    'pmtud_blackhole': 'Path MTU discovery blackhole drops certificate fragments.',
    'catastrophic_regex_backtracking': 'Nested regex repetition causes catastrophic backtracking.',
    'open_deleted_file': 'An unlinked log still consumes space because a process holds it open.',
    'online_logical_replication': 'Online logical replication/CDC with a short cutover.',
    'cors_wildcard_credentials': 'Credentialed browser request cannot use wildcard allowed origin.',
    'binary_float_rounding': 'Binary floating-point currency arithmetic causes rounding differences.',
    'configure_pdb': 'Configure a valid Kubernetes PodDisruptionBudget preserving required replicas.',
    'musl_conntrack_dns': 'Musl parallel A/AAAA queries reuse a source port and encounter conntrack drops.',
    'capacity_exhaustion': 'Pool size alone is too small for ordinary demand.',
    'dns_server_down': 'DNS server is unavailable.',
    'gc_pressure': 'Garbage collection pause causes the incident.',
    'deployment_binary_regression': 'Roll back a changed application binary.',
    'tls_certificate_expired': 'TLS certificate expired.',
    'disk_named_files': 'Ordinary named files are filling the filesystem.',
    'kafka_insufficient_partitions': 'Too few Kafka partitions for throughput.',
    'INSUFFICIENT_EVIDENCE': 'The provided context does not support a specific answer.',
}

# Only the verifier uses this mapping. The executor receives a common ontology,
# not a per-task shortlist built from the answer key.
EXPECTED_MECHANISMS = {
    1:'pool_connection_leak', 2:'cache_expiry_stampede', 4:'disable_feature_flag',
    5:'unclosed_client_session', 7:'blocked_external_http_no_timeout',
    8:'circuit_breaker_timeout', 9:'pmtud_blackhole',
    11:'catastrophic_regex_backtracking',12:'open_deleted_file',
    14:'online_logical_replication',15:'cors_wildcard_credentials',
    17:'binary_float_rounding',18:'configure_pdb',19:'musl_conntrack_dns',
}

PUBLIC_INTERFACES = {
    3: 'Define reserve_items(items). Each item has integer .id. Provided globals: lock_item(id) is a context manager and decrement_stock(item) performs the reservation. Return runnable Python implementing the fix.',
    6: 'Define search_users(tenant_id, query). Provided global db is a sqlite3 connection with .execute(sql, parameters=()). Return matching rows (list or cursor). Table users columns: id, tenant_id, name.',
    10:'Define process_payment(idempotency_key, amount). Provided globals: redis has .get(key), .set(key,value,nx=False,ex=None); stripe.Charge.create(amount=...) returns a JSON-compatible receipt. Return that receipt or the cached receipt.',
    13:'Define transfer(from_acc,to_acc,amount). Provided db has .transaction() context manager, .query(sql,account_id) returning numeric balance, .execute(sql, amount, account_id) for balance updates. Return False or raise ValueError on insufficient funds. SQL FOR UPDATE is supported by this fixture.',
    16:'Define rate_limit(leak_rate,capacity,clock) returning a decorator. clock() gives seconds. The decorated callable returns its normal result when admitted and False when denied. Return working Python, including state management.',
    20:'Define test_burst(TokenBucket), a Python test that raises AssertionError when the behavior is incorrect. TokenBucket(capacity,refill_rate,clock) accepts a callable clock() in seconds and has .allow() -> bool. Control time without sleeping.',
}


def number(task_id):
    return int(task_id.split('_')[1])


def make_packet(task, blocks, seed):
    n=number(task.task_id)
    context=[dict(block_id='b_'+hashlib.sha256(b.block_id.encode()).hexdigest()[:8],
                  content=b.content, source=b.source, block_type=b.block_type) for b in blocks]
    packet=dict(objective=task.objective, task_class=task.task_class, context=context,
                interface=PUBLIC_INTERFACES.get(n),
                mechanism_options=ROOT_OPTIONS if n not in PUBLIC_INTERFACES else None)
    if n==8:
        packet['response_contract']='Use parameters.timeout_ms for the latency-trip timeout. This bounded fixture checks the latency budget, not a failure-rate trip policy.'
    if n==18:
        packet['response_contract']='Use parameters.min_available OR parameters.max_unavailable for a valid PDB manifest; do not specify both.'
    return packet


def check_code(n, source):
    """Run adversarial behavioral checks; every call gets fresh state."""
    from replay.sandbox import fixture_namespace
    scope=fixture_namespace(source,'<executor-generated-python>')
    checks=[]
    if n==3:
        acquired, decremented, held=[],[],set()
        @contextlib.contextmanager
        def lock_item(i):
            acquired.append(i);held.add(i)
            try:yield
            finally:held.remove(i)
        def decrement(item):
            assert item.id in held, 'Reservation outside its lock'
            decremented.append(item.id)
        scope.update(lock_item=lock_item,decrement_stock=decrement)
        scope['reserve_items']([SimpleNamespace(id=i) for i in [7,2,5]])
        assert acquired==[2,5,7], f'Inconsistent acquisition order: {acquired}'
        assert sorted(decremented)==[2,5,7] and not held
        checks=['global_lock_order','all_items_reserved_once','locks_released']
    elif n==6:
        db=sqlite3.connect(':memory:')
        db.execute('CREATE TABLE users(id INTEGER, tenant_id TEXT, name TEXT)')
        db.executemany('INSERT INTO users VALUES(?,?,?)',[(1,'A','Alice'),(2,'A','Bob'),(3,'B','Alice')])
        scope['db']=db
        def rows(tenant,query):
            result=scope['search_users'](tenant,query)
            return list(result)
        assert [r[0] for r in rows('A','Ali')]==[1], 'Normal query/tenant filter fails'
        assert rows("A' OR 1=1 --",'')==[], 'Tenant parameter injection succeeds'
        assert rows('A',"' OR 1=1 --")==[], 'Search parameter injection succeeds'
        assert len(list(db.execute('SELECT * FROM users')))==3
        checks=['normal_query','tenant_isolation','tenant_injection','query_injection','table_preserved']
    elif n==10:
        class Redis:
            def __init__(self):self.values={};self.events=[]
            def get(self,key):return self.values.get(key)
            def set(self,key,value,nx=False,ex=None):
                self.events.append(('set',key,nx,ex))
                if nx and key in self.values:return False
                self.values[key]=value;return True
        redis=Redis();charges=[]
        def create(**kw):
            charges.append(kw)
            return dict(id='charge_'+str(len(charges)),amount=kw['amount'])
        scope.update(redis=redis,stripe=SimpleNamespace(Charge=SimpleNamespace(create=create)))
        first=scope['process_payment']('k1',100)
        second=scope['process_payment']('k1',100)
        assert first==second, 'Duplicate did not return the cached receipt'
        assert len(charges)==1, 'Duplicate charged twice'
        assert any(key=='idemp:k1' and nx and ex==120 for _,key,nx,ex in redis.events), 'Missing atomic reservation with required key/TTL'
        third=scope['process_payment']('k2',200)
        assert len(charges)==2 and third!=first
        checks=['duplicate_not_charged','cached_receipt','atomic_key_and_ttl','distinct_key']
    elif n==13:
        class DB:
            def __init__(self):
                self.balances={1:100,2:0};self.lock=threading.RLock();self.local=threading.local();self.barrier=threading.Barrier(3)
            @contextlib.contextmanager
            def transaction(self):
                with self.lock:
                    before=dict(self.balances);self.local.inside=True
                    try:yield
                    except BaseException:self.balances=before;raise
                    finally:self.local.inside=False
            def query(self,sql,account):
                value=self.balances[account]
                if not getattr(self.local,'inside',False):
                    self.barrier.wait(timeout=2)
                return value
            def execute(self,sql,amount,account):
                if 'UPDATE' not in sql.upper():raise ValueError('Unexpected SQL')
                with self.lock:self.balances[account]+=(-amount if ' - ' in sql else amount)
        db=DB();scope['db']=db;errors=[]
        def worker():
            try:scope['transfer'](1,2,100)
            except ValueError:pass
            except BaseException as exc:errors.append(str(exc))
        threads=[threading.Thread(target=worker) for _ in range(3)]
        for thread in threads:thread.start()
        for thread in threads:thread.join(timeout=4)
        assert not any(thread.is_alive() for thread in threads), 'Transfer threads did not terminate'
        assert not errors, errors
        assert db.balances=={1:0,2:100}, f'Double spending or no transfer: {db.balances}'
        checks=['three_concurrent_transfers','no_overdraft','no_money_creation','one_transfer_completes']
    elif n==16:
        clock_value=[0.0];hits=[]
        @scope['rate_limit'](leak_rate=2.0,capacity=3,clock=lambda:clock_value[0])
        def endpoint():hits.append(1);return 'ok'
        assert [endpoint() for _ in range(3)]==['ok']*3
        assert endpoint() is False and len(hits)==3
        clock_value[0]=.5
        assert endpoint()=='ok' and endpoint() is False
        clock_value[0]=10
        assert [endpoint() for _ in range(3)]==['ok']*3 and endpoint() is False
        checks=['burst_capacity','deny_without_execution','fractional_time_recovery','capacity_cap']
    elif n==20:
        class Bucket:
            always=False;recover=True;capacity_adjust=0
            def __init__(self,capacity,refill_rate,clock):
                self.capacity=capacity+self.capacity_adjust;self.rate=refill_rate;self.clock=clock;self.last=clock();self.tokens=self.capacity
            def allow(self):
                if self.always:return True
                now=self.clock()
                if self.recover:self.tokens=min(self.capacity,self.tokens+(now-self.last)*self.rate)
                self.last=now
                if self.tokens<1:return False
                self.tokens-=1;return True
        scope['test_burst'](Bucket)
        for name,attr in [('always_allow',dict(always=True)),('no_refill',dict(recover=False)),('wrong_burst',dict(capacity_adjust=-1))]:
            mutant=type('Mutant',(Bucket,),attr)
            try:scope['test_burst'](mutant)
            except Exception:checks.append('kills_'+name)
            else:raise AssertionError('Generated test accepted '+name)
        checks.insert(0,'correct_bucket_passes')
    else:raise ValueError('No coding fixture')
    return checks


def verify_artifact(task, artifact):
    if not isinstance(artifact,dict):return dict(passed=None,reason='invalid_executor_receipt')
    if artifact.get('status')=='ABSTAIN':return dict(passed=False,reason='executor_abstained')
    if artifact.get('status')!='ANSWER':return dict(passed=None,reason='invalid_artifact_status')
    n=number(task.task_id)
    if n in PUBLIC_INTERFACES:
        source=artifact.get('python')
        if not isinstance(source,str) or not source.strip():return dict(passed=False,reason='no_executable_fix')
        from replay.sandbox import run_check
        result=run_check(n,source,recipe='legacy',timeout=12)
        result['source_sha256']=hashlib.sha256(source.encode()).hexdigest()
        return result
    passed=artifact.get('mechanism')==EXPECTED_MECHANISMS[n]
    details=artifact.get('parameters',{})
    if n==8:
        timeout=details.get('timeout_ms') if isinstance(details,dict) else None
        passed=passed and isinstance(timeout,(int,float)) and not isinstance(timeout,bool) and 0<timeout<=1500
    if n==18:
        fields={k:v for k,v in details.items() if v is not None} if isinstance(details,dict) else {}
        # Preserve >=3 of 5 AND allow a one-node maintenance drain. A more
        # conservative budget is valid too; the task does not demand maximal disruption.
        passed=passed and fields in [{'min_available':3},{'min_available':4},
                                     {'max_unavailable':1},{'max_unavailable':2}]
    return dict(passed=bool(passed),reason='curated_typed_outcome_constraints',
                verifier_kind='curated_answer_assertions',production_environment_replayed=False)


if __name__=='__main__':
    request=json.load(sys.stdin);captured=io.StringIO()
    try:
        with contextlib.redirect_stdout(captured):checks=check_code(request['task_number'],request['source'])
        result=dict(passed=True,reason='executable_fixture_checks',checks=checks)
    except Exception as exc:
        result=dict(passed=False,reason='generated_program_failed_fixture',error=f'{type(exc).__name__}: {exc}')
    result['program_stdout']=captured.getvalue()[-2000:]
    print(json.dumps(result))
