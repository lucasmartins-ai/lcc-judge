"""Candidate verifier: broader executable contracts, strict quantitative types.

Not a production oracle. Legacy pilot source and receipts stay unchanged.
Semantic probabilities are optional diagnostics; training admission is external.
"""
from __future__ import annotations
import ast
import contextlib
import io
import json
import math
import os
import re
import sqlite3
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
from types import SimpleNamespace

if __name__=='__main__':sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from replay.real_fixtures import EXPECTED_MECHANISMS, PUBLIC_INTERFACES, number


def check_budget(parameters,replicas=5,quorum=3,drain=1):
    if not isinstance(parameters,dict):return False
    fields={k:v for k,v in parameters.items() if v is not None}
    if set(fields) not in [{'min_available'},{'max_unavailable'}]:return False
    key,value=next(iter(fields.items()))
    if type(value) is int:count=value
    elif isinstance(value,str) and re.fullmatch(r'(?:100|[0-9]{1,2})%',value):
        count=math.ceil(int(value[:-1])*replicas/100)
    else:return False
    healthy=count if key=='min_available' else replicas-count
    return quorum<=healthy<=replicas-drain


def typed_constraints(n,artifact,contract=None):
    contract=contract or {}
    if artifact.get('mechanism')!=contract.get('mechanism',EXPECTED_MECHANISMS.get(n)):return False
    params=artifact.get('parameters',{})
    if n==8:
        timeout=params.get('timeout_ms') if isinstance(params,dict) else None
        return type(timeout) in [int,float] and math.isfinite(timeout) and 0<timeout<=contract.get('timeout_budget_ms',1500)
    if n==18:
        return check_budget(params,contract.get('replicas',5),contract.get('quorum',3),contract.get('drain',1))
    return isinstance(artifact.get('answer'),str) and bool(artifact['answer'].strip())


def check_program(n,source):
    tree=ast.parse(source)
    allowed={'contextlib','functools','json','collections','decimal','math','re','threading','time','unittest'}
    for node in ast.walk(tree):
        modules=[x.name.split('.')[0] for x in node.names] if isinstance(node,ast.Import) else [node.module.split('.')[0]] if isinstance(node,ast.ImportFrom) and node.module else []
        if any(m not in allowed for m in modules):raise ValueError('Import outside fixture API')
        if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id in {'open','eval','exec','compile','__import__','input'}:raise ValueError('Call outside fixture API')
        if isinstance(node,ast.Attribute) and node.attr.startswith('__'):raise ValueError('Introspection outside fixture API')
    scope={};exec(compile(tree,'<candidate-program>','exec'),scope)
    checks=[]
    if n==3:
        for ids in [[7,2,5],[41,13,29],[9],[],[12,3,17,1]]:
            acquired=[];changed=[];held=set()
            @contextlib.contextmanager
            def lock(i):
                acquired.append(i);held.add(i)
                try:yield
                finally:held.remove(i)
            def decrement(item):
                assert item.id in held,'reservation outside lock';changed.append(item.id)
            scope.update(lock_item=lock,decrement_stock=decrement)
            scope['reserve_items']([SimpleNamespace(id=i) for i in ids])
            assert acquired==sorted(ids) and sorted(changed)==sorted(ids) and not held
        checks=['five_inventory_inputs','ascending_lock_order','all_reservations_under_lock']
    elif n==6:
        db=sqlite3.connect(':memory:');db.execute('CREATE TABLE users(id INTEGER,tenant_id TEXT,name TEXT)')
        data=[(1,'A','Alice'),(2,'A','Bob'),(3,'B','Alice'),(4,'B',"O'Connor"),(5,'C','Renée'),(6,'A','ALINA')]
        db.executemany('INSERT INTO users VALUES(?,?,?)',data);scope['db']=db
        for tenant,query in [('A','Ali'),('A','Bob'),('B','Alice'),('B',"O'Connor"),('C','Renée'),('C',''),('missing',''),("A' OR 1=1 --",''),('B',"'; DROP TABLE users;--"),('A',"x' OR '1'='1"),('B','%'),('A','_')]:
            reference=list(db.execute('SELECT * FROM users WHERE tenant_id=? AND name LIKE?',(tenant,'%'+query+'%')))
            actual=list(scope['search_users'](tenant,query))
            assert sorted(tuple(r) for r in actual)==sorted(reference),'query, tenant or injection failure'
        assert len(list(db.execute('SELECT * FROM users')))==len(data)
        checks=['twelve_sql_inputs','tenant_isolation','multiple_injections','unicode_apostrophe','table_preserved']
    elif n==10:
        class Redis:
            def __init__(self,lost=False):self.values={};self.events=[];self.lost=lost
            def get(self,key):return self.values.get(key)
            def set(self,key,value,nx=False,ex=None):
                self.events.append((key,nx,ex))
                if nx and self.lost:
                    self.lost=False;self.values[key]=json.dumps({'id':'other-winner','amount':317});return False
                if nx and key in self.values:return False
                self.values[key]=value;return True
        for lost in [False,True]:
            store=Redis(lost);charges=[]
            def create(**kw):
                value={'id':'charge-'+str(len(charges)),**kw};charges.append(value);return value
            scope.update(redis=store,stripe=SimpleNamespace(Charge=SimpleNamespace(create=create)))
            first=scope['process_payment']('novel-17',317)
            second=scope['process_payment']('novel-17',317)
            if lost:
                assert charges==[],'charged despite losing SET NX'
                assert first==second=={'id':'other-winner','amount':317}
            else:
                assert len(charges)==1 and first==second==charges[0]
                assert any(k=='idemp:novel-17' and nx and ttl==120 for k,nx,ttl in store.events)
                other=scope['process_payment']('novel-83',912)
                assert len(charges)==2 and other==charges[1] and charges[1]['amount']==912
        checks=['multiple_keys_amounts','cached_receipt','required_atomic_ttl','lost_nx_does_not_charge']
    elif n==13:
        class DB:
            def __init__(self,balance,credit_error=False):
                self.conn=sqlite3.connect(':memory:',check_same_thread=False)
                self.conn.execute('CREATE TABLE accounts(id INTEGER,balance INTEGER)')
                self.conn.executemany('INSERT INTO accounts VALUES(?,?)',[(11,balance),(23,0)]);self.conn.commit()
                self.lock=threading.RLock();self.inside=threading.local();self.credit_error=credit_error
            @contextlib.contextmanager
            def transaction(self):
                with self.lock:
                    self.inside.active=True
                    try:yield;self.conn.commit()
                    except BaseException:self.conn.rollback();raise
                    finally:self.inside.active=False
            def query(self,sql,account):
                assert getattr(self.inside,'active',False),'read outside transaction'
                return self.conn.execute(re.sub(r'\s+FOR\s+UPDATE','',sql,flags=re.I),(account,)).fetchone()[0]
            def execute(self,sql,amount,account):
                assert getattr(self.inside,'active',False),'write outside transaction'
                if self.credit_error and account==23:raise RuntimeError('injected credit failure')
                return self.conn.execute(sql,(amount,account))
            def balances(self):return [r[0] for r in self.conn.execute('SELECT balance FROM accounts ORDER BY id')]
        for balance,amount,wanted in [(100,100,[0,100]),(500,75,[275,225]),(40,75,[40,0])]:
            db=DB(balance);scope['db']=db;errors=[]
            def worker():
                try:scope['transfer'](11,23,amount)
                except ValueError:pass
                except Exception as exc:errors.append(str(exc))
            threads=[threading.Thread(target=worker) for _ in range(3)]
            for thread in threads:thread.start()
            for thread in threads:thread.join(3)
            assert not errors and not any(t.is_alive() for t in threads) and db.balances()==wanted
        db=DB(200,True);scope['db']=db
        try:scope['transfer'](11,23,75)
        except RuntimeError:pass
        assert db.balances()==[200,0],'partial debit not rolled back'
        checks=['three_concurrent_transfers','two_amounts','insufficient_funds','actual_sql_semantics','failure_rollback']
    elif n==16:
        for rate,capacity,times in [(2.,3,[0,0,0,0,.5,.5,10,10,10,10]),(.5,2,[0,0,0,1,2,2,4,20,20,20]),(4.,1,[0,0,.25,.25,.5,5,5])]:
            clock=[0.];calls=[]
            @scope['rate_limit'](rate,capacity,lambda:clock[0])
            def endpoint():calls.append(1);return 'accepted'
            water=0.;last=0.;expected_calls=0
            for now in times:
                water=max(0.,water-(now-last)*rate);last=now
                allow=water+1<=capacity
                if allow:water+=1;expected_calls+=1
                clock[0]=now;value=endpoint()
                assert value==('accepted' if allow else False) and len(calls)==expected_calls
        checks=['three_rate_capacity_configs','deterministic_trace','no_denied_side_effects','fractional_refill']
    elif n==20:
        class Bucket:
            always=False;recover=True;adjust=0
            def __init__(self,capacity,refill_rate,clock):
                self.cap=capacity+self.adjust;self.rate=refill_rate;self.clock=clock;self.last=clock();self.tokens=self.cap
            def allow(self):
                if self.always:return True
                now=self.clock()
                if self.recover:self.tokens=min(self.cap,self.tokens+(now-self.last)*self.rate)
                self.last=now
                if self.tokens<1:return False
                self.tokens-=1;return True
        scope['test_burst'](Bucket)
        for name,attr in [('always_allow',{'always':True}),('no_refill',{'recover':False}),('short_burst',{'adjust':-1}),('long_burst',{'adjust':1})]:
            mutant=type('Mutant',(Bucket,),attr)
            try:scope['test_burst'](mutant)
            except AssertionError:checks.append(name)
            else:raise AssertionError('generated test accepted '+name)
        checks.insert(0,'correct_bucket_passes')
    else:raise ValueError('No executable contract')
    return checks


def verify_artifact(task,artifact,contract=None,semantic_probability=None,semantic_threshold=None):
    if not isinstance(artifact,dict) or artifact.get('status') not in ['ANSWER','ABSTAIN']:
        return {'passed':None,'reason':'invalid_artifact'}
    if artifact['status']=='ABSTAIN':return {'passed':False,'reason':'abstained'}
    n=number(task.task_id)
    if n not in PUBLIC_INTERFACES:
        if not typed_constraints(n,artifact,contract):return {'passed':False,'reason':'typed_constraint_failure'}
        if semantic_threshold is not None:
            if type(semantic_probability) not in [int,float] or not math.isfinite(semantic_probability):
                return {'passed':None,'reason':'semantic_check_unavailable'}
            if semantic_probability<semantic_threshold:return {'passed':False,'reason':'semantic_check_below_frozen_threshold'}
        return {'passed':True,'reason':'bounded_typed_constraints','semantic_checked':semantic_threshold is not None}
    source=artifact.get('python')
    if not isinstance(source,str) or not source.strip():return {'passed':False,'reason':'missing_program'}
    with tempfile.TemporaryDirectory(prefix='lcc-calibration-check-') as directory:
        try:
            proc=subprocess.run([sys.executable,'-I',str(Path(__file__).resolve()),'--check'],
                input=json.dumps({'task_number':n,'source':source}),text=True,capture_output=True,
                cwd=directory,env={'PATH':os.defpath,'LANG':'C.UTF-8'},timeout=10)
            return json.loads(proc.stdout)
        except subprocess.TimeoutExpired:return {'passed':None,'reason':'verifier_timeout'}
        except (ValueError,OSError):return {'passed':None,'reason':'verifier_process_error'}


if __name__=='__main__':
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
    request=json.load(sys.stdin);captured=io.StringIO()
    try:
        with contextlib.redirect_stdout(captured):checks=check_program(request['task_number'],request['source'])
        result={'passed':True,'reason':'expanded_executable_contract','checks':checks}
    except Exception as exc:result={'passed':False,'reason':'program_failed_contract','error':f'{type(exc).__name__}: {exc}'}
    result['stdout']=captured.getvalue()[-2000:];print(json.dumps(result))
