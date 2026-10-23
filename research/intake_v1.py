"""Intake judge v1 pipeline (protocol: research/goal-engine-2026-10-04/intake-judge-v1/PROTOCOL.md).

    python -m research.intake_v1 split      # session split, counts only
    python -m research.intake_v1 owner      # map the 83 owner-judged items onto the new import
    python -m research.intake_v1 teacher    # Opus labels train/dev + owner items (cap 3,500 calls, cached)
    python -m research.intake_v1 check      # teacher vs owner on the 83 items (stop rule 0.75)
    python -m research.intake_v1 train      # fixed 6-config grid, dev macro-F1 pick, FREEZE.json

Private text stays in ~/.lcc/intake-v1/. The repo gets counts, ids and hashes only.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import random
import subprocess
import sys
import tempfile
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from research.intake_judge import BUCKETS, Judge, export, features
from research.intake_keywords import classify as keyword_classify
from research.llm_judge_arm import LIMIT_RE, _json_in

BASE = Path.home() / '.lcc' / 'intake-v1'
OLD = Path.home() / '.lcc' / 'request-log'
REPO = Path(__file__).resolve().parent
OUT = REPO / 'goal-engine-2026-10-04' / 'intake-judge-v1'
TAXONOMY = REPO / 'goal-engine-2026-10-04' / 'request-taxonomy-v1' / 'taxonomy-v2.json'
CUTOFF = '2026-10-09T00:00:00Z'
SEED = 20261023
CALL_CAP = 3500
BATCH = 20
WORKERS = 4
GRID = [(k, c) for k in ('char', 'char+word') for c in (0.3, 1.0, 3.0)]


def _read_jsonl(path):
    with open(path, encoding='utf-8') as fh:
        return [json.loads(line) for line in fh if line.strip()]


def _write_private(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding='utf-8')
    os.chmod(tmp, 0o600)
    tmp.replace(path)


def records():
    out = {}
    for p in sorted((BASE / 'imported').glob('*.jsonl')):
        for r in _read_jsonl(p):
            out[r['id']] = r
    return out


def categories():
    t = json.loads(TAXONOMY.read_text(encoding='utf-8'))
    return [c['id'] for c in t['categories']] + ['UNKNOWN'], t


# --- split -------------------------------------------------------------------------------------------------
def split():
    path = BASE / 'split.json'
    if path.exists():
        raise SystemExit(f'{path} exists: the split is built once')
    recs = records()
    first = {}
    for r in recs.values():
        ts = r.get('timestamp_utc')
        if ts:
            first[r['session_hash']] = min(first.get(r['session_hash'], ts), ts)
    held = {s for s, ts in first.items() if ts >= CUTOFF}
    trainval = sorted({r['session_hash'] for r in recs.values()} - held)
    rng = random.Random(SEED)
    rng.shuffle(trainval)
    dev = set(trainval[:len(trainval) // 5])
    assign = {i: ('heldout' if r['session_hash'] in held else 'dev' if r['session_hash'] in dev else 'train')
              for i, r in recs.items()}
    _write_private(path, assign)
    counts = Counter(assign.values())
    sessions = {k: len({recs[i]['session_hash'] for i, v in assign.items() if v == k}) for k in counts}
    by_source = Counter((assign[i], r['source']) for i, r in recs.items())
    summary = {'items': dict(counts), 'sessions': sessions,
               'by_split_source': {f'{a}|{s}': n for (a, s), n in sorted(by_source.items())}}
    (OUT / 'split-counts.json').write_text(json.dumps(summary, indent=1, sort_keys=True) + '\n')
    print(json.dumps(summary, indent=1, sort_keys=True))


# --- owner-judged items -----------------------------------------------------------------------------------
def owner():
    tax = OLD / 'taxonomy-v1'
    gold = {o['id']: o['owner_label'] for o in json.loads((tax / 'owner-judgments.json').read_text())}
    proposed_v2 = {}
    for p in sorted(tax.glob('labels-v2-*.jsonl')):
        for r in _read_jsonl(p):
            proposed_v2[r['id']] = r['label']
    with open(tax / 'taxonomy-review-result-2.csv', newline='', encoding='utf-8') as fh:
        for row in csv.DictReader(fh):
            gold[row['id']] = proposed_v2[row['id']] if row['verdict'] == 'right' else row['corrected']
    old = {}
    for p in sorted((OLD / 'imported').glob('*.jsonl')):
        for r in _read_jsonl(p):
            old[r['id']] = r
    by_key = defaultdict(list)
    for r in records().values():
        by_key[(r['source'], r.get('timestamp_utc'))].append(r)
    mapped, missing = {}, []
    for oid, label in gold.items():
        o = old.get(oid)
        cands = by_key.get((o['source'], o.get('timestamp_utc')), []) if o else []
        if o and len(cands) > 1 or (o and not o.get('timestamp_utc')):
            cands = [c for c in cands if c['goal'] == o['goal']] or cands[:0]
        if len(cands) == 1:
            mapped[cands[0]['id']] = label
        else:
            missing.append(oid)
    _write_private(BASE / 'owner-gold.json', mapped)
    summary = {'owner_items': len(gold), 'mapped': len(mapped), 'unmatched': len(missing)}
    print(json.dumps(summary))
    return summary


# --- teacher -------------------------------------------------------------------------------------------------
def teacher_system(cats, tax):
    lines = ['You label requests that a developer typed to a coding agent. Pick exactly one category per '
             'request, from the request text alone, using these definitions and decision rules.', '']
    for c in tax['categories']:
        lines += [f"- {c['id']}: {c['definition_pt']}", f"  Rule: {c['decision_rule']}"]
    lines += [f"- UNKNOWN: {tax['unknown_rule']}", '', f"Mixed requests: {tax['combined_requests_rule']}", '',
              'Placeholders like <TOKEN>, <EMAIL>, <PATH> are redactions. Reply with JSON only: '
              '{"answers": {"<request id>": "<category id>"}}. Do not use tools.']
    return '\n'.join(lines)


def teacher_argv(cats, tax):
    schema = {'type': 'object', 'required': ['answers'], 'properties': {'answers': {
        'type': 'object', 'additionalProperties': {'type': 'string', 'enum': cats}}}}
    argv = ['claude', '-p', '--model', 'opus', '--tools', '', '--output-format', 'json',
            '--json-schema', json.dumps(schema), '--no-session-persistence', '--disable-slash-commands',
            '--strict-mcp-config', '--permission-prompts', 'none', '--setting-sources', '',
            '--exclude-dynamic-system-prompt-sections', '--system-prompt', teacher_system(cats, tax)]
    assert not any('dangerously' in a for a in argv), 'never skip permissions'
    return argv


def _answers(stdout):
    try:
        env = json.loads(stdout)
    except ValueError:
        return _json_in(stdout)
    if isinstance(env, dict) and env.get('is_error'):
        return None
    so = env.get('structured_output') if isinstance(env, dict) else None
    if isinstance(so, dict) and isinstance(so.get('answers'), dict):
        return so['answers']
    return _json_in(env.get('result') if isinstance(env, dict) else stdout)


class LimitHit(RuntimeError):
    pass


def _call(argv, batch):
    body = 'REQUESTS:\n' + json.dumps({f'r{n}': r['goal'] for n, r in enumerate(batch)}, ensure_ascii=False)
    with tempfile.TemporaryDirectory() as cwd:
        p = subprocess.run(argv, input=body, capture_output=True, text=True, cwd=cwd, timeout=330,
                           env={k: v for k, v in os.environ.items() if not k.startswith(('PYTHON', 'ANTHROPIC_'))})
    ans = None if p.returncode else _answers(p.stdout)
    if ans is None:
        msg = p.stdout[-2000:] + p.stderr[-2000:]
        if LIMIT_RE.search(msg):
            raise LimitHit(LIMIT_RE.search(msg).group(0))
        raise RuntimeError(f'no answers (exit {p.returncode}): {p.stderr[-300:]}')
    return {r['id']: ans.get(f'r{n}') for n, r in enumerate(batch)}


def teacher(limit=None):
    cats, tax = categories()
    argv = teacher_argv(cats, tax)
    (BASE / 'teacher').mkdir(exist_ok=True)
    (BASE / 'teacher' / 'system-prompt.txt').write_text(teacher_system(cats, tax), encoding='utf-8')
    cache_path, calls_path = BASE / 'teacher' / 'labels.jsonl', BASE / 'teacher' / 'calls.json'
    done = {r['id']: r['label'] for r in _read_jsonl(cache_path)} if cache_path.exists() else {}
    calls = json.loads(calls_path.read_text())['calls'] if calls_path.exists() else 0
    assign = json.loads((BASE / 'split.json').read_text())
    recs = records()
    owner_ids = set(json.loads((BASE / 'owner-gold.json').read_text()))
    todo = [recs[i] for i in sorted(recs) if (assign[i] != 'heldout' or i in owner_ids) and i not in done]
    batches = [todo[k:k + BATCH] for k in range(0, len(todo), BATCH)][:limit]
    print(f'{len(done)} cached, {len(todo)} to label in {len(batches)} calls; calls so far {calls}', flush=True)
    stop = False

    def work(batch):
        nonlocal calls, stop
        if stop or calls >= CALL_CAP:
            return None
        calls += 1
        try:
            return _call(argv, batch)
        except LimitHit as e:
            stop = True
            print(f'usage limit: {e}; resume later from cache', flush=True)
        except (RuntimeError, subprocess.TimeoutExpired) as e:
            print(f'batch failed: {str(e)[:200]}', flush=True)
        return None

    with ThreadPoolExecutor(WORKERS) as pool, open(cache_path, 'a', encoding='utf-8') as fh:
        for n, got in enumerate(pool.map(work, batches)):
            for i, lab in (got or {}).items():
                if lab in cats:
                    fh.write(json.dumps({'id': i, 'label': lab}) + '\n')
            fh.flush()
            calls_path.write_text(json.dumps({'calls': calls}))
            if n % 10 == 0:
                print(f'{n + 1}/{len(batches)} batches, calls {calls}', flush=True)
    os.chmod(cache_path, 0o600)
    print(f'calls total {calls}')


def teacher_labels():
    return {r['id']: r['label'] for r in _read_jsonl(BASE / 'teacher' / 'labels.jsonl')}


def check():
    gold = json.loads((BASE / 'owner-gold.json').read_text())
    lab = teacher_labels()
    both = [i for i in gold if i in lab]
    agree = sum(gold[i] == lab[i] for i in both)
    res = {'owner_items_mapped': len(gold), 'teacher_labelled': len(both), 'agree': agree,
           'agreement': round(agree / len(both), 4) if both else None, 'stop_rule': 0.75,
           'keyword_agree': sum(gold[i] == keyword_classify(records()[i]['goal']) for i in both)}
    res['passes'] = bool(both) and agree / len(both) >= 0.75
    (OUT / 'teacher-check.json').write_text(json.dumps(res, indent=1) + '\n')
    print(json.dumps(res))
    return res


# --- model --------------------------------------------------------------------------------------------------
def _matrix(texts, kinds):
    idx, val, ptr = [], [], [0]
    for t in texts:
        f = features(t, kinds)
        idx.extend(f)
        val.extend(f.values())
        ptr.append(len(idx))
    import numpy as np
    return np.array(idx, dtype=np.int64), np.array(val, dtype=np.float64), np.array(ptr, dtype=np.int64)


def fit(texts, y, cats, kinds, C, iters=400, lr=0.05):
    """Multinomial LR, class-balanced, L2 = ||W||^2 / (2 C n); full-batch Adam, deterministic."""
    import numpy as np
    idx, val, ptr = _matrix(texts, kinds)
    n, k = len(texts), len(cats)
    rows = np.repeat(np.arange(n), np.diff(ptr))
    yi = np.array([cats.index(c) for c in y])
    counts = np.bincount(yi, minlength=k)
    sw = n / (k * np.maximum(counts, 1))[yi]
    Y = np.eye(k)[yi]
    W, b = np.zeros((BUCKETS, k)), np.zeros(k)
    mW, vW, mb, vb = (np.zeros_like(W), np.zeros_like(W), np.zeros(k), np.zeros(k))
    for t in range(1, iters + 1):
        Z = np.add.reduceat(W[idx] * val[:, None], ptr[:-1], axis=0) + b
        Z -= Z.max(1, keepdims=True)
        P = np.exp(Z)
        P /= P.sum(1, keepdims=True)
        G = (P - Y) * sw[:, None] / n
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


def macro_f1(gold, pred):
    labels = sorted(set(gold))
    f1 = []
    for c in labels:
        tp = sum(g == c and p == c for g, p in zip(gold, pred))
        fp = sum(g != c and p == c for g, p in zip(gold, pred))
        fn = sum(g == c and p != c for g, p in zip(gold, pred))
        f1.append(0 if tp == 0 else 2 * tp / (2 * tp + fp + fn))
    return sum(f1) / len(f1)


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def train():
    if (OUT / 'FREEZE.json').exists():
        raise SystemExit('FREEZE.json exists: v1 is frozen')
    cats, _ = categories()
    assign = json.loads((BASE / 'split.json').read_text())
    lab, recs = teacher_labels(), records()
    tr = [i for i in sorted(lab) if assign[i] == 'train']
    dv = [i for i in sorted(lab) if assign[i] == 'dev']
    gold_dev = [lab[i] for i in dv]
    rows, best = [], None
    (BASE / 'models').mkdir(exist_ok=True)
    for kinds, C in GRID:
        t0 = time.time()
        W, b = fit([recs[i]['goal'] for i in tr], [lab[i] for i in tr], cats, kinds, C)
        path = BASE / 'models' / f'intake-v1-{kinds}-C{C}.json'
        export(path, cats, kinds, W, b, {'C': C, 'train_items': len(tr), 'seed': SEED})
        j = Judge.load(path)  # evaluate the exported (float16) artifact, as shipped
        pred = [j.predict(recs[i]['goal'])[0] for i in dv]
        row = {'kinds': kinds, 'C': C, 'dev_macro_f1': round(macro_f1(gold_dev, pred), 4),
               'dev_accuracy': round(sum(g == p for g, p in zip(gold_dev, pred)) / len(dv), 4),
               'model_bytes': path.stat().st_size, 'fit_s': round(time.time() - t0, 1)}
        rows.append(row)
        print(json.dumps(row), flush=True)
        key = (row['dev_macro_f1'], -row['model_bytes'])
        if best is None or key > best[0]:
            best = (key, row, path)
    kw = [keyword_classify(recs[i]['goal']) for i in dv]
    majority = Counter(lab[i] for i in tr).most_common(1)[0][0]
    pick = best[2]
    final = BASE / 'model.json'
    final.write_bytes(pick.read_bytes())
    os.chmod(final, 0o600)
    files = {'model.json (~/.lcc/intake-v1)': final, 'research/intake_judge.py': REPO / 'intake_judge.py',
             'research/intake_keywords.py': REPO / 'intake_keywords.py', 'research/intake_v1.py': REPO / 'intake_v1.py',
             'teacher system prompt (~/.lcc/intake-v1/teacher)': BASE / 'teacher' / 'system-prompt.txt'}
    freeze = {'frozen_at_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
              'pick': best[1], 'grid': rows, 'train_items': len(tr), 'dev_items': len(dv),
              'dev_label_counts': dict(Counter(gold_dev).most_common()), 'majority_class': majority,
              'dev_keyword_baseline': {'macro_f1': round(macro_f1(gold_dev, kw), 4),
                                       'accuracy': round(sum(g == p for g, p in zip(gold_dev, kw)) / len(dv), 4)},
              'sha256': {k: _sha(v) for k, v in files.items()},
              'note': 'research/intake_v1.py includes the gold sampler and the eval (evaluate); its hash covers both'}
    (OUT / 'FREEZE.json').write_text(json.dumps(freeze, indent=1) + '\n')
    print(json.dumps(freeze['pick']))


# --- held-out gold and the one-shot test ------------------------------------------------------------------
def _committed(path):
    """FREEZE.json must be committed, unmodified, and on origin before held-out prompts are drawn."""
    rel = str(Path(path).relative_to(REPO.parent))
    git = ['git', '-C', str(REPO.parent)]
    tracked = subprocess.run(git + ['ls-files', '--error-unmatch', rel], capture_output=True).returncode == 0
    clean = subprocess.run(git + ['diff', '--quiet', 'HEAD', '--', rel]).returncode == 0
    pushed = subprocess.run(git + ['branch', '-r', '--contains', 'HEAD'], capture_output=True, text=True).stdout.strip()
    return tracked and clean and bool(pushed)


def gold_sample():
    """150 primary held-out prompts, at most 2 per session (seeded), excluding text seen in train/dev."""
    assign, recs = json.loads((BASE / 'split.json').read_text()), records()
    norm = lambda t: ' '.join(t.lower().split())  # noqa: E731
    seen = {norm(recs[i]['goal']) for i, s in assign.items() if s != 'heldout'}
    by_session = defaultdict(list)
    linked = 0
    for i in sorted(i for i, s in assign.items() if s == 'heldout'):
        if norm(recs[i]['goal']) in seen:
            linked += 1
            continue
        by_session[recs[i]['session_hash']].append(i)
    rng = random.Random(SEED)
    picks = []
    for s in sorted(by_session):
        ids = by_session[s][:]
        rng.shuffle(ids)
        picks.append(ids[:2])
    rng.shuffle(picks)
    pool = [i for pair in picks for i in pair]
    return pool, linked, len(by_session)


GOLD_PAGE = """<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Gabarito do intake</title>
<style>:root{--bg:#fafafa;--fg:#222;--card:#fff;--line:#ddd;--goal:#f3f3f3;--muted:#555;--ok:#2a9d4a}
@media (prefers-color-scheme:dark){:root{--bg:#161616;--fg:#eee;--card:#222;--line:#333;--goal:#2b2b2b;--muted:#aaa}}
body{font:16px/1.5 system-ui;max-width:860px;margin:0 auto;padding:16px;background:var(--bg);color:var(--fg)}
.item{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:12px 16px;margin:12px 0}
.done{border-left:6px solid var(--ok)}.goal{white-space:pre-wrap;word-break:break-word;background:var(--goal);padding:8px;border-radius:6px}
select{margin-top:8px;width:100%;font-size:16px;padding:6px}.def{color:var(--muted);font-size:14px}
#bar{position:sticky;top:0;background:var(--bg);padding:8px 0;border-bottom:1px solid var(--line)}
button{font-size:16px;padding:8px 16px}details{background:var(--card);padding:8px 12px;border-radius:8px}</style></head><body>
<h1>Gabarito: que tipo de pedido é este?</h1>
<p>São __N__ pedidos seus feitos depois de 09/10 (dados sensíveis trocados por &lt;MARCADORES&gt;). Para cada um,
escolha a categoria olhando <b>só o texto</b>, ou <b>Não sei</b>. Nenhuma resposta de modelo aparece aqui.
O progresso fica salvo no navegador. No fim, clique <b>Baixar resultado</b>.</p>
<details><summary><b>As categorias</b> (clique para abrir)</summary><ul>__GLOSSARY__</ul></details>
<div id="bar"><span id="count"></span> <button onclick="save()">Baixar resultado</button></div>
<div id="items"></div>
<script>
const ITEMS=__ITEMS__, CATS=__CATS__, KEY='intake-v1-gold';
let st={};try{st=JSON.parse(localStorage.getItem(KEY))||{}}catch(e){}
function persist(){try{localStorage.setItem(KEY,JSON.stringify(st))}catch(e){}render()}
function esc(s){return String(s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]))}
function render(){let n=0;document.getElementById('items').innerHTML=ITEMS.map((it,i)=>{const v=st[it.id]||'';if(v)n++;
 return `<div class="item ${v?'done':''}"><div>${i+1}.</div><div class="goal">${esc(it.goal)}</div>
 <select onchange="st['${it.id}']=this.value;persist()"><option value="">Escolha…</option>
 ${CATS.map(c=>`<option value="${c.id}" ${v===c.id?'selected':''}>${esc(c.name)}</option>`).join('')}
 <option value="unsure" ${v==='unsure'?'selected':''}>Não sei</option></select>
 ${v&&v!=='unsure'?`<div class="def">${esc(CATS.find(c=>c.id===v).definition)}</div>`:''}</div>`}).join('');
 document.getElementById('count').textContent=`${n}/${ITEMS.length} respondidos`}
function save(){const lines=['id,label'].concat(ITEMS.map(it=>`"${it.id}","${st[it.id]||''}"`));
 const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([lines.join('\\n')],{type:'text/csv'}));
 a.download='intake-v1-gold.csv';a.click()}
render();
</script></body></html>
"""


def gold_page(n=150, offset=0):
    import html
    if not _committed(OUT / 'FREEZE.json'):
        raise SystemExit('FREEZE.json must be committed and pushed before held-out prompts are drawn')
    _, tax = categories()
    pool, linked, sessions = gold_sample()
    items = [{'id': i, 'goal': records()[i]['goal']} for i in pool[offset:offset + n]]
    cats = [{'id': c['id'], 'name': c['name_pt'], 'definition': c['definition_pt']} for c in tax['categories']]
    cats.append({'id': 'UNKNOWN', 'name': 'Não dá para saber pelo texto',
                 'definition': 'Fragmento, colagem sem instrução ou texto quase todo redigido.'})
    glossary = ''.join(f"<li><b>{html.escape(c['name'])}</b>: {html.escape(c['definition'])}</li>" for c in cats)
    body = (GOLD_PAGE.replace('__GLOSSARY__', glossary).replace('__N__', str(len(items)))
            .replace('__ITEMS__', json.dumps(items, ensure_ascii=False).replace('</', '<\\/'))
            .replace('__CATS__', json.dumps(cats, ensure_ascii=False).replace('</', '<\\/')))
    out = BASE / 'gold' / ('gabarito.html' if not offset else f'gabarito-{offset}.html')
    out.parent.mkdir(exist_ok=True)
    out.write_text(body, encoding='utf-8')
    os.chmod(out, 0o600)
    summary = {'gold_items_drawn': len(items), 'offset': offset, 'primary_pool': len(pool),
               'heldout_sessions_in_pool': sessions, 'seen_text_excluded': linked}
    (OUT / f'gold-draw{"-" + str(offset) if offset else ""}.json').write_text(json.dumps(summary, indent=1) + '\n')
    print(json.dumps(summary))
    print(out)


def _bootstrap(groups, diff_fn, n=2000):
    rng = random.Random(SEED)
    keys = sorted(groups)
    vals = []
    for _ in range(n):
        sample = [i for k in (rng.choice(keys) for _ in keys) for i in groups[k]]
        vals.append(diff_fn(sample))
    vals.sort()
    return round(vals[int(0.025 * n)], 4), round(vals[int(0.975 * n) - 1], 4)


def _read_gold(path):
    with open(path, newline='', encoding='utf-8') as fh:
        return {row['id']: row['label'] for row in csv.DictReader(fh)}


def evaluate(pass_paths):
    """One-shot test on the owner gold (amendment 2): primary = items both passes label alike;
    each full pass is reported as a sensitivity view. Writes test-results.json; refuses to run twice."""
    out = OUT / 'test-results.json'
    if out.exists():
        raise SystemExit('the held-out gold is spent: test-results.json exists')
    passes = [_read_gold(p) for p in pass_paths]
    clean = [{i: v for i, v in g.items() if v not in ('', 'unsure')} for g in passes]
    views = {f'pass{n + 1}': g for n, g in enumerate(clean)}
    if len(clean) == 2:
        views = {'primary_agree': {i: v for i, v in clean[0].items() if clean[1].get(i) == v}, **views}
    all_ids = sorted(set().union(*clean))
    recs, lab = records(), teacher_labels()
    freeze = json.loads((OUT / 'FREEZE.json').read_text())
    cats, tax = categories()
    # arms, computed once on every labelled id
    j = Judge.load(BASE / 'model.json')
    v1 = {i: j.predict(recs[i]['goal'])[0] for i in all_ids}
    texts = BASE / 'gold' / 'cost-input.json'
    _write_private(texts, [recs[i]['goal'] for i in all_ids])
    p = subprocess.run([sys.executable, '-m', 'research.intake_judge', str(BASE / 'model.json'), str(texts)],
                       capture_output=True, text=True, check=True, cwd=REPO.parent)
    cost = json.loads(p.stdout)
    lat = sorted(cost['latency_ms'])
    kw = {i: keyword_classify(recs[i]['goal']) for i in all_ids}
    maj = {i: freeze['majority_class'] for i in all_ids}
    cache = BASE / 'gold' / 'opus.json'  # cached so a failed call does not re-spend finished batches
    opus = json.loads(cache.read_text()) if cache.exists() else {}
    argv = teacher_argv(cats, tax)
    todo = [i for i in all_ids if i not in opus]
    for k in range(0, len(todo), BATCH):
        opus.update(_call(argv, [recs[i] for i in todo[k:k + BATCH]]))
        _write_private(cache, opus)
    arms = {'intake_v1': v1, 'keyword': kw, 'majority': maj, 'opus': opus}
    res = {'pass_sha256': [_sha(p) for p in pass_paths], 'pass_items': [len(g) for g in passes],
           'pass_unsure': [sum(v in ('', 'unsure') for v in g.values()) for g in passes],
           'owner_self_agreement': (sum(clean[0].get(i) == v for i, v in clean[1].items()) if len(clean) == 2 else None),
           'cost': {'median_ms': round(lat[len(lat) // 2], 3), 'p90_ms': round(lat[int(0.9 * len(lat))], 3),
                    'load_ms': round(cost['load_ms'], 1), 'model_bytes': (BASE / 'model.json').stat().st_size,
                    'peak_rss_mb': round(cost['peak_rss_mb'], 1), 'method': 'fresh process, 1 thread'},
           'views': {}}
    c = res['cost']
    cost_ok = c['median_ms'] <= 5 and c['p90_ms'] <= 20 and c['model_bytes'] <= 2_000_000 and c['peak_rss_mb'] <= 100
    for name, gold in views.items():
        res['views'][name] = _score(gold, arms, recs, lab, cost_ok)
    out.write_text(json.dumps(res, indent=1) + '\n')
    print(json.dumps({'cost': res['cost'], 'self_agreement': res['owner_self_agreement'],
                      **{n: {k: v[k] for k in ('items', 'arms', 'diffs', 'acceptance')} for n, v in res['views'].items()}},
                     indent=1))


def _score(gold, arms, recs, lab, cost_ok):
    ids = sorted(gold)
    v1 = arms['intake_v1']
    groups = defaultdict(list)
    for i in ids:
        groups[recs[i]['session_hash']].append(i)

    def acc(arm, s):
        return sum(arms[arm].get(i) == gold[i] for i in s) / len(s)

    def mf1(arm, s):
        return macro_f1([gold[i] for i in s], [arms[arm].get(i) for i in s])

    res = {'items': len(ids), 'sessions': len(groups),
           'gold_label_counts': dict(Counter(gold.values()).most_common()), 'arms': {}, 'diffs': {}}
    for a in arms:
        res['arms'][a] = {'accuracy': round(acc(a, ids), 4), 'macro_f1': round(mf1(a, ids), 4)}
    for other in ('keyword', 'majority', 'opus'):
        res['diffs'][f'v1-{other}'] = {
            'accuracy': round(acc('intake_v1', ids) - acc(other, ids), 4),
            'accuracy_ci': _bootstrap(groups, lambda s, o=other: acc('intake_v1', s) - acc(o, s)),
            'macro_f1': round(mf1('intake_v1', ids) - mf1(other, ids), 4),
            'macro_f1_ci': _bootstrap(groups, lambda s, o=other: mf1('intake_v1', s) - mf1(o, s))}
    d = res['diffs']
    res['acceptance'] = {
        '1_beats_rules': all(d[f'v1-{o}'][m][0] > 0 for o in ('keyword', 'majority') for m in ('accuracy_ci', 'macro_f1_ci')),
        '2_close_to_opus': d['v1-opus']['accuracy_ci'][0] > -0.10,
        '3_cost': cost_ok}
    res['recall_by_category'] = {
        cat: {'n': len(g), **{a: round(sum(arms[a].get(i) == cat for i in g) / len(g), 3) for a in arms}}
        for cat in sorted(set(gold.values())) for g in [[i for i in ids if gold[i] == cat]]}
    res['v1_precision_by_category'] = {
        cat: round(sum(gold[i] == cat for i in ids if v1[i] == cat) / max(1, sum(v1[i] == cat for i in ids)), 3)
        for cat in sorted({v1[i] for i in ids})}
    res['by_language'] = {l: {a: round(acc(a, s), 4) for a in arms} | {'n': len(s)}
                          for l in sorted({str(recs[i]['language']) for i in ids})
                          for s in [[i for i in ids if str(recs[i]['language']) == l]]}
    res['by_source'] = {src: {a: round(acc(a, s), 4) for a in arms} | {'n': len(s)}
                        for src in sorted({recs[i]['source'] for i in ids})
                        for s in [[i for i in ids if recs[i]['source'] == src]]}
    res['v1_confusion'] = {f'{g}->{p}': n for (g, p), n in sorted(Counter((gold[i], v1[i]) for i in ids).items())}
    res['teacher_labels_on_gold'] = sum(i in lab for i in ids)
    return res


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('command', choices=('split', 'owner', 'teacher', 'check', 'train', 'gold-page', 'eval'))
    ap.add_argument('--limit', type=int, help='teacher: max batches this run')
    ap.add_argument('--offset', type=int, default=0, help='gold-page: top-up draw starts here')
    ap.add_argument('csv', nargs='*', help='eval: one CSV per owner labelling pass')
    a = ap.parse_args(argv)
    if a.command == 'teacher':
        teacher(a.limit)
    elif a.command == 'gold-page':
        gold_page(offset=a.offset)
    elif a.command == 'eval':
        evaluate(a.csv)
    else:
        globals()[a.command]()


if __name__ == '__main__':
    sys.exit(main())
