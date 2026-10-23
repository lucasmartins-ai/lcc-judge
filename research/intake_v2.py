"""Intake judge v2 pipeline (protocol: research/goal-engine-2026-10-04/intake-judge-v2/PROTOCOL.md).

    python -m research.intake_v2 split      # held-out = sessions from 2026-10-24; dev 20% (+ owner-dev sessions)
    python -m research.intake_v2 teacher    # Opus labels with the previous turn (cached, shared 3,500-call cap)
    python -m research.intake_v2 check      # teacher vs owner-dev (stop rule 0.75)
    python -m research.intake_v2 shrink     # prune + PCA the static embeddings to train/dev tokens, 64 dims
    python -m research.intake_v2 train      # 9-config grid, budgets, selection, FREEZE.json
    python -m research.intake_v2 count      # held-out trigger count (sessions only)
    python -m research.intake_v2 gold-page  # after the trigger and the pushed freeze; two passes
    python -m research.intake_v2 eval pass1.csv pass2.csv

Private text stays in ~/.lcc/intake-v2/. The repo gets counts, ids and hashes only.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import random
import subprocess
import sys
import tempfile
import time
from collections import Counter, defaultdict
from pathlib import Path

from research import intake_v1 as v1
from research.intake_judge import Judge as JudgeV1
from research.intake_judge_v2 import WIDTH, Embedder, Judge, export, family_ranges, family_rows, vector
from research.intake_keywords import classify as keyword_classify
from research.llm_judge_arm import LIMIT_RE

BASE = Path.home() / '.lcc' / 'intake-v2'
EMB_SRC = Path.home() / '.lcc' / 'models' / 'potion-multilingual-128M'
OUT = v1.REPO / 'goal-engine-2026-10-04' / 'intake-judge-v2'
CUTOFF = '2026-10-24T00:00:00Z'
SEED = 20261024
CALL_CAP = 3500
GRID = [('A', 3.0), ('A', 10.0), ('A', 30.0), ('B', 3.0), ('B', 10.0), ('B', 30.0),
        ('E', 1.0), ('E', 10.0), ('H', 10.0)]
BUDGET = {'A': (5, 20, 2_000_000, 100), 'B': (5, 20, 2_000_000, 100),
          'E': (5, 20, 30_000_000, 150), 'H': (5, 20, 30_000_000, 150)}  # median ms, p90 ms, bytes, RSS MB
V1_OWNER_DEV_ACC = 0.509
TRIGGER_SESSIONS = 100


def records():
    out = {}
    for p in sorted((BASE / 'imported').glob('*.jsonl')):
        for r in v1._read_jsonl(p):
            out[r['id']] = r
    return out


def _session_first(recs):
    first = {}
    for r in recs.values():
        ts = r.get('timestamp_utc')
        if ts:
            first[r['session_hash']] = min(first.get(r['session_hash'], ts), ts)
    return first


# --- owner-dev: v1 owner gold (both passes agree) mapped onto v2 records ---------------------------------
def owner_dev_map(recs):
    g1 = v1._read_gold(v1.BASE / 'gold' / 'pass1.csv')
    g2 = v1._read_gold(v1.BASE / 'gold' / 'pass2.csv')
    agreed = {i: v for i, v in g1.items() if g2.get(i) == v and v not in ('', 'unsure')}
    old = v1.records()
    by_key = defaultdict(list)
    for r in recs.values():
        by_key[(r['source'], r.get('timestamp_utc'), r['goal'])].append(r['id'])
    mapped, missing = {}, 0
    for oid, label in agreed.items():
        o = old[oid]
        cands = by_key.get((o['source'], o.get('timestamp_utc'), o['goal']), [])
        if len(cands) == 1:
            mapped[cands[0]] = label
        else:
            missing += 1
    return mapped, missing


def split():
    path = BASE / 'split.json'
    if path.exists():
        raise SystemExit(f'{path} exists: the split is built once')
    recs = records()
    first = _session_first(recs)
    owner, missing = owner_dev_map(recs)
    forced = {recs[i]['session_hash'] for i in owner}
    trainval = sorted({r['session_hash'] for r in recs.values() if first.get(r['session_hash'], '') < CUTOFF})
    rng = random.Random(SEED)
    rng.shuffle(trainval)
    dev = set(trainval[:len(trainval) // 5]) | forced
    assign = {i: ('heldout' if first.get(r['session_hash'], '') >= CUTOFF
                  else 'dev' if r['session_hash'] in dev else 'train') for i, r in recs.items()}
    v1._write_private(path, assign)
    v1._write_private(BASE / 'owner-dev.json', owner)
    counts = Counter(assign.values())
    summary = {'items': dict(counts),
               'sessions': {k: len({recs[i]['session_hash'] for i, v in assign.items() if v == k}) for k in counts},
               'with_prev': {k: sum(bool(recs[i].get('prev_agent')) for i, v in assign.items() if v == k) for k in counts},
               'owner_dev': {'agreed_v1_items': len(owner) + missing, 'mapped': len(owner), 'unmatched': missing},
               'forced_dev_sessions': len(forced)}
    OUT.mkdir(exist_ok=True)
    (OUT / 'split-counts.json').write_text(json.dumps(summary, indent=1, sort_keys=True) + '\n')
    print(json.dumps(summary, indent=1, sort_keys=True))


# --- teacher -----------------------------------------------------------------------------------------------
def teacher_system():
    cats, tax = v1.categories()
    return (v1.teacher_system(cats, tax) + '\n\nEach request comes with the tail of the agent\'s previous turn '
            '("previous_agent_turn", null when unknown). Use it as context to understand what the request '
            'refers to; the category is about the user\'s request, not the agent\'s turn.')


def teacher_argv():
    cats, _ = v1.categories()
    schema = {'type': 'object', 'required': ['answers'], 'properties': {'answers': {
        'type': 'object', 'additionalProperties': {'type': 'string', 'enum': cats}}}}
    argv = ['claude', '-p', '--model', 'opus', '--tools', '', '--output-format', 'json',
            '--json-schema', json.dumps(schema), '--no-session-persistence', '--disable-slash-commands',
            '--strict-mcp-config', '--permission-prompts', 'none', '--setting-sources', '',
            '--exclude-dynamic-system-prompt-sections', '--system-prompt', teacher_system()]
    assert not any('dangerously' in a for a in argv), 'never skip permissions'
    return argv


def _call(argv, batch):
    body = 'REQUESTS:\n' + json.dumps({f'r{n}': {'previous_agent_turn': r.get('prev_agent'), 'request': r['goal']}
                                       for n, r in enumerate(batch)}, ensure_ascii=False)
    with tempfile.TemporaryDirectory() as cwd:
        p = subprocess.run(argv, input=body, capture_output=True, text=True, cwd=cwd, timeout=330,
                           env={k: v for k, v in os.environ.items() if not k.startswith(('PYTHON', 'ANTHROPIC_'))})
    ans = None if p.returncode else v1._answers(p.stdout)
    if ans is None:
        msg = p.stdout[-2000:] + p.stderr[-2000:]
        if LIMIT_RE.search(msg):
            raise v1.LimitHit(LIMIT_RE.search(msg).group(0))
        raise RuntimeError(f'no answers (exit {p.returncode}): {p.stderr[-300:]}')
    return {r['id']: ans.get(f'r{n}') for n, r in enumerate(batch)}


def _calls(delta=0):
    path = BASE / 'teacher' / 'calls.json'
    n = json.loads(path.read_text())['calls'] if path.exists() else 0
    if delta:
        path.write_text(json.dumps({'calls': n + delta}))
    return n + delta


def teacher():
    cats, _ = v1.categories()
    argv = teacher_argv()
    (BASE / 'teacher').mkdir(exist_ok=True)
    (BASE / 'teacher' / 'system-prompt.txt').write_text(teacher_system(), encoding='utf-8')
    cache = BASE / 'teacher' / 'labels.jsonl'
    done = {r['id'] for r in v1._read_jsonl(cache)} if cache.exists() else set()
    assign, recs = json.loads((BASE / 'split.json').read_text()), records()
    # records appended after the split (count re-imports) are never teacher-labelled here
    todo = [recs[i] for i in sorted(recs) if assign.get(i, 'heldout') != 'heldout' and i not in done]
    batches = [todo[k:k + v1.BATCH] for k in range(0, len(todo), v1.BATCH)]
    print(f'{len(done)} cached, {len(todo)} to label in {len(batches)} calls; calls so far {_calls()}', flush=True)
    import threading
    state = {'stop': False, 'calls': _calls()}
    lock = threading.Lock()

    def work(batch):
        with lock:
            if state['stop'] or state['calls'] >= CALL_CAP:
                return None
            state['calls'] += 1
        try:
            return _call(argv, batch)
        except v1.LimitHit as e:
            state['stop'] = True
            print(f'usage limit: {e}; resume later from cache', flush=True)
        except (RuntimeError, subprocess.TimeoutExpired) as e:
            print(f'batch failed: {str(e)[:200]}', flush=True)
        return None

    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(v1.WORKERS) as pool, open(cache, 'a', encoding='utf-8') as fh:
        for n, got in enumerate(pool.map(work, batches)):
            for i, lab in (got or {}).items():
                if lab in cats:
                    fh.write(json.dumps({'id': i, 'label': lab}) + '\n')
            fh.flush()
            with lock:
                (BASE / 'teacher' / 'calls.json').write_text(json.dumps({'calls': state['calls']}))
            if n % 10 == 0:
                print(f'{n + 1}/{len(batches)} batches, calls {state["calls"]}', flush=True)
    os.chmod(cache, 0o600)


def teacher_labels():
    return {r['id']: r['label'] for r in v1._read_jsonl(BASE / 'teacher' / 'labels.jsonl')}


def check():
    owner, lab = json.loads((BASE / 'owner-dev.json').read_text()), teacher_labels()
    both = [i for i in owner if i in lab]
    agree = sum(owner[i] == lab[i] for i in both)
    res = {'owner_dev': len(owner), 'teacher_labelled': len(both), 'agree': agree,
           'accuracy': round(agree / len(both), 4) if both else None, 'stop_rule': 0.75,
           'teacher_calls': _calls(), 'teacher_labels': len(lab)}
    res['passes'] = bool(both) and agree / len(both) >= 0.75
    (OUT / 'teacher-check.json').write_text(json.dumps(res, indent=1) + '\n')
    print(json.dumps(res))
    return res


# --- shrink the static embeddings ---------------------------------------------------------------------------
def shrink():
    import numpy as np
    from safetensors.numpy import load_file
    from tokenizers import Tokenizer
    out = BASE / 'emb-64.npz'
    if out.exists():
        raise SystemExit(f'{out} exists')
    tok = Tokenizer.from_file(str(EMB_SRC / 'tokenizer.json'))
    assign, recs = json.loads((BASE / 'split.json').read_text()), records()
    kept = set()
    for i, s in assign.items():
        if s != 'heldout':  # vocabulary from train/dev only
            for t in (recs[i]['goal'], recs[i].get('prev_agent') or ''):
                kept.update(tok.encode(t, add_special_tokens=False).ids)
    ids = np.array(sorted(kept), dtype=np.int64)
    full = load_file(str(EMB_SRC / 'model.safetensors'))['embeddings']
    X = full[ids].astype(np.float64)
    mu = X.mean(0)
    _, _, vt = np.linalg.svd(X - mu, full_matrices=False)
    rows = ((X - mu) @ vt[:64].T).astype(np.float16)
    np.savez(out, ids=ids, rows=rows)
    os.chmod(out, 0o600)
    res = {'kept_tokens': int(len(ids)), 'vocab': int(full.shape[0]), 'dims': 64,
           'bytes': out.stat().st_size, 'explained_variance_64': round(float(
               (np.linalg.svd(X - mu, compute_uv=False)[:64] ** 2).sum()
               / (np.linalg.svd(X - mu, compute_uv=False) ** 2).sum()), 4),
           'source_sha256': {f: v1._sha(EMB_SRC / f) for f in ('config.json', 'tokenizer.json', 'model.safetensors')}}
    (OUT / 'shrink.json').write_text(json.dumps(res, indent=1) + '\n')
    print(json.dumps(res))


def embedder():
    return Embedder(EMB_SRC / 'tokenizer.json', BASE / 'emb-64.npz')


# --- train / select -----------------------------------------------------------------------------------------
def fit_vectors(vecs, y, cats, C, iters=400, lr=0.05):
    """v1.fit on precomputed {index: value} vectors over WIDTH columns."""
    import numpy as np
    idx = np.array([k for v in vecs for k in v], dtype=np.int64)
    val = np.array([x for v in vecs for x in v.values()], dtype=np.float64)
    ptr = np.cumsum([0] + [len(v) for v in vecs])
    n, k = len(vecs), len(cats)
    rows = np.repeat(np.arange(n), np.diff(ptr))
    yi = np.array([cats.index(c) for c in y])
    sw = n / (k * np.maximum(np.bincount(yi, minlength=k), 1))[yi]
    Y = np.eye(k)[yi]
    W, b = np.zeros((WIDTH, k)), np.zeros(k)
    mW, vW, mb, vb = np.zeros_like(W), np.zeros_like(W), np.zeros(k), np.zeros(k)
    for t in range(1, iters + 1):
        Z = np.add.reduceat(W[idx] * val[:, None], ptr[:-1], axis=0) + b
        Z -= Z.max(1, keepdims=True)
        Pr = np.exp(Z)
        Pr /= Pr.sum(1, keepdims=True)
        G = (Pr - Y) * sw[:, None] / n
        gW = np.zeros_like(W)
        np.add.at(gW, idx, val[:, None] * G[rows])
        gW += W / (C * n)
        gb = G.sum(0)
        for p, g, m, v in ((W, gW, mW, vW), (b, gb, mb, vb)):
            m *= 0.9
            m += 0.1 * g
            v *= 0.999
            v += 0.001 * g * g
            p -= lr * (m / (1 - 0.9 ** t)) / (np.sqrt(v / (1 - 0.999 ** t)) + 1e-8)
    return W, b


def _bench(model_path, items, family):
    texts = BASE / 'bench-input.json'
    v1._write_private(texts, items)
    args = [sys.executable, '-m', 'research.intake_judge_v2', str(model_path), str(texts)]
    if family in ('E', 'H'):
        args += [str(EMB_SRC / 'tokenizer.json'), str(BASE / 'emb-64.npz')]
    p = subprocess.run(args, capture_output=True, text=True, check=True, cwd=v1.REPO.parent)
    c = json.loads(p.stdout)
    lat = sorted(c['latency_ms'])
    return {'median_ms': round(lat[len(lat) // 2], 3), 'p90_ms': round(lat[int(0.9 * len(lat))], 3),
            'load_ms': round(c['load_ms'], 1), 'peak_rss_mb': round(c['peak_rss_mb'], 1)}


def _files_bytes(path, family):
    n = path.stat().st_size
    if family in ('E', 'H'):
        n += (EMB_SRC / 'tokenizer.json').stat().st_size + (BASE / 'emb-64.npz').stat().st_size
    return n


def _threshold(pairs):
    """Lowest probability cut with >= 0.80 accuracy on dev; pairs = [(prob, correct)]."""
    for t in [x / 100 for x in range(20, 100, 5)]:
        s = [c for p, c in pairs if p >= t]
        if s and sum(s) / len(s) >= 0.80:
            return t, len(s) / len(pairs), round(sum(s) / len(s), 4)
    return None, 0.0, None


def _measure(family, C, path, emb, recs, lab, owner, dv):
    """Dev row for one exported config: scores, owner-dev, cost, size, budget, eligibility, threshold."""
    j = Judge.load(path, emb if family in ('E', 'H') else None)
    pred = {i: j.predict(recs[i]['goal'], recs[i].get('prev_agent')) for i in set(dv) | set(owner)}
    gold = [lab[i] for i in dv]
    cost = _bench(path, [[recs[i]['goal'], recs[i].get('prev_agent')] for i in dv], family)
    med, p90, max_bytes, max_rss = BUDGET[family]
    size = _files_bytes(path, family)
    row = {'family': family, 'C': C,
           'dev_macro_f1': round(v1.macro_f1(gold, [pred[i][0] for i in dv]), 4),
           'dev_accuracy': round(sum(pred[i][0] == lab[i] for i in dv) / len(dv), 4),
           'owner_dev_accuracy': round(sum(pred[i][0] == owner[i] for i in owner) / len(owner), 4),
           'files_bytes': size, **cost}
    row['within_budget'] = (cost['median_ms'] <= med and cost['p90_ms'] <= p90 and size <= max_bytes
                           and cost["peak_rss_mb"] <= max_rss)
    row['eligible'] = row['within_budget'] and row['owner_dev_accuracy'] >= V1_OWNER_DEV_ACC
    row['threshold'], row['threshold_coverage'], row['threshold_accuracy'] = _threshold(
        [(pred[i][1], pred[i][0] == lab[i]) for i in dv])
    return row


def train(refit=True):
    if (OUT / 'FREEZE.json').exists():
        raise SystemExit('FREEZE.json exists: v2 is frozen')
    cats, _ = v1.categories()
    assign, recs, lab = json.loads((BASE / 'split.json').read_text()), records(), teacher_labels()
    owner = json.loads((BASE / 'owner-dev.json').read_text())
    tr = [i for i in sorted(lab) if assign[i] == 'train']
    dv = [i for i in sorted(lab) if assign[i] == 'dev']
    emb = embedder()
    (BASE / 'models').mkdir(exist_ok=True)
    table = []
    for family, C in GRID:
        t0 = time.time()
        path = BASE / 'models' / f'intake-v2-{family}-C{C}.json'
        if not refit:
            row = _measure(family, C, path, emb, recs, lab, owner, dv)
            table.append(row)
            print(json.dumps(row), flush=True)
            continue
        vec = lambda i, f=family: vector(recs[i]['goal'], recs[i].get('prev_agent'), f, emb)  # noqa: E731
        W, b = fit_vectors([vec(i) for i in tr], [lab[i] for i in tr], cats, C)
        path = BASE / 'models' / f'intake-v2-{family}-C{C}.json'
        export(path, cats, family, W, b, {'C': C, 'train_items': len(tr), 'seed': SEED})
        row = _measure(family, C, path, emb, recs, lab, owner, dv)
        row['fit_s'] = round(time.time() - t0, 1)
        table.append(row)
        print(json.dumps(row), flush=True)

    def best(rows):
        rows = [r for r in rows if r['eligible']]
        return max(rows, key=lambda r: (r['dev_macro_f1'], -r['files_bytes'])) if rows else None

    pick = best(table)
    fallback = best([r for r in table if r['family'] in ('A', 'B')])
    j1 = JudgeV1.load(v1.BASE / 'model.json')
    v1_dev = sum(j1.predict(recs[i]['goal'])[0] == lab[i] for i in dv) / len(dv)
    freeze = {'frozen_at_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'grid': table,
              'pick': pick, 'fallback': fallback, 'train_items': len(tr), 'dev_items': len(dv),
              'owner_dev_items': len(owner), 'v1_dev_accuracy_vs_teacher_v2': round(v1_dev, 4),
              'majority_class': Counter(lab[i] for i in tr).most_common(1)[0][0],
              'dev_label_counts': dict(Counter(lab[i] for i in dv).most_common())}
    files = {'research/intake_judge_v2.py': v1.REPO / 'intake_judge_v2.py', 'research/intake_v2.py': v1.REPO / 'intake_v2.py',
             'research/intake_judge.py': v1.REPO / 'intake_judge.py', 'research/intake_v1.py': v1.REPO / 'intake_v1.py',
             'research/intake_keywords.py': v1.REPO / 'intake_keywords.py',
             'teacher system prompt (~/.lcc/intake-v2/teacher)': BASE / 'teacher' / 'system-prompt.txt',
             'emb-64.npz (~/.lcc/intake-v2)': BASE / 'emb-64.npz',
             'tokenizer.json (potion-multilingual-128M)': EMB_SRC / 'tokenizer.json',
             'v1 model.json (~/.lcc/intake-v1)': v1.BASE / 'model.json'}
    for role, row in (('pick', pick), ('fallback', fallback)):
        if row:
            src = BASE / 'models' / f"intake-v2-{row['family']}-C{row['C']}.json"
            dst = BASE / f'{role}.json'
            dst.write_bytes(src.read_bytes())
            os.chmod(dst, 0o600)
            files[f'{role}.json (~/.lcc/intake-v2)'] = dst
    freeze['sha256'] = {k: v1._sha(p) for k, p in files.items()}
    (OUT / 'FREEZE.json').write_text(json.dumps(freeze, indent=1) + '\n')
    print(json.dumps({'pick': pick, 'fallback': fallback}, indent=1))


# --- held-out --------------------------------------------------------------------------------------------------
def count():
    """Re-import (append-only, same base) and count qualifying held-out sessions. Counts only."""
    subprocess.run([sys.executable, '-m', 'research.import_agent_requests', 'run', '--base', str(BASE), '--with-prev'],
                   check=True, capture_output=True, cwd=v1.REPO.parent,
                   env={**os.environ, 'PYTHONPATH': f"/Users/Master/lcc/src:{v1.REPO.parent}"})
    recs = records()
    first = _session_first(recs)
    held = {s for s, ts in first.items() if ts >= CUTOFF}
    qual = {r['session_hash'] for r in recs.values() if r['session_hash'] in held and r.get('prev_agent')}
    res = {'heldout_sessions': len(held), 'qualifying_sessions': len(qual), 'trigger': TRIGGER_SESSIONS,
           'heldout_prompts': sum(r['session_hash'] in held for r in recs.values())}
    print(json.dumps(res))
    return res


def gold_sample():
    recs = records()
    first = _session_first(recs)
    norm = lambda r: (' '.join(r['goal'].lower().split()), r.get('prev_agent') or '')  # noqa: E731
    seen = {norm(r) for r in recs.values() if first.get(r['session_hash'], '') < CUTOFF}
    by_session, linked = defaultdict(list), 0
    for i in sorted(recs):
        r = recs[i]
        if first.get(r['session_hash'], '') < CUTOFF:
            continue
        if norm(r) in seen:
            linked += 1
            continue
        by_session[r['session_hash']].append(i)
    rng = random.Random(SEED)
    picks = []
    for s in sorted(by_session):
        ids = by_session[s][:]
        rng.shuffle(ids)
        picks.append(ids[:2])
    rng.shuffle(picks)
    return [i for pair in picks for i in pair], linked, len(by_session)


GOLD_PAGE = v1.GOLD_PAGE.replace(
    "<div class=\"goal\">${esc(it.goal)}</div>",
    "${it.prev?`<div class=\"def\">Último turno do agente (final):</div><div class=\"goal prev\">${esc(it.prev)}</div>"
    "<div class=\"def\">Seu pedido:</div>`:''}<div class=\"goal\">${esc(it.goal)}</div>").replace(
    "KEY='intake-v1-gold'", "KEY='intake-v2-gold-'+PASS").replace(
    "a.download='intake-v1-gold.csv'", "a.download='intake-v2-gold-'+PASS+'.csv'").replace(
    ".goal{", ".prev{opacity:.75;font-size:14px}.goal{").replace(
    "escolha a categoria olhando <b>só o texto</b>", "escolha a categoria do <b>seu pedido</b>, usando o turno do agente só como contexto")


def gold_page(pass_name):
    import html
    if not v1._committed(OUT / 'FREEZE.json'):
        raise SystemExit('FREEZE.json must be committed and pushed before held-out prompts are drawn')
    c = count()
    if c['qualifying_sessions'] < TRIGGER_SESSIONS:
        raise SystemExit(f"trigger not reached: {c['qualifying_sessions']} < {TRIGGER_SESSIONS} sessions")
    _, tax = v1.categories()
    pool, linked, sessions = gold_sample()
    recs = records()
    items = [{'id': i, 'goal': recs[i]['goal'], 'prev': recs[i].get('prev_agent') or ''} for i in pool[:150]]
    rng = random.Random(f'{SEED}-{pass_name}')
    rng.shuffle(items)  # each pass sees its own order
    cats = [{'id': x['id'], 'name': x['name_pt'], 'definition': x['definition_pt']} for x in tax['categories']]
    cats.append({'id': 'UNKNOWN', 'name': 'Não dá para saber',
                 'definition': 'Fragmento, colagem sem instrução ou texto quase todo redigido.'})
    glossary = ''.join(f"<li><b>{html.escape(x['name'])}</b>: {html.escape(x['definition'])}</li>" for x in cats)
    body = (GOLD_PAGE.replace('__GLOSSARY__', glossary).replace('__N__', str(len(items)))
            .replace('__ITEMS__', json.dumps(items, ensure_ascii=False).replace('</', '<\\/'))
            .replace('__CATS__', json.dumps(cats, ensure_ascii=False).replace('</', '<\\/'))
            .replace('<script>', f'<script>const PASS={json.dumps(pass_name)};', 1))
    out = BASE / 'gold' / f'gabarito-{pass_name}.html'
    out.parent.mkdir(exist_ok=True)
    out.write_text(body, encoding='utf-8')
    os.chmod(out, 0o600)
    summary = {'pass': pass_name, 'items': len(items), 'primary_pool': len(pool), 'sessions_in_pool': sessions,
               'seen_text_excluded': linked, 'with_prev': sum(bool(x['prev']) for x in items), **c}
    (OUT / f'gold-draw-{pass_name}.json').write_text(json.dumps(summary, indent=1) + '\n')
    print(json.dumps(summary))
    print(out)


def evaluate(pass_paths):
    out = OUT / 'test-results.json'
    if out.exists():
        raise SystemExit('the held-out gold is spent: test-results.json exists')
    passes = [v1._read_gold(p) for p in pass_paths]
    excluded = {i for g in passes for i, v in g.items() if v in ('', 'unsure')}
    clean = [{i: v for i, v in g.items() if v not in ('', 'unsure')} for g in passes]
    views = {f'pass{n + 1}': g for n, g in enumerate(clean)}
    views = {'primary_agree': {i: v for i, v in clean[0].items()
                               if i not in excluded and all(g.get(i) == v for g in clean[1:])}, **views}
    ids = sorted(set().union(*clean))
    recs, freeze = records(), json.loads((OUT / 'FREEZE.json').read_text())
    emb = embedder()
    arms = {}
    for role in ('pick', 'fallback'):
        row = freeze[role]
        if row and (role == 'pick' or row != freeze['pick']):
            j = Judge.load(BASE / f'{role}.json', emb if row['family'] in ('E', 'H') else None)
            arms[f'v2_{role}'] = {i: j.predict(recs[i]['goal'], recs[i].get('prev_agent'))[0] for i in ids}
    j1 = JudgeV1.load(v1.BASE / 'model.json')
    arms['v1'] = {i: j1.predict(recs[i]['goal'])[0] for i in ids}
    arms['keyword'] = {i: keyword_classify(recs[i]['goal']) for i in ids}
    arms['majority'] = dict.fromkeys(ids, freeze['majority_class'])
    cache = BASE / 'gold' / 'opus.json'
    opus = json.loads(cache.read_text()) if cache.exists() else {}
    argv = teacher_argv()
    todo = [i for i in ids if i not in opus]
    for k in range(0, len(todo), v1.BATCH):
        if _calls() >= CALL_CAP:
            raise SystemExit('call cap reached before the Opus arm finished')
        _calls(1)
        opus.update(_call(argv, [recs[i] for i in todo[k:k + v1.BATCH]]))
        v1._write_private(cache, opus)
    arms['opus'] = opus
    cost = _bench(BASE / 'pick.json', [[recs[i]['goal'], recs[i].get('prev_agent')] for i in ids],
                  freeze['pick']['family'])
    med, p90, max_bytes, max_rss = BUDGET[freeze['pick']['family']]
    cost_ok = (cost['median_ms'] <= med and cost['p90_ms'] <= p90 and cost['peak_rss_mb'] <= max_rss
               and freeze['pick']['files_bytes'] <= max_bytes)
    res = {'pass_sha256': [v1._sha(p) for p in pass_paths], 'excluded_unsure': len(excluded), 'cost': cost,
           'views': {}}
    for name, gold in views.items():
        res['views'][name] = _score(gold, arms, recs, cost_ok)
    out.write_text(json.dumps(res, indent=1) + '\n')
    print(json.dumps({'cost': cost, **{n: {k: v[k] for k in ('items', 'arms', 'diffs', 'acceptance')}
                                       for n, v in res['views'].items()}}, indent=1))


def reselect():
    """Amendment 1: convert the 9 exports to the range format (same weights), re-measure, re-select."""
    import base64
    old = OUT / 'FREEZE.json'
    if not old.exists():
        raise SystemExit('nothing to reselect')
    (OUT / 'FREEZE-prefix.json').write_text(old.read_text())
    old.unlink()
    for family, C in GRID:
        path = BASE / 'models' / f'intake-v2-{family}-C{C}.json'
        d = json.loads(path.read_text())
        if 'rows' in d:
            assert d['rows'] == family_rows(family), 'rows are not the family ranges'
            w0 = base64.b64decode(d['weights_f16'])
            d.pop('rows')
            d['ranges'] = family_ranges(family)
            path.write_text(json.dumps(d))
            assert base64.b64decode(json.loads(path.read_text())['weights_f16']) == w0
    train(refit=False)


def _bootstrap(groups, diff_fn, n=2000):
    rng = random.Random(SEED)
    keys = sorted(groups)
    vals = sorted(diff_fn([i for k in (rng.choice(keys) for _ in keys) for i in groups[k]]) for _ in range(n))
    return round(vals[int(0.025 * n)], 4), round(vals[int(0.975 * n) - 1], 4)


def _score(gold, arms, recs, cost_ok):
    ids = sorted(gold)
    groups = defaultdict(list)
    for i in ids:
        groups[recs[i]['session_hash']].append(i)

    def acc(arm, s):
        return sum(arms[arm].get(i) == gold[i] for i in s) / len(s)

    def mf1(arm, s):
        return v1.macro_f1([gold[i] for i in s], [arms[arm].get(i) for i in s])

    rng_boot = lambda fn: _bootstrap(groups, fn)  # noqa: E731
    res = {'items': len(ids), 'sessions': len(groups), 'gold_label_counts': dict(Counter(gold.values()).most_common()),
           'arms': {a: {'accuracy': round(acc(a, ids), 4), 'macro_f1': round(mf1(a, ids), 4)} for a in arms},
           'diffs': {}}
    others = [a for a in arms if a != 'v2_pick']
    for o in others:
        res['diffs'][f'v2_pick-{o}'] = {
            'accuracy': round(acc('v2_pick', ids) - acc(o, ids), 4),
            'accuracy_ci': rng_boot(lambda s, o=o: acc('v2_pick', s) - acc(o, s)),
            'macro_f1': round(mf1('v2_pick', ids) - mf1(o, ids), 4),
            'macro_f1_ci': rng_boot(lambda s, o=o: mf1('v2_pick', s) - mf1(o, s))}
    if 'v2_fallback' in arms:
        res['diffs']['v2_fallback-v1'] = {'accuracy': round(acc('v2_fallback', ids) - acc('v1', ids), 4),
                                          'accuracy_ci': rng_boot(lambda s: acc('v2_fallback', s) - acc('v1', s))}
    d = res['diffs']
    res['acceptance'] = {
        '1_replaces_v1': d['v2_pick-v1']['accuracy_ci'][0] > 0,
        '1b_fallback_replaces_v1': (d['v2_fallback-v1']['accuracy_ci'][0] > 0 if 'v2_fallback-v1' in d
                                    else d['v2_pick-v1']['accuracy_ci'][0] > 0),
        '2_beats_rules': all(d['v2_pick-keyword'][m][0] > 0 for m in ('accuracy_ci', 'macro_f1_ci')),
        '3_cost': cost_ok,
        '4_close_to_opus_label': d['v2_pick-opus']['accuracy_ci'][0] > -0.10}
    res['recall_by_category'] = {
        c: {'n': len(g), **{a: round(sum(arms[a].get(i) == c for i in g) / len(g), 3) for a in arms}}
        for c in sorted(set(gold.values())) for g in [[i for i in ids if gold[i] == c]]}
    res['by_prev'] = {k: {a: round(acc(a, s), 4) for a in arms} | {'n': len(s)}
                      for k, s in (('with_prev', [i for i in ids if recs[i].get('prev_agent')]),
                                   ('without_prev', [i for i in ids if not recs[i].get('prev_agent')])) if s}
    res['by_language'] = {lang: {a: round(acc(a, s), 4) for a in arms} | {'n': len(s)}
                          for lang in sorted({str(recs[i]['language']) for i in ids})
                          for s in [[i for i in ids if str(recs[i]['language']) == lang]]}
    return res


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('command', choices=('split', 'teacher', 'check', 'shrink', 'train', 'reselect', 'count', 'gold-page', 'eval'))
    ap.add_argument('--pass', dest='pass_name', default='pass1', help='gold-page: pass1 or pass2')
    ap.add_argument('csv', nargs='*')
    a = ap.parse_args(argv)
    if a.command == 'gold-page':
        gold_page(a.pass_name)
    elif a.command == 'eval':
        evaluate(a.csv)
    else:
        globals()[a.command]()


if __name__ == '__main__':
    sys.exit(main())
