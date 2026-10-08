"""Pinned passage-ranking recipe, with complete-pair and submission accounting.

Research scores only: no selection policy, probability calibration or LCC default.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import time

import torch


def loading_info_for_json(info):
    """Preserve loader diagnostics while normalizing its runtime set containers."""
    if isinstance(info, dict):
        return {key: loading_info_for_json(value) for key, value in info.items()}
    if isinstance(info, set):
        return [loading_info_for_json(value) for value in sorted(info)]
    if isinstance(info, (list, tuple)):
        return [loading_info_for_json(value) for value in info]
    return info


class PairReranker:
    def __init__(self, model, tokenizer, *, max_pair_tokens=None, batch_size=16):
        declared=model.config.max_position_embeddings
        if getattr(model.config,'model_type',None) in {'roberta','xlm-roberta'}:
            # These position ids begin after the padding index; table row count
            # is not the number of complete non-padding input tokens supported.
            padding=model.config.pad_token_id
            if type(padding) is not int or padding<0:
                raise ValueError('Known RoBERTa padding position required')
            declared-=padding+1
        token_limit=getattr(tokenizer,'model_max_length',declared)
        if type(token_limit) is not int or token_limit<1:
            raise ValueError('Positive integral tokenizer window required')
        declared=min(declared,token_limit)
        window=declared if max_pair_tokens is None else max_pair_tokens
        if (type(window) is not int or not 1<=window<=declared or
                type(batch_size) is not int or batch_size<1 or model.config.num_labels!=1):
            raise ValueError('Valid single-logit model and bounded window/batch required')
        self.model,self.tokenizer=model.eval(),tokenizer
        self.window,self.batch_size=window,batch_size
        self.accounting=dict(counted_tokens=0,submitted_tokens=0,forward_completed_tokens=0,valid_score_tokens=0)

    @classmethod
    def from_snapshot(cls, snapshot, manifest, **kwargs):
        from transformers import AutoModelForSequenceClassification,AutoTokenizer
        snapshot=Path(snapshot)
        for name,expected in manifest['files'].items():
            if hashlib.sha256((snapshot/name).read_bytes()).hexdigest()!=expected:
                raise ValueError(f'Artifact identity mismatch: {name}')
        began=time.perf_counter()
        model,info=AutoModelForSequenceClassification.from_pretrained(
            snapshot,local_files_only=True,trust_remote_code=False,use_safetensors=True,
            dtype=torch.float32,output_loading_info=True)
        # Old BERT snapshots include a deterministic position-id buffer that is
        # nonpersistent in this runtime. No missing learned parameter is allowed.
        if info.get('missing_keys') or set(info.get('unexpected_keys',[]))-{'bert.embeddings.position_ids'} or info.get('mismatched_keys'):
            raise ValueError(f'Incomplete pretrained model: {info}')
        if any(not bool(torch.isfinite(p).all()) for p in model.parameters()):
            raise ValueError('Nonfinite pretrained parameter')
        tokenizer=AutoTokenizer.from_pretrained(snapshot,local_files_only=True,trust_remote_code=False)
        result=cls(model.to('cpu'),tokenizer,**kwargs)
        result.identity=dict(repo_id=manifest['repo_id'],revision=manifest['revision'],
                             model_sha256=manifest['files']['model.safetensors'],
                             parameters=sum(p.numel() for p in model.parameters()),
                             dtype='float32',device='cpu',load_s=time.perf_counter()-began,
                             loading_info=loading_info_for_json(info))
        return result

    def score(self, objectives, texts):
        if (not isinstance(objectives,list) or not isinstance(texts,list) or len(objectives)!=len(texts) or
                any(not isinstance(v,str) for v in objectives+texts)):
            raise ValueError('Matching lists of objective/report strings required')
        lengths=[len(self.tokenizer(q,t,truncation=False)['input_ids']) for q,t in zip(objectives,texts)]
        result=[]
        for q,t,n in zip(objectives,texts,lengths):
            result.append(dict(input_sha256=hashlib.sha256(json.dumps([q,t],sort_keys=True).encode()).hexdigest(),
                               score=None,actual_tokens=n,truncated=False,window_exceeded=n>self.window,
                               submitted=False,forward_completed=False,status='UNKNOWN',
                               error='input_exceeds_window' if n>self.window else None))
        eligible=[i for i,n in enumerate(lengths) if n<=self.window]
        self.accounting['counted_tokens']+=sum(lengths)
        for offset in range(0,len(eligible),self.batch_size):
            indices=eligible[offset:offset+self.batch_size]
            began=time.perf_counter()
            encoded=self.tokenizer([objectives[i] for i in indices],[texts[i] for i in indices],
                                   padding=True,truncation=False,return_tensors='pt')
            encoded={k:v.to('cpu') for k,v in encoded.items()}
            if encoded['attention_mask'].sum(1).tolist()!=[lengths[i] for i in indices]:
                for i in indices:result[i]['error']='token_accounting_mismatch'
                continue
            for i in indices:
                result[i]['submitted']=True
                self.accounting['submitted_tokens']+=lengths[i]
            try:
                with torch.inference_mode():values=self.model(**encoded).logits
                for i in indices:
                    result[i]['forward_completed']=True
                    self.accounting['forward_completed_tokens']+=lengths[i]
                if values.shape!=(len(indices),1):raise ValueError('Expected one raw logit per pair')
                values=values[:,0].detach().cpu()
                for i,value in zip(indices,values):
                    if not bool(torch.isfinite(value)):
                        result[i]['error']='nonfinite_score'
                    else:
                        result[i].update(score=float(value),status='SCORED')
                        self.accounting['valid_score_tokens']+=lengths[i]
            except (ValueError,RuntimeError) as exc:
                for i in indices:result[i]['error']=f'forward_error:{type(exc).__name__}'
            elapsed=time.perf_counter()-began
            for i in indices:result[i]['batch_wall_s']=elapsed
        return result
