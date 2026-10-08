"""Independent, standard-library audit. Does not import the benchmark runner.

Run: python3 research/audit-2026-10-03/verify.py
Source data/checkpoints are read-only; evidence is written beside this script.
"""
from pathlib import Path
from collections import Counter, defaultdict
import ast
import hashlib
import json
import re
import statistics

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def calls(path, name):
    tree = ast.parse(path.read_text())
    return sorted((node.lineno, [ast.literal_eval(a) for a in node.args])
                  for node in ast.walk(tree)
                  if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                  and node.func.id == name)


def auc(facts, negatives):
    pairs = len(facts) * len(negatives)
    wins = sum(f > n for f in facts for n in negatives)
    ties = sum(f == n for f in facts for n in negatives)
    return dict(wins=wins, ties=ties, pairs=pairs,
                strict=wins / pairs if pairs else None,
                half_ties=(wins + ties / 2) / pairs if pairs else None)


raw_path = ROOT / 'bakeoff/results/results.json'
data = json.loads(raw_path.read_text())
rows = data['rows']
probes = calls(ROOT / 'bakeoff/probes.py', 'ProbeCase')
old_ids = {args[0] for _, args in probes[:8]}
new_ids = {args[0] for _, args in probes[8:]}
cells = defaultdict(list)
for row in rows:
    cells[row['model'], row['depth_tokens']].append(row)

recalculated = {}
summary_errors = []
checked = 0
for stored in data['summary']:
    model = stored['model']
    if 'error' in stored:
        continue
    entry = {}
    for depth in data['depths']:
        rr = cells[model, depth]
        scores = {k: [r['score'] for r in rr if r['kind'] == k and r['score'] is not None]
                  for k in ('fact', 'noise_decoy', 'noise_unrelated')}
        f, j, d = scores['fact'], scores['noise_decoy'], scores['noise_unrelated']
        lat = [r['latency_ms'] for r in rr if r['score'] is not None]
        values = dict(auc_detect=auc(f, d), auc_judge=auc(f, j), n=len(f),
                      n_by_kind={k: len(v) for k, v in scores.items()},
                      versions=dict(Counter(r.get('probe_version', 'MISSING') for r in rr)),
                      errors=sum(bool(r['error']) for r in rr),
                      truncated=sum(bool(r['truncated']) for r in rr))
        expected = dict(auc_detect=round(values['auc_detect']['half_ties'], 3) if f and d else None,
                        auc_judge=round(values['auc_judge']['half_ties'], 3) if f and j else None,
                        mean_fact=round(statistics.mean(f), 3) if f else None,
                        mean_unrelated=round(statistics.mean(d), 3) if d else None,
                        mean_decoy=round(statistics.mean(j), 3) if j else None,
                        p50_latency_ms=round(statistics.median(lat), 1) if lat else None,
                        errors=values['errors'], n=len(f))
        for key, value in expected.items():
            checked += 1
            if stored['by_depth'][str(depth)][key] != value:
                summary_errors.append([model, depth, key, value])
        values['summary_values'] = expected
        values['case_ids'] = sorted({r['case_id'] for r in rr})
        for subset, ids in [('old8', old_ids), ('new54', new_ids),
                            ('without_raft', old_ids | (new_ids - {'raft_leader_flap'}))]:
            ss = [r for r in rr if r['case_id'] in ids]
            ff = {r['case_id']: r['score'] for r in ss if r['kind'] == 'fact'}
            result = {}
            for family, kind in [('D', 'noise_unrelated'), ('J', 'noise_decoy')]:
                nn = {r['case_id']: r['score'] for r in ss if r['kind'] == kind}
                result[family] = auc(list(ff.values()), list(nn.values()))
                result[family]['paired_wins'] = sum(ff[c] > nn[c] for c in ff if c in nn)
                result[family]['paired_n'] = len(ff)
            values[subset] = result
        entry[str(depth)] = values
    effective = {}
    for family in ('detect', 'judge'):
        passing = [depth for depth in data['depths']
                   if (entry[str(depth)][f'auc_{family}']['strict'] or 0) >= .9]
        effective[family] = dict(passing_depths=passing, maximum=max(passing) if passing else None,
                                report_sentinel=max(passing) if passing else 0)
    recalculated[model] = dict(depths=entry, effective_context=effective)

md_errors = []
md_checked = 0
summary_by_model = {s['model']: s for s in data['summary']}
current_model = None
for line_no, line in enumerate((ROOT / 'bakeoff/results/RESULTS.md').read_text().splitlines(), 1):
    if line.startswith('### '):
        current_model = line[4:]
    if current_model and re.match(r'\| \d+ \|', line):
        parts = [v.strip() for v in line.strip('|').split('|')]
        expected = summary_by_model[current_model]['by_depth'][parts[0]]
        for key, value in zip(('auc_detect', 'auc_judge', 'mean_fact', 'mean_unrelated',
                               'mean_decoy', 'p50_latency_ms', 'errors'), parts[1:]):
            md_checked += 1
            if str(expected[key]) != value:
                md_errors.append([line_no, current_model, key, value, expected[key]])

holdout_names = {'vector_drift', 'bot_traffic', 'pdf_render', 'sms_delivery'}
domains = {args[0]: args for _, args in calls(ROOT / 'specialist/corpus.py', 'Domain')}
corpus = {}
hash_sets = {}
for split in ('train', 'val', 'ood'):
    path = ROOT / f'data/exp02d/{split}.jsonl'
    items = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    leak = {}
    for name in sorted(holdout_names):
        fields = set(domains[name][2])
        hits = []
        for line_no, item in enumerate(items, 1):
            matched = [line for line in item['text'].splitlines()
                       if fields <= set(re.findall(r'\b([A-Za-z_][A-Za-z_0-9]*)=', line))]
            if matched:
                hits.append(dict(line=line_no, id=item['id'], kind=item['kind'],
                                 decisive_line=matched[0]))
        leak[name] = dict(count=len(hits), examples=hits[:3])
    digest = hashlib.sha256(''.join(sorted(i['content_hash'] for i in items)).encode()).hexdigest()[:16]
    hash_sets[split] = {i['content_hash'] for i in items}
    corpus[split] = dict(n=len(items), domains=dict(Counter(i['domain'] for i in items)),
                         kinds=dict(Counter(i['kind'] for i in items)), digest=digest,
                         bad_content_hash=sum(hashlib.sha256((i['objective'] + '\n' + i['text']).encode()).hexdigest()[:16]
                                              != i['content_hash'] for i in items),
                         holdout_domain_field_count=sum(i['domain'] in holdout_names for i in items),
                         holdout_text_signatures=leak,
                         first160_domains=dict(Counter(i['domain'] for i in items[:160])))

evidence = dict(source_sha256=sha(raw_path), source_rows=len(rows),
                duplicate_keys=sum(n - 1 for n in Counter((r['model'], r['depth_tokens'], r['case_id'], r['kind'])
                                                         for r in rows).values()),
                summary_checked=checked, summary_errors=summary_errors,
                markdown_detail_checked=md_checked, markdown_detail_errors=md_errors,
                probe_case_count=len(probes), corpus=corpus,
                split_hash_intersections={f'{a}/{b}': len(hash_sets[a] & hash_sets[b])
                                          for a, b in [('train', 'val'), ('train', 'ood'), ('val', 'ood')]},
                recalculated=recalculated,
                checkpoint_sha256={str(p.relative_to(ROOT)): sha(p) for p in sorted((ROOT / 'models').glob('*/weights.pt'))})
derived = {}
for directory in sorted((ROOT / 'data').iterdir()):
    if not directory.is_dir():
        continue
    manifest_path = directory / 'manifest.json'
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else None
    checks = {}
    for split in ('train', 'val', 'ood'):
        path = directory / f'{split}.jsonl'
        if not path.exists():
            continue
        items = [json.loads(line) for line in path.read_text().splitlines()]
        digest = hashlib.sha256(''.join(sorted(i['content_hash'] for i in items)).encode()).hexdigest()[:16]
        checks[split] = dict(n=len(items), claimed=manifest['splits'][split] if manifest else None,
                            actual_digest=digest,
                            bad_content_hash=sum(hashlib.sha256((i['objective'] + '\n' + i['text']).encode()).hexdigest()[:16]
                                                 != i['content_hash'] for i in items))
    derived[directory.name] = dict(manifest_exists=bool(manifest), splits=checks)
evidence['all_dataset_checks'] = derived
(OUT / 'evidence.json').write_text(json.dumps(evidence, indent=2) + '\n')
accepted = recalculated['specialist-exp04-unfreeze2-dyn-49k']
for depth, cell in accepted['depths'].items():
    if cell['n']:
        print('accepted', depth, 'n=', cell['n'], 'J=', cell['auc_judge'], 'D=', cell['auc_detect'])
print('effective_context', accepted['effective_context'])
print('summary', checked, 'checks, errors=', len(summary_errors))
print('RESULTS.md', md_checked, 'checks, errors=', len(md_errors))
for split in ('train', 'val'):
    print('holdout signatures', split,
          {d: v['count'] for d, v in corpus[split]['holdout_text_signatures'].items()})
print('evidence:', OUT / 'evidence.json')
