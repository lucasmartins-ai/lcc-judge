"""Bounded LCC pipeline/outcome diagnostic. Known curated contracts, never P2."""
import argparse
import concurrent.futures
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import random
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'research/goal-engine-2026-10-04/lcc-pareto'
LCC = Path('/Users/Master/LCC')
PROFILES = ['full', 'specialist', 'laya', 'jev']


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prepare():
    from transformers import AutoTokenizer
    from specialist.model import MODERNBERT_REVISION
    from replay.tasks import TASKS
    tok=AutoTokenizer.from_pretrained('answerdotai/ModernBERT-base',revision=MODERNBERT_REVISION,local_files_only=True)
    tasks=[t for t in TASKS if int(t.task_id.split('_')[1]) in [1,2,4,18]]
    grid=[]
    for task in tasks:
        evidence='\n\n'.join(b.content for b in task.blocks)
        for budget in [8192,32768]:
            rng=random.Random(f'pareto-442382:{task.task_id}:{budget}')
            noise=[];count=0
            while count<budget:
                chunk='\n'.join(f'archive-cleaner tick={rng.randrange(100000)} partition={rng.randrange(99)} records={rng.randrange(9999)} checksum=valid state=healthy' for _ in range(16))
                noise.append(chunk);count+=len(tok(chunk,add_special_tokens=False)['input_ids'])
            low,high=0,len(noise)
            while low<high:
                mid=(low+high+1)//2
                text='\n\n'.join(noise[:mid]+[evidence])
                if len(tok(text,add_special_tokens=False)['input_ids'])<=budget:low=mid
                else:high=mid-1
            text='\n\n'.join(noise[:low]+[evidence])
            grid.append(dict(task_id=task.task_id,budget_hf=budget,text=text,
                actual_dossier_hf=len(tok(text,add_special_tokens=False)['input_ids']),
                input_sha256=hashlib.sha256(text.encode()).hexdigest(),
                late_evidence=True,curated_sources=len(task.blocks)))
    sources=['research/lcc_pareto.py','lcc_engine/engine.py','bakeoff/adapters.py',
        'replay/real_pilot.py','replay/real_fixtures.py','replay/referenced_pilot.py',
        'replay/pdb_verifier.py','replay/jev_bridge.ts','replay/tasks.py']
    protocol=dict(schema='lcc-pareto/0.1',task_numbers=[1,2,4,18],profiles=PROFILES,
        budgets_hf=[8192,32768],repeats=3,seed=442382,executor_seeds_applied=False,
        policy='Current LCC threshold .40; trim disabled; one block per judge call; safety protections retained; specialist shadow KEEP only',
        provider_comparison='Operational pipeline policies differ; not isolated model/dtype superiority',
        criteria=dict(outcome_success_min=.90,max_loss_vs_full=.02,min_input_reduction=.25),
        dtype='native CPU fp32; pinned Laya CPU runtime default; Jev remote',threads=8,
        reference_scope='Known curated contracts 1/2/4/18; synthetic unrelated fillers; diagnostic not production confirmation',
        training_admission=False,independent_human_review=False,
        sources={n:sha(ROOT/n) for n in sources},
        lcc_sources={str(p.relative_to(LCC)):sha(p) for p in [LCC/'src/lcc/relevance/compactor.py',LCC/'src/lcc/relevance/blocks.py',LCC/'src/lcc/relevance/laya.py',LCC/'src/lcc/relevance/jev.py']},
        backbone_revision=MODERNBERT_REVISION,checkpoint_sha256=sha(ROOT/'models/exp02e-unfreeze2/weights.pt'),
        laya_revision='052592a15d198d9ad47da779604259b10b47b7aa',jev_model='jev-1.13.0',
        grid_sha256=hashlib.sha256(json.dumps(grid,sort_keys=True).encode()).hexdigest())
    protocol['protocol_sha256']=hashlib.sha256(json.dumps(protocol,sort_keys=True).encode()).hexdigest()
    OUT.mkdir(parents=True,exist_ok=True)
    for name,value in [('protocol.json',protocol),('grid.json',grid)]:
        path=OUT/name;encoded=json.dumps(value,indent=2)+'\n'
        if path.exists():assert path.read_text()==encoded,'Frozen Pareto changed'
        else:path.write_text(encoded)
    for name in sources:
        dest=OUT/'executed-source'/name;dest.parent.mkdir(parents=True,exist_ok=True)
        if not dest.exists():dest.write_bytes((ROOT/name).read_bytes())
        assert sha(dest)==protocol['sources'][name]
    for name,expected in protocol['lcc_sources'].items():
        dest=OUT/'executed-source/lcc'/name;dest.parent.mkdir(parents=True,exist_ok=True)
        if not dest.exists():dest.write_bytes((LCC/name).read_bytes())
        assert sha(dest)==expected
    return protocol,grid,tasks


class JevClient:
    last_resolved_model='jev-1.13.0'
    def __init__(self,directory):self.directory=directory;self.calls=0;self.receipts=[]
    def evaluate(self,state,questions):
        from replay.real_pilot import TSX
        from lcc.relevance.jev import JevRequestError
        self.calls+=1;target=self.directory/f'jev/{self.calls:04d}';target.mkdir(parents=True,exist_ok=True)
        request=dict(feature='lcc_judge_pareto',state=state,questions=questions)
        (target/'request.json').write_text(json.dumps(request,indent=2)+'\n')
        try:
            result=subprocess.run([TSX,str(ROOT/'replay/jev_bridge.ts')],input=json.dumps(request),capture_output=True,text=True,timeout=30)
            (target/'response.json').write_text(result.stdout);(target/'stderr.txt').write_text(result.stderr)
            response=json.loads(result.stdout);self.receipts.append(response)
            if response['status']!='SUCCESS':raise JevRequestError(response.get('error','Jev failed'))
            return response['response']
        except (ValueError,OSError,subprocess.TimeoutExpired) as exc:raise JevRequestError(str(exc)) from exc


class LayaClient:
    def __init__(self):
        from bakeoff.adapters import PinnedLayaAdapter
        self.adapter=PinnedLayaAdapter('pinned',str(Path.home()/'.cache/huggingface/hub/models--convaiinnovations--laya-multilingual/snapshots/052592a15d198d9ad47da779604259b10b47b7aa'))
        start=time.perf_counter();self.adapter.load();self.load_s=time.perf_counter()-start
        self.context_limit=self.adapter.declared_window;self.available_state_tokens=self.context_limit-192
        self.last_resolved_model='laya-multilingual@052592a15d198d9ad47da779604259b10b47b7aa'
        self.calls=[]
    def evaluate(self,state,questions):
        from laya.common import build_sequence
        from lcc.relevance.laya import LayaContextLimitExceededError
        agent=self.adapter._agent
        lengths=[len(build_sequence(agent.tok,state,agent._to_internal(q),max_len=10**9,head_max_len=agent.cfg.get('head_max_len',192))[0]) for q in questions.values()]
        truncated=max(lengths)>self.context_limit
        self.calls.append(dict(actual_tokens=lengths,refused_before_forward=truncated))
        if truncated:raise LayaContextLimitExceededError(max(lengths),max(lengths),self.context_limit)
        return agent.predict(state,questions)


def compile_profiles(protocol,grid):
    sys.path.insert(0,str(LCC/'src'))
    from lcc.relevance.compactor import RelevanceCompactionRequest,compact_context,report_to_dict
    from lcc_engine import ContextEngine
    import torch
    torch.set_num_threads(protocol['threads'])
    engine=None;laya=None
    for profile in PROFILES:
        for item in grid:
            target=OUT/profile/item['task_id']/str(item['budget_hf']);target.mkdir(parents=True,exist_ok=True)
            path=target/'compilation.json'
            if path.exists():
                saved=json.loads(path.read_text());assert saved['protocol_sha256']==protocol['protocol_sha256']
                continue
            client=None;load_s=0
            if profile=='specialist':
                if engine is None:engine=ContextEngine(ROOT/'models/exp02e-unfreeze2')
                client=engine
            elif profile=='laya':
                if laya is None:laya=LayaClient();load_s=laya.load_s
                client=laya
            elif profile=='jev':client=JevClient(target)
            start=time.perf_counter()
            if profile=='full':output=item['text'];report=None
            else:
                task=next(t for t in TASKS_LOCAL if t.task_id==item['task_id'])
                result=compact_context(RelevanceCompactionRequest(text=item['text'],question=task.objective,
                    provider=profile,client=client,threshold=.40,trim_head_chars=0,batch_size=1,max_workers=1,
                    min_block_chars=30,max_block_chars=3000,deterministic_protection=True,
                    enable_sufficiency=False,enable_semantic_verify=False))
                output=result.compacted_text;report=report_to_dict(result.report)
            compiled=dict(protocol_sha256=protocol['protocol_sha256'],profile=profile,task_id=item['task_id'],
                budget_hf=item['budget_hf'],input_sha256=item['input_sha256'],output_sha256=hashlib.sha256(output.encode()).hexdigest(),
                compilation_wall_s=time.perf_counter()-start,additional_load_s=load_s,report=report,
                input_dossier_hf=item['actual_dossier_hf'],same_bytes=output==item['text'],
                laya_calls=laya.calls[-report['calls']:] if profile=='laya' and report['calls'] else [],
                jev_receipts=client.receipts if profile=='jev' else [])
            (target/'compiled.txt').write_text(output);path.write_text(json.dumps(compiled,indent=2)+'\n')
            print('compiled',profile,item['task_id'],item['budget_hf'],round(compiled['compilation_wall_s'],2),flush=True)
        if profile=='laya' and laya is not None:laya.adapter.close();laya=None


def episode(protocol,item,profile,repeat,task):
    from replay.tasks import ContextBlock
    from replay import real_pilot,referenced_pilot
    target=OUT/profile/item['task_id']/str(item['budget_hf'])
    output=(target/'compiled.txt').read_text()
    submitted=replace(task,blocks=[ContextBlock('compiled_context',output,'doc','controlled-dossier')])
    receipt=real_pilot.episode(submitted,'baseline',repeat,target,protocol,verifier=referenced_pilot.structural,diagnostics=False)
    if receipt.get('outcome_review_completed'):return receipt
    directory=target/'episodes'/task.task_id/'baseline'/str(repeat)
    (directory/'execution-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    if receipt['verification']['passed'] is True:
        from replay.real_fixtures import number,ROOT_OPTIONS
        from replay.pdb_verifier import prepare_text_review,combine
        packet=json.loads((directory/'packet.json').read_text())
        pdb=number(task.task_id)==18
        state=prepare_text_review(receipt['artifact'],dict(replicas=5,quorum=3,drain=1)) if pdb else \
            dict(objective=task.objective,context=packet['context'],submitted_answer=receipt['artifact'],mechanism_meanings=ROOT_OPTIONS)
        questions=referenced_pilot.PDB_QUESTION if pdb else referenced_pilot.QUESTION
        if state is None:receipt['verification']=dict(passed=False,reason='missing_explanation')
        else:
            client=JevClient(directory)
            try:
                response=client.evaluate(state,questions);receipt['outcome_jev']=client.receipts[-1]
                p=response['answers']['text_consistent' if pdb else 'consistent']['noul']
            except Exception as exc:receipt['outcome_jev']=dict(status='ERROR',error=str(exc));p=None
            receipt['verification']=combine(receipt['verification'],p,.50)
    receipt['outcome_review_completed']=True;receipt['training_eligible']=False
    (directory/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    return receipt


def outcomes(protocol,grid,tasks):
    jobs=[(item,profile,r,next(t for t in tasks if t.task_id==item['task_id']))
          for item in grid for profile in PROFILES for r in range(3)]
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        futures=[pool.submit(episode,protocol,*job) for job in jobs]
        for index,future in enumerate(concurrent.futures.as_completed(futures),start=1):
            future.result()
            if index%8==0:print(f'{index}/{len(jobs)} outcome receipts',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--phase',choices=['prepare','compile','outcomes','all'],default='all');args=parser.parse_args()
    protocol,grid,TASKS_LOCAL=prepare()
    if args.phase in ['compile','all']:compile_profiles(protocol,grid)
    if args.phase in ['outcomes','all']:outcomes(protocol,grid,TASKS_LOCAL)
