"""Current-tokenizer coverage against saved training configuration, no retraining."""
from collections import Counter
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'research/goal-engine-2026-10-04'


def run():
    from transformers import AutoTokenizer
    from specialist.corpus import DOMAINS
    config_path=ROOT/'models/exp02e-unfreeze2/config.json'
    cfg=json.loads(config_path.read_text());revision='8949b909ec900327062f0ebf497f51aef5e6f0c8'
    tok=AutoTokenizer.from_pretrained(cfg['model_id'],revision=revision,local_files_only=True)
    data=ROOT/'data/exp02e/train.jsonl';rows=[json.loads(s) for s in data.read_text().splitlines()]
    domains={d.name:d for d in DOMAINS};lengths=[];counts=Counter();details=[]
    for row in rows:
        full=tok(row['objective'],row['text'],truncation=False)
        length=len(full['input_ids']);lengths.append(length)
        if length>cfg['max_len']:counts['full_pairs_over_training_limit']+=1
        if row['kind']=='neg_unrelated':continue
        domain=domains[row['domain']];fields=domain.anomaly if row['kind']=='pos' else domain.healthy
        spans=[];offset=0
        for line in row['text'].splitlines(keepends=True):
            if all(f'{k}={v}' in line for k,v in fields.items()):spans.append((offset,offset+len(line.rstrip('\n'))))
            offset+=len(line)
        assert len(spans)==1,'Unambiguous authored line required'
        counts[row['kind']+'_related_lines']+=1
        encoded=tok(row['objective'],row['text'],truncation=True,max_length=cfg['max_len'],return_offsets_mapping=True)
        visible=max(b for (a,b),segment in zip(encoded['offset_mapping'],encoded.sequence_ids()) if segment==1)
        start,end=spans[0]
        if end>visible:
            reason='entire_line_missing' if start>=visible else 'line_partially_cut'
            counts[row['kind']+'_'+reason]+=1
            details.append(dict(id=row['id'],kind=row['kind'],domain=row['domain'],actual_hf=length,
                                visible_text_character_end=visible,evidence_line_character_start=start,
                                evidence_line_character_end=end,coverage=reason))
    result=dict(n=len(rows),config_training_max_len=cfg['max_len'],actual_hf_min=min(lengths),actual_hf_max=max(lengths),
        counts=dict(counts),affected_related_lines=details,
        data_sha256=hashlib.sha256(data.read_bytes()).hexdigest(),config_sha256=hashlib.sha256(config_path.read_bytes()).hexdigest(),
        analysis_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),tokenizer_revision=revision,
        historical_training_reexecuted=False,historical_tokenizer_identity_certified=False,
        loss_causality_established=False,scope='Current pinned tokenizer and saved training max_len; exact complete-line coverage, not outcome necessity or a causal training diagnosis')
    (OUT/'training-input-coverage-details.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='affected_related_lines'},indent=2))


if __name__=='__main__':run()
