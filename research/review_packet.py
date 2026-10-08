"""Blind human label review packet (goal-family-corpus-v1 PLAN section 4); no model outputs, no inference."""
import argparse
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
import random

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'research/goal-engine-2026-10-04'
PROBE = BASE / 'goal-interpreter-probe-v1'
OUT = BASE / 'human-review-v1'
SEED = 20261008
QUOTA = 15
LANGUAGES = ('en', 'pt')
GROUPS = ('supported', 'unknown', 'contrast', 'ambiguity')
PROVENANCES = ('authored', 'genuine_lcc')
COLUMNS = ['item_id', 'family_id', 'language', 'question', 'proposed_label', 'registry_definition',
           'verdict', 'corrected_label', 'note']
VERDICTS = ('agree', 'disagree', 'ambiguous')
KIND_LABELS = {'diagnosis_goal': 'UNKNOWN:diagnosis', 'derived_or_multifield_goal': 'UNKNOWN:derived',
               'broader_usefulness_goal': 'UNKNOWN:broader', 'out_of_registry': 'UNKNOWN:other'}
PASS_OVERALL, PASS_STRATUM = .95, .90


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def text_sha(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def label_id(label):
    return label.strip().split(' (', 1)[0]


def candidates(probe):
    """Every exposed development question with its authored label; current data is authored only."""
    registry = json.loads((probe / 'registry.json').read_text())
    labels = {f['id']: (f"{f['id']} ({f['unit']})", f"unit: {f['unit']}. {f['definition']}") for f in registry['fields']}
    labels.update({u['id']: (u['id'], u['definition']) for u in registry['unsupported']})
    items = []
    for split in ('train', 'validation'):
        annotations = json.loads((probe / f'{split}-annotations.json').read_text())
        for q in json.loads((probe / f'{split}-inputs.json').read_text()):
            a = annotations[q['id']]
            label = a['target'] if a['kind'] == 'direct' else KIND_LABELS[a['kind']]
            # ponytail: contrast/ambiguity groups and genuine_lcc provenance do not exist in current data yet.
            group = 'supported' if a['kind'] == 'direct' else 'unknown'
            items.append(dict(query_id=q['id'], split=split, language=q['language'], question=q['question'],
                              label=label, proposed_label=labels[label][0], definition=labels[label][1],
                              family_id=text_sha('|'.join(a['wording_families']))[:12],
                              wording_families=a['wording_families'], source_ids=a['source_ids'],
                              stratum=f"{q['language']}|{group}|authored"))
    return items, set(labels)


def pick(pool, quota, rng):
    """Round-robin over labels (field/kind), distinct families first, seeded order."""
    by_label = {}
    for item in sorted(pool, key=lambda x: x['query_id']):
        by_label.setdefault(item['label'], []).append(item)
    queues = []
    for label in sorted(by_label):
        shuffled, seen = rng.sample(by_label[label], len(by_label[label])), set()
        first = [x for x in shuffled if not (x['family_id'] in seen or seen.add(x['family_id']))]
        queues.append(first + [x for x in shuffled if x not in first])
    chosen = []
    while len(chosen) < quota and any(queues):
        for q in queues:
            if q and len(chosen) < quota:
                chosen.append(q.pop(0))
    return chosen


def build(out=OUT, seed=SEED, probe=PROBE, force=False):
    out = Path(out)
    if not force and (out / 'packet.csv').exists():
        with open(out / 'packet.csv', newline='', encoding='utf-8-sig') as f:
            if any((r.get(c) or '').strip() for r in csv.DictReader(f) for c in ('verdict', 'corrected_label', 'note')):
                raise FileExistsError(f'{out / "packet.csv"} already holds reviewer work; pass --force to overwrite it')
    items, _ = candidates(probe)
    strata, chosen = {}, []
    for lang in LANGUAGES:
        for group in GROUPS:
            for prov in PROVENANCES:
                name = f'{lang}|{group}|{prov}'
                pool = [x for x in items if x['stratum'] == name]
                taken = pick(pool, QUOTA, random.Random(f'{seed}:{name}'))
                chosen += taken
                strata[name] = dict(available=len(pool), sampled=len(taken), shortfall=QUOTA - len(taken),
                                    by_label=dict(sorted(Counter(x['label'] for x in taken).items())))
    random.Random(f'{seed}:order').shuffle(chosen)
    out.mkdir(parents=True, exist_ok=True)
    key = {}
    with open(out / 'packet.csv', 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        for n, x in enumerate(chosen, 1):
            item_id = f'HR-{n:03d}'
            writer.writerow(dict(item_id=item_id, family_id=x['family_id'], language=x['language'],
                                 question=x['question'], proposed_label=x['proposed_label'],
                                 registry_definition=x['definition'], verdict='', corrected_label='', note=''))
            key[item_id] = dict(stratum=x['stratum'], split=x['split'], query_id=x['query_id'],
                                source_ids=x['source_ids'], wording_families=x['wording_families'],
                                label=x['label'], question_sha256=text_sha(x['question']),
                                proposed_label=x['proposed_label'])
    (out / 'key.json').write_text(json.dumps(dict(seed=seed, items=key), indent=1, sort_keys=True) + '\n')
    sources = {str(p.relative_to(ROOT)): sha(p) for p in sorted(probe.glob('*-inputs.json'))
               + sorted(probe.glob('*-annotations.json')) + [probe / 'registry.json', Path(__file__)]
               if p.is_relative_to(ROOT)}
    present = {g for name, s in strata.items() if s['available'] for g in [name.split('|')[1]]}
    receipt = dict(schema='human-review-packet/0.1', plan='research/goal-engine-2026-10-04/goal-family-corpus-v1/PLAN.md#4',
                   seed=seed, quota_per_stratum=QUOTA, target_items=QUOTA * len(strata), items=len(chosen),
                   shortfall=sum(s['shortfall'] for s in strata.values()), strata=strata,
                   missing_groups=[g for g in GROUPS if g not in present],
                   missing_provenances=[p for p in PROVENANCES if not any(
                       s['available'] for name, s in strata.items() if name.endswith('|' + p))],
                   families=len({x['family_id'] for x in chosen}), sibling_frame_text='not present in current data',
                   sources=sources, packet_sha256=sha(out / 'packet.csv'), key_sha256=sha(out / 'key.json'),
                   reviewer='project owner (Lucas); not the corpus author (agents authored it)',
                   model_outputs_in_packet=False, split_in_packet=False, model_forwards=0, API_calls=0)
    (out / 'build-receipt.json').write_text(json.dumps(receipt, indent=1, sort_keys=True) + '\n')
    return receipt


def score(packet, key_path, probe=PROBE):
    key = json.loads(Path(key_path).read_text())['items']
    _, valid = candidates(probe)
    with open(packet, newline='', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        if reader.fieldnames != COLUMNS:
            raise ValueError(f'Columns must be exactly {COLUMNS}')
        rows = list(reader)
    ids = [r['item_id'] for r in rows]
    if len(ids) != len(set(ids)) or set(ids) != set(key):
        raise ValueError('Packet must hold every key item exactly once')
    blank = [r['item_id'] for r in rows if not r['verdict'].strip()]
    if blank:
        raise ValueError(f'Packet not finished: {len(blank)}/{len(rows)} rows have no verdict '
                         f'(first: {blank[0]}). Fill verdict in {packet} per INSTRUCTIONS_PT.md.')
    strata = {}
    for r in rows:
        k, verdict = key[r['item_id']], r['verdict'].strip().lower()
        if text_sha(r['question']) != k['question_sha256'] or r['proposed_label'] != k['proposed_label']:
            raise ValueError(f"{r['item_id']}: question or proposed label was edited")
        if verdict not in VERDICTS:
            raise ValueError(f"{r['item_id']}: verdict must be one of {VERDICTS}, got {r['verdict']!r}")
        corrected = r['corrected_label'].strip()
        if verdict == 'disagree' and label_id(corrected) not in valid:
            raise ValueError(f"{r['item_id']}: disagree needs a registered corrected_label, got {corrected!r}")
        if corrected and label_id(corrected) not in valid:
            raise ValueError(f"{r['item_id']}: unknown corrected_label {corrected!r}")
        s = strata.setdefault(k['stratum'], Counter())
        s[verdict] += 1
        s['n'] += 1
    result = {name: dict(n=c['n'], **{v: c[v] for v in VERDICTS}, agreement=c['agree'] / c['n'])
              for name, c in sorted(strata.items())}
    n, agree = sum(c['n'] for c in strata.values()), sum(c['agree'] for c in strata.values())
    agreement = agree / n
    gate = agreement >= PASS_OVERALL and all(s['agreement'] >= PASS_STRATUM for s in result.values())
    complete = len(strata) == len(LANGUAGES) * len(GROUPS) * len(PROVENANCES)
    return dict(schema='human-review-score/0.1', n=n, agree=agree, agreement=agreement,
                pass_rule=dict(overall=PASS_OVERALL, every_stratum=PASS_STRATUM), strata=result,
                gate_pass=gate, plan_complete=complete, adoption_ready=gate and complete,
                packet_sha256=sha(packet), key_sha256=sha(key_path),
                note='ambiguous counts as non-agreement; plan_complete is false while PLAN strata are missing')


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest='command', required=True)
    b = sub.add_parser('build')
    b.add_argument('--out', default=OUT)
    b.add_argument('--seed', type=int, default=SEED)
    b.add_argument('--force', action='store_true', help='overwrite a packet that already holds reviewer work')
    s = sub.add_parser('score')
    s.add_argument('--packet', default=OUT / 'packet.csv')
    s.add_argument('--key', default=OUT / 'key.json')
    s.add_argument('--result', default=OUT / 'score.json')
    args = parser.parse_args()
    if args.command == 'build':
        print(json.dumps(build(Path(args.out), args.seed, force=args.force), indent=1, sort_keys=True))
    else:
        result = score(args.packet, args.key)
        Path(args.result).write_text(json.dumps(result, indent=1, sort_keys=True) + '\n')
        print(json.dumps({k: result[k] for k in ('n', 'agreement', 'gate_pass', 'plan_complete')}, indent=1))


if __name__ == '__main__':
    main()
