"""Export the once-captured, frozen fresh confirmation through existing helpers."""

from datetime import datetime, timezone
import json
from pathlib import Path
import shutil

from research.audit_tool_relation_confirmation import BASE, audit_design, load
from research.audit_tool_relation_state_supervision import digest, sha
from research.tool_relation_state_supervision import build_rows, write_rows, _save

ROOT = Path(__file__).resolve().parents[1]


def prepare():
    out = BASE/'supervision-v1'
    if out.exists():
        raise ValueError('New immutable final destination required; no overwrite or selective retry')
    design_audit = audit_design(); d = load(BASE/'design-v2/protocol.json')
    upstream = load(BASE.parent/'semantic-next/upstream/artifacts.json')
    token_files = {k:v for k,v in upstream['files'].items() if k not in ('model.safetensors','README.md')}
    snapshot = Path.home()/'.cache/huggingface/hub/models--cross-encoder--mmarco-mMiniLMv2-L12-H384-v1/snapshots'/upstream['revision']
    if any(sha(snapshot/name) != value for name,value in token_files.items()):
        raise ValueError('Pinned tokenizer drift')
    names = ['research/tool_relation_confirmation.py','research/audit_tool_relation_confirmation.py',
             'research/tool_relation_state_supervision.py','research/audit_tool_relation_state_supervision.py',
             'research/measurement_projection.py','research/audit_tool_relation_states.py']
    sources = {name:sha(ROOT/name) for name in names}
    captured = [p for directory in ('design','design-v2','calibration','final') for p in (BASE/directory).rglob('*') if p.is_file() and '__pycache__' not in p.parts]
    files = {str(p.relative_to(BASE)):sha(p) for p in sorted(captured)}
    p = dict(schema='varied-direct-record-fresh-confirmation-supervision/0.1',frozen_at_utc=datetime.now(timezone.utc).isoformat(),
        design_sha256=d['sha256'],capture_design_sha256=d['capture_design_sha256'],design_audit=design_audit,
        sources=sources,capture_files=files,requests=d['requests'],calibration_excluded=d['calibration_excluded'],
        tokenizer=dict(repo_id=upstream['repo_id'],revision=upstream['revision'],files=token_files,window=512),
        compression='gzip JSONL,mtime0,empty filename;full rows/views, no truncation or data omission',
        model_forwards=0,API_calls=0,P2_admission=False,quality_approved=False,default_changed=False,publishing=False)
    p['sha256'] = digest(p); out.mkdir()
    for name in sources:
        target = out/'sources'/name; target.parent.mkdir(parents=True,exist_ok=True); shutil.copyfile(ROOT/name,target)
        if sha(target) != sources[name]:
            raise ValueError('Source changed during freeze')
    _save(out/'protocol.json',p)
    _save(out/'started.json',dict(protocol_sha256=p['sha256'],started_at_utc=datetime.now(timezone.utc).isoformat()))
    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(snapshot,local_files_only=True,trust_remote_code=False)
    population = build_rows('final',load(BASE/'final/raw.json'),d,requests=d['requests'])
    coverage = dict(protocol_sha256=p['sha256'],model_forwards=0,splits={'final':write_rows(out,'final',population,tokenizer)})
    _save(out/'coverage.json',coverage)
    _save(out/'completion.json',dict(protocol_sha256=p['sha256'],finished_at_utc=datetime.now(timezone.utc).isoformat(),model_forwards=0))
    return coverage


if __name__ == '__main__':
    print(json.dumps(prepare(),indent=2,allow_nan=False))
