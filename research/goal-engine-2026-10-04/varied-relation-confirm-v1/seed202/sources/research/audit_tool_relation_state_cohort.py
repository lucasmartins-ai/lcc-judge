"""Independent raw split/calibration audit for varied-state development captures."""

import argparse
from datetime import datetime
import json
from pathlib import Path

from research.audit_tool_relation_states import audit,digest,sha

DEFAULT=Path(__file__).resolve().parent/'goal-engine-2026-10-04/tool-relation-states-v2'


def audit_cohort(base=DEFAULT):
    cohort=json.loads((base/'cohort.json').read_text())
    assert digest({k:v for k,v in cohort.items() if k!='sha256'})==cohort['sha256']
    assert cohort['requests']=={'train':{'seed':442601,'fixtures':64},'validation':{'seed':442602,'fixtures':32}}
    assert cohort['capture_retry'] is False and cohort['model_forwards']==0 and cohort['P2_admission'] is False
    audits={split:audit(base/split) for split in ['calibration','train','validation']}
    sets={};protocols={};rows={}
    for split in audits:
        p=json.loads((base/split/'protocol.json').read_text());protocols[split]=p
        raw=json.loads((base/split/'raw.json').read_text());rows[split]=raw['measurements']['fixtures']
        assert p['runtime']==cohort['runtime'] and p['runtime']['source_sha256']==cohort['source_sha256']
        assert p['runtime']['dependency_sha256']==cohort['dependency_sha256']
        sets[split]={r['fixture_content_sha256'] for r in rows[split]}
        if split!='calibration':
            assert p['request']==cohort['requests'][split]
            assert datetime.fromisoformat(cohort['frozen_at_utc'])<=datetime.fromisoformat(p['frozen_at_utc'])
    assert protocols['calibration']['request']=={'seed':442600,'fixtures':16}
    assert cohort['calibration_excluded']['protocol_sha256']==protocols['calibration']['sha256']
    assert datetime.fromisoformat(json.loads((base/'calibration/completion.json').read_text())['finished_at_utc'])<=datetime.fromisoformat(cohort['frozen_at_utc'])
    overlap={f'{a}:{b}':len(sets[a]&sets[b]) for a,b in [('train','validation'),('train','calibration'),('validation','calibration')]}
    assert not any(overlap.values())
    source_name='research/audit_tool_relation_state_cohort.py';source_path=Path(__file__)
    return dict(status='PASS',cohort_sha256=cohort['sha256'],audit_source_sha256=sha(source_path),
        captures=audits,fixture_content_intersections=overlap,development_fixtures=96,development_fields=1728,
        calibration_fixtures=16,calibration_fields=288,calibration_excluded=True,model_forwards=0,
        tools_reexecuted_during_audit=False,P2_admission=False,default_changed=False,
        audit_source=source_name,scope='Authored actual varied-state development fixtures; raw split/content only, no effective-input/label/token or model-quality certification')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--base',type=Path,default=DEFAULT);args=parser.parse_args()
    print(json.dumps(audit_cohort(args.base),indent=2,allow_nan=False))
