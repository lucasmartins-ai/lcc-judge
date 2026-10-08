"""Independent reconstruction of typed dossier receipt hashes and P1 coverage."""
import hashlib
import json
from pathlib import Path
import statistics

import tiktoken

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'research/goal-engine-2026-10-04/observation-frontier'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    protocol = json.loads((OUT/'protocol.json').read_text())
    for path, expected in protocol['sources'].items():
        assert sha(OUT/'executed-source'/path) == expected
    assert sha(OUT/'final-data.jsonl') == protocol['source_data_sha256']
    data = [json.loads(line) for line in (OUT/'final-data.jsonl').read_text().splitlines()]
    result = json.loads((OUT/'results.json').read_text())
    assert len(result['rows']) == 18 and len({(r['domain'],r['requested_budget_cl100k']) for r in result['rows']}) == 18
    tokenizer = tiktoken.get_encoding('cl100k_base')
    for receipt in result['rows']:
        originals = [r for r in data if r['group'] == receipt['group']]
        assert len(originals) == 7
        req = originals[0]['request']
        blocks = []
        for block_index in range(receipt['block_count'] - 7):
            index = block_index * 8
            records = [dict(time=req['start'],level='ERROR',entity=f'archive-{index+j:08x}',
                            field=req['field'],value=99,unit='count') for j in range(8)]
            text = '\n'.join(json.dumps(row,sort_keys=True) for row in records)
            blocks.append(dict(id=f'prefix-{index:08x}',text=text,label=0))
        blocks.extend(dict(id=r['id'],text=r['text'],label=r['label']) for r in originals)
        assert len(blocks) == receipt['block_count']
        decisions = {r['id']:r for r in receipt['decisions']}
        assert len(decisions) == len(blocks)
        for block in blocks:
            d = decisions[block['id']]
            assert d['text_sha256'] == hashlib.sha256(block['text'].encode()).hexdigest()
            assert d['status'] == {0:'NO_MATCH',1:'MATCH',None:'UNKNOWN'}[block['label']]
            assert d['decision'] == ('DROP' if block['label'] == 0 else 'KEEP')
        kept = set(receipt['kept_ids'])
        full = '\n\n'.join(r['text'] for r in blocks)
        candidate = '\n\n'.join(r['text'] for r in blocks if r['id'] in kept)
        assert receipt['full_sha256'] == hashlib.sha256(full.encode()).hexdigest()
        assert receipt['candidate_sha256'] == hashlib.sha256(candidate.encode()).hexdigest()
        assert receipt['actual_dossier_tokens'] == len(tokenizer.encode(full)) <= receipt['requested_budget_cl100k']
        assert receipt['candidate_tokens'] == len(tokenizer.encode(candidate))
        assert receipt['input_bytes'] == len(full.encode()) and receipt['candidate_bytes'] == len(candidate.encode())
        assert abs(receipt['removed_byte_fraction']-(1-len(candidate.encode())/len(full.encode()))) < 1e-12
        assert receipt['known_observation_coverage'] == receipt['unknown_retention'] == 1.
    audit = dict(rows=18, all_context_hashes_reconstructed=True, all_decisions_match_typed_annotations=True,
                 all_dossier_token_counts_reproduced=True, API_calls=0,
                 scope='typed synthetic observation retrieval; no external ground truth or latency remeasurement')
    (OUT/'audit.json').write_text(json.dumps(audit,indent=2)+'\n')
    print(json.dumps(audit,indent=2))


if __name__ == '__main__':
    main()
