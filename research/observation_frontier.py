"""Bounded exact-observation workflow at long dossier sizes, without APIs.

This is P1 preservation of declared record observations, not P2 necessity and not
proof of arbitrary LCC diagnosis. Source/data freeze before measured dispatch.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import platform
import resource
import statistics
import time

import tiktoken
from lcc_engine.observations import ObservationEngine, ObservationRequest

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'research/goal-engine-2026-10-04/observation-frontier'
DATA = ROOT / 'research/goal-engine-2026-10-04/direct-relevance-v1/final.jsonl'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def freeze():
    sources = ['research/observation_frontier.py', 'lcc_engine/observations.py']
    protocol = dict(schema='typed-observation-frontier/0.1', budgets_cl100k=[8192, 32768, 131072],
                    repeats=3, source_data_sha256=sha(DATA), groups='first group per each of six final domains',
                    policy='NO_MATCH drops; MATCH/UNKNOWN keeps whole bytes; explicit caller slots only',
                    criteria=dict(known_observation_coverage=1., unknown_retention=1., removed_bytes_min=.25),
                    ground_truth='typed synthetic record annotations; no executor or production outcome',
                    scope='six known authored held-out-field fixtures in supported grammars; not broad semantic capability',
                    sources={name: sha(ROOT / name) for name in sources})
    OUT.mkdir(exist_ok=True)
    encoded = json.dumps(protocol, indent=2, sort_keys=True) + '\n'
    if (OUT / 'protocol.json').exists():
        assert (OUT / 'protocol.json').read_text() == encoded
    else:
        (OUT / 'protocol.json').write_text(encoded)
    for name in sources:
        target = OUT / 'executed-source' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            assert sha(target) == protocol['sources'][name]
        else:
            target.write_bytes((ROOT / name).read_bytes())
    (OUT / 'final-data.jsonl').write_bytes(DATA.read_bytes()) if not (OUT / 'final-data.jsonl').exists() else None
    assert sha(OUT / 'final-data.jsonl') == protocol['source_data_sha256']
    return protocol


def make_dossier(rows, budget, tokenizer):
    request = rows[0]['request']
    critical = [dict(id=r['id'], text=r['text']) for r in rows]
    tail = '\n\n'.join(b['text'] for b in critical)
    blocks, current = [], len(tokenizer.encode(tail))
    index = 0
    # Whole records in bounded eight-line blocks; requested entity never occurs.
    while True:
        lines = [json.dumps(dict(time=request['start'], level='ERROR', entity=f'archive-{index+j:08x}',
                                  field=request['field'], value=99, unit='count'), sort_keys=True) for j in range(8)]
        text = '\n'.join(lines)
        added = len(tokenizer.encode(text + '\n\n'))
        if current + added > budget:
            break
        blocks.append(dict(id=f'prefix-{index:08x}', text=text))
        current += added
        index += 8
    blocks.extend(critical)
    full = '\n\n'.join(b['text'] for b in blocks)
    actual = len(tokenizer.encode(full))
    assert actual <= budget and budget - actual < 800
    return blocks, full, actual


def main():
    protocol = freeze()
    result_path = OUT / 'results.json'
    if result_path.exists():
        raise ValueError('Completed receipt exists; audit it, do not silently repeat')
    partial = OUT / 'rows.jsonl'
    if partial.exists():
        raise ValueError('Partial receipt exists; inspect before any new run')
    data = [json.loads(line) for line in DATA.read_text().splitlines()]
    first = {}
    for row in data:
        first.setdefault(row['domain'], row['group'])
    tokenizer = tiktoken.get_encoding('cl100k_base')
    engine = ObservationEngine()
    results = []
    with partial.open('x') as stream:
        for domain, group in first.items():
            rows = [r for r in data if r['group'] == group]
            request = ObservationRequest(**rows[0]['request'])
            expected = {r['id'] for r in rows if r['label'] == 1}
            unknown = {r['id'] for r in rows if r['label'] is None}
            for budget in protocol['budgets_cl100k']:
                blocks, full, tokens = make_dossier(rows, budget, tokenizer)
                repeats = []
                for _ in range(protocol['repeats']):
                    measured = engine.rank_observations(request, blocks)
                    repeats.append(measured)
                kept = set(repeats[0]['kept_ids'])
                assert all(set(r['kept_ids']) == kept for r in repeats)
                assert expected <= kept and unknown <= kept
                candidate = '\n\n'.join(b['text'] for b in blocks if b['id'] in kept)
                assert all(next(b['text'] for b in blocks if b['id'] == key) in candidate for key in expected | unknown)
                row = dict(domain=domain, group=group, requested_budget_cl100k=budget, actual_dossier_tokens=tokens,
                           candidate_tokens=len(tokenizer.encode(candidate)), input_bytes=len(full.encode()),
                           candidate_bytes=len(candidate.encode()), removed_byte_fraction=1 - len(candidate.encode())/len(full.encode()),
                           known_observation_coverage=len(expected & kept)/len(expected), unknown_retention=len(unknown & kept)/len(unknown),
                           full_sha256=hashlib.sha256(full.encode()).hexdigest(), candidate_sha256=hashlib.sha256(candidate.encode()).hexdigest(),
                           p50_rank_ms=statistics.median(r['latency_ms'] for r in repeats), block_count=len(blocks),
                           kept_ids=repeats[0]['kept_ids'], decisions=repeats[0]['items'])
                results.append(row)
                stream.write(json.dumps(row) + '\n')
                stream.flush()
                print(domain, budget, round(row['p50_rank_ms'], 2), row['known_observation_coverage'], flush=True)
    by_budget = {}
    for budget in protocol['budgets_cl100k']:
        rows = [r for r in results if r['requested_budget_cl100k'] == budget]
        by_budget[budget] = dict(n=len(rows), observation_coverage_min=min(r['known_observation_coverage'] for r in rows),
                                unknown_retention_min=min(r['unknown_retention'] for r in rows),
                                removed_bytes_min=min(r['removed_byte_fraction'] for r in rows),
                                p50_rank_ms=statistics.median(r['p50_rank_ms'] for r in rows),
                                candidate_tokens_max=max(r['candidate_tokens'] for r in rows))
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    result = dict(protocol_sha256=sha(OUT/'protocol.json'), rows=results, by_budget=by_budget,
                  platform=platform.platform(), process_highwater_rss_bytes=rss if platform.system() == 'Darwin' else rss*1024,
                  limitation='one process, first call can be cold; RSS includes interpreter/tokenizer; no matched neural timing or LCC executor outcome')
    result_path.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(by_budget, indent=2))


if __name__ == '__main__':
    main()
