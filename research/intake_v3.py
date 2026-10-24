"""Intake judge v3 pipeline (protocol + amendments: research/goal-engine-2026-10-04/intake-judge-v3/).

    ~/.lcc/public/.venv/bin/python -m research.intake_v3 build   # needs pyarrow: public prompts -> JSONL
    python -m research.intake_v3 teacher        # Opus labels public train/dev (v2 teacher, cap 600 calls)
    python -m research.intake_v3 train          # 6 configs (family B x data ii/iii x C), FREEZE.json
    python -m research.intake_v3 external-draw  # after the pushed freeze: 100 items + Claude/Codex/Gemini votes
    python -m research.intake_v3 eval --external gold.csv [--owner pass1.csv pass2.csv]

Private and public text stays in ~/.lcc/intake-v3/ (public files in ~/.lcc/public/). The repo gets counts,
ids and hashes only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import re
import subprocess
import sys
import tempfile
import time
from collections import Counter, defaultdict
from pathlib import Path

from research import intake_v1 as v1
from research import intake_v2 as v2

BASE = Path.home() / '.lcc' / 'intake-v3'
PUBLIC = Path.home() / '.lcc' / 'public'
OUT = v1.REPO / 'goal-engine-2026-10-04' / 'intake-judge-v3'
SEED = 20261025
CALL_CAP = 600
WILDCHAT_N = 3000
GRID = [(data, C) for data in ('ii', 'iii') for C in (3.0, 10.0, 30.0)]
OWNER_DEV_F1_MIN = 0.480
V1_GOLD_ACC_MIN = 0.509
PREV = 600


# --- build ----------------------------------------------------------------------------------------------------
def _rec(source, group, n, goal, prev, rl):
    goal = rl.redact(goal)[:rl.MAX_GOAL_CHARS]
    prev = rl.redact(prev)[-PREV:] if prev else None
    rid = hashlib.sha256(f'{source}\0{group}\0{n}\0{goal}'.encode()).hexdigest()[:16]
    return {'id': rid, 'source': source, 'group': group, 'goal': goal, 'prev_agent': prev,
            'language': rl.detect_language(goal)}


def _prompts(messages):
    """[(text, prev assistant text)] for human prompts of 1-1000 chars in an OpenAI-style message list."""
    out, prev = [], None
    for m in messages:
        m = m if isinstance(m, dict) else json.loads(m)
        role, content = m.get('role'), m.get('content')
        if role == 'assistant':
            if isinstance(content, str) and content.strip():
                prev = content.strip()
        elif role == 'user' and isinstance(content, str):
            t = content.strip()
            if t and not t.startswith('<') and len(t) <= 1000:
                out.append((t, prev))
            prev = None
    return out


def _split_groups(groups, held_share=0.2, dev_share=0.2):
    keys = sorted(groups)
    rng = random.Random(SEED)
    rng.shuffle(keys)
    n_held = round(len(keys) * held_share)
    held, rest = set(keys[:n_held]), keys[n_held:]
    dev = set(rest[:round(len(rest) * dev_share)])
    return {k: 'heldout' if k in held else 'dev' if k in dev else 'train' for k in keys}


def build():
    import pyarrow.parquet as pq
    sys.path.insert(0, '/Users/Master/lcc/src')
    from lcc import request_log as rl
    out = BASE / 'public.jsonl'
    if out.exists():
        raise SystemExit(f'{out} exists: built once')
    BASE.mkdir(mode=0o700, exist_ok=True)
    recs, files = [], {}
    # public Claude Code: split by session
    path = PUBLIC / 'claude-fable-5' / '0.parquet'
    files[str(path.relative_to(PUBLIC))] = v1._sha(path)
    rows = pq.read_table(path, columns=['harness', 'session_id', 'messages']).to_pylist()
    cc = [r for r in rows if r['harness'] == 'claude_code']
    cc_split = _split_groups({r['session_id'] for r in cc})
    for r in cc:
        for n, (t, prev) in enumerate(_prompts(r['messages'])):
            rec = _rec('cc_public', r['session_id'], n, t, prev, rl)
            rec['split'] = cc_split[r['session_id']]
            recs.append(rec)
    # WildChat: coding conversations, en/pt, not toxic; split by hashed IP
    wc = []
    for path in sorted((PUBLIC / 'wildchat-4.8m').glob('*.parquet')):
        files[str(path.relative_to(PUBLIC))] = v1._sha(path)
        for r in pq.read_table(path, columns=['conversation_hash', 'language', 'toxic', 'hashed_ip',
                                               'conversation']).to_pylist():
            if r['language'] not in ('English', 'Portuguese') or r['toxic']:
                continue
            conv = r['conversation']
            if not any(m.get('role') == 'assistant' and '```' in (m.get('content') or '') for m in conv):
                continue
            for n, (t, prev) in enumerate(_prompts(conv)):
                rec = _rec('wildchat', r['hashed_ip'], f"{r['conversation_hash']}:{n}", t, prev, rl)
                rec['wc_language'] = r['language']
                wc.append(rec)
    wc_split = _split_groups({r['group'] for r in wc})
    for r in wc:
        r['split'] = wc_split[r['group']]
    pool = [r for r in wc if r['split'] != 'heldout']
    rng = random.Random(SEED)
    rng.shuffle(pool)
    pt = [r for r in pool if r['wc_language'] == 'Portuguese']
    en = [r for r in pool if r['wc_language'] == 'English']
    keep = pt + en[:max(0, WILDCHAT_N - len(pt))]
    held = [r for r in wc if r['split'] == 'heldout']
    recs += keep + held
    with open(out, 'w', encoding='utf-8') as fh:
        fh.writelines(json.dumps(r, ensure_ascii=False) + '\n' for r in recs)
    os.chmod(out, 0o600)
    counts = Counter((r['source'], r['split']) for r in recs)
    summary = {'files_sha256': files, 'ruleset_sha256': rl.RULESET_SHA256,
               'items': {f'{s}|{p}': n for (s, p), n in sorted(counts.items())},
               'groups': {f'{s}|{p}': len({r['group'] for r in recs if r['source'] == s and r['split'] == p})
                          for (s, p) in sorted(counts)},
               'with_prev': {s: sum(bool(r['prev_agent']) for r in recs if r['source'] == s)
                             for s in ('cc_public', 'wildchat')},
               'wildchat_train_dev_pt': len(pt), 'wildchat_pool_train_dev': len(pool)}
    OUT.mkdir(exist_ok=True)
    (OUT / 'build-counts.json').write_text(json.dumps(summary, indent=1, sort_keys=True) + '\n')
    print(json.dumps(summary, indent=1, sort_keys=True))


def public():
    return {r['id']: r for r in v1._read_jsonl(BASE / 'public.jsonl')}


# --- teacher (the v2 teacher, unchanged) --------------------------------------------------------------------------
def teacher():
    cats, _ = v1.categories()
    argv = v2.teacher_argv()
    (BASE / 'teacher').mkdir(exist_ok=True)
    cache = BASE / 'teacher' / 'labels.jsonl'
    done = {r['id'] for r in v1._read_jsonl(cache)} if cache.exists() else set()
    recs = public()
    todo = [r for i, r in sorted(recs.items()) if r['split'] != 'heldout' and i not in done]
    batches = [todo[k:k + v1.BATCH] for k in range(0, len(todo), v1.BATCH)]
    calls_path = BASE / 'teacher' / 'calls.json'
    calls = json.loads(calls_path.read_text())['calls'] if calls_path.exists() else 0
    print(f'{len(done)} cached, {len(todo)} to label in {len(batches)} calls; calls so far {calls}', flush=True)
    import threading
    from concurrent.futures import ThreadPoolExecutor
    state, lock = {'stop': False, 'calls': calls}, threading.Lock()

    def work(batch):
        with lock:
            if state['stop'] or state['calls'] >= CALL_CAP:
                return None
            state['calls'] += 1
        try:
            return v2._call(argv, batch)
        except v1.LimitHit as e:
            state['stop'] = True
            print(f'usage limit: {e}', flush=True)
        except (RuntimeError, subprocess.TimeoutExpired) as e:
            print(f'batch failed: {str(e)[:200]}', flush=True)
        return None

    with ThreadPoolExecutor(v1.WORKERS) as pool, open(cache, 'a', encoding='utf-8') as fh:
        for n, got in enumerate(pool.map(work, batches)):
            for i, lab in (got or {}).items():
                if lab in cats:
                    fh.write(json.dumps({'id': i, 'label': lab}) + '\n')
            fh.flush()
            with lock:
                calls_path.write_text(json.dumps({'calls': state['calls']}))
            if n % 10 == 0:
                print(f'{n + 1}/{len(batches)} batches, calls {state["calls"]}', flush=True)
    os.chmod(cache, 0o600)
    lab = {r['id']: r['label'] for r in v1._read_jsonl(cache)}
    res = {'public_labelled': len(lab), 'calls': state['calls'],
           'label_counts': {s: dict(Counter(lab[i] for i in lab if recs[i]['source'] == s).most_common())
                            for s in ('cc_public', 'wildchat')}}
    (OUT / 'teacher-counts.json').write_text(json.dumps(res, indent=1) + '\n')
    print(json.dumps(res))


def public_labels():
    return {r['id']: r['label'] for r in v1._read_jsonl(BASE / 'teacher' / 'labels.jsonl')}


# --- train / select ----------------------------------------------------------------------------------------------
def train():
    if (OUT / 'FREEZE.json').exists():
        raise SystemExit('FREEZE.json exists: v3 is frozen')
    from research.intake_judge_v2 import Judge, export, vector
    cats, _ = v1.categories()
    o_assign = json.loads((v2.BASE / 'split.json').read_text())
    o_recs, o_lab = v2.records(), v2.teacher_labels()
    owner_gold = json.loads((v2.BASE / 'owner-dev.json').read_text())
    p_recs, p_lab = public(), public_labels()
    o_tr = [i for i in sorted(o_lab) if o_assign.get(i) == 'train']
    o_dv = [i for i in sorted(o_lab) if o_assign.get(i) == 'dev']
    p_tr = {s: [i for i in sorted(p_lab) if p_recs[i]['source'] == s and p_recs[i]['split'] == 'train']
            for s in ('cc_public', 'wildchat')}
    p_dv = [i for i in sorted(p_lab) if p_recs[i]['split'] == 'dev']
    data = {'ii': p_tr['cc_public'], 'iii': p_tr['cc_public'] + p_tr['wildchat']}
    item = lambda i: o_recs[i] if i in o_recs else p_recs[i]  # noqa: E731
    label = lambda i: o_lab[i] if i in o_lab else p_lab[i]  # noqa: E731
    (BASE / 'models').mkdir(exist_ok=True)
    table = []
    for d, C in GRID:
        t0 = time.time()
        tr = o_tr + data[d]
        W, b = v2.fit_vectors([vector(item(i)['goal'], item(i).get('prev_agent'), 'B') for i in tr],
                              [label(i) for i in tr], cats, C)
        path = BASE / 'models' / f'intake-v3-B-{d}-C{C}.json'
        export(path, cats, 'B', W, b, {'C': C, 'data': d, 'train_items': len(tr), 'seed': SEED})
        j = Judge.load(path)
        pred = {i: j.predict(item(i)['goal'], item(i).get('prev_agent')) for i in set(o_dv) | set(p_dv) | set(owner_gold)}
        f1 = lambda ids: v1.macro_f1([label(i) for i in ids], [pred[i][0] for i in ids])  # noqa: E731
        cost = v2._bench(path, [[item(i)['goal'], item(i).get('prev_agent')] for i in o_dv + p_dv], 'B')
        size = path.stat().st_size
        row = {'data': d, 'C': C, 'train_items': len(tr),
               'owner_dev_macro_f1': round(f1(o_dv), 4), 'public_dev_macro_f1': round(f1(p_dv), 4),
               'cc_dev_macro_f1': round(f1([i for i in p_dv if p_recs[i]['source'] == 'cc_public']), 4),
               'wildchat_dev_macro_f1': round(f1([i for i in p_dv if p_recs[i]['source'] == 'wildchat']), 4),
               'owner_v1_gold_accuracy': round(sum(pred[i][0] == owner_gold[i] for i in owner_gold) / len(owner_gold), 4),
               'files_bytes': size, **cost, 'fit_s': round(time.time() - t0, 1)}
        row['score'] = round((row['owner_dev_macro_f1'] + row['public_dev_macro_f1']) / 2, 4)
        med, p90, max_bytes, max_rss = v2.BUDGET['B']
        row['within_budget'] = (cost['median_ms'] <= med and cost['p90_ms'] <= p90 and size <= max_bytes
                                and cost['peak_rss_mb'] <= max_rss)
        row['eligible'] = (row['within_budget'] and row['owner_dev_macro_f1'] >= OWNER_DEV_F1_MIN
                           and row['owner_v1_gold_accuracy'] >= V1_GOLD_ACC_MIN)
        row['threshold'], row['threshold_coverage'], row['threshold_accuracy'] = v2._threshold(
            [(pred[i][1], pred[i][0] == label(i)) for i in o_dv + p_dv])
        table.append(row)
        print(json.dumps(row), flush=True)
    elig = [r for r in table if r['eligible']]
    pick = max(elig, key=lambda r: (r['score'], -r['train_items'])) if elig else None
    freeze = {'frozen_at_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'grid': table, 'pick': pick,
              'owner_train': len(o_tr), 'owner_dev': len(o_dv), 'public_dev': len(p_dv),
              'majority_class': Counter(label(i) for i in o_tr + data['iii']).most_common(1)[0][0]}
    files = {'research/intake_v3.py': v1.REPO / 'intake_v3.py', 'research/intake_v2.py': v1.REPO / 'intake_v2.py',
             'research/intake_judge_v2.py': v1.REPO / 'intake_judge_v2.py',
             'research/intake_keywords.py': v1.REPO / 'intake_keywords.py',
             'v2 teacher prompt': v2.BASE / 'teacher' / 'system-prompt.txt',
             'public.jsonl (~/.lcc/intake-v3)': BASE / 'public.jsonl'}
    if pick:
        dst = BASE / 'pick.json'
        dst.write_bytes((BASE / 'models' / f"intake-v3-B-{pick['data']}-C{pick['C']}.json").read_bytes())
        os.chmod(dst, 0o600)
        files['pick.json (~/.lcc/intake-v3)'] = dst
    freeze['sha256'] = {k: v1._sha(p) for k, p in files.items()}
    (OUT / 'FREEZE.json').write_text(json.dumps(freeze, indent=1) + '\n')
    print(json.dumps({'pick': pick}, indent=1))


# --- external gold: draw, three votes, page --------------------------------------------------------------------
def external_sample():
    recs = public()
    rng = random.Random(SEED)
    cc = defaultdict(list)
    wc = defaultdict(list)
    for i in sorted(recs):
        r = recs[i]
        if r['split'] != 'heldout':
            continue
        (cc if r['source'] == 'cc_public' else wc)[r['group']].append(i)
    out = []
    for groups, per, cap in ((cc, 2, 30),):
        keys = sorted(groups)
        rng.shuffle(keys)
        for k in keys:
            ids = groups[k][:]
            rng.shuffle(ids)
            out += ids[:per]
        out = out[:cap]
    wkeys = sorted(wc)
    rng.shuffle(wkeys)
    picks = []
    for k in wkeys:
        ids = wc[k][:]
        rng.shuffle(ids)
        picks.append(ids[0])
    pt = [i for i in picks if recs[i].get('wc_language') == 'Portuguese'][:20]
    en = [i for i in picks if recs[i].get('wc_language') == 'English']
    out += pt + en[:100 - len(out) - len(pt)]
    rng.shuffle(out)
    return out


def _codex_vote(batch):
    cats, _ = v1.categories()
    schema = {'type': 'object', 'additionalProperties': False, 'required': ['answers'], 'properties': {'answers': {
        'type': 'object', 'additionalProperties': False, 'required': [f'r{n}' for n in range(len(batch))],
        'properties': {f'r{n}': {'type': 'string', 'enum': cats} for n in range(len(batch))}}}}
    body = (v2.teacher_system() + '\n\nREQUESTS:\n'
            + json.dumps({f'r{n}': {'previous_agent_turn': r.get('prev_agent'), 'request': r['goal']}
                          for n, r in enumerate(batch)}, ensure_ascii=False))
    with tempfile.TemporaryDirectory() as d:
        sp, op = Path(d) / 'schema.json', Path(d) / 'out.json'
        sp.write_text(json.dumps(schema))
        (Path(d) / 'cwd').mkdir()
        subprocess.run(['codex', 'exec', '-m', 'gpt-6.1-sol', '-s', 'read-only', '--skip-git-repo-check', '--ephemeral',
                        '--output-schema', str(sp), '-C', str(Path(d) / 'cwd'), '-o', str(op), '-'],
                       input=body, capture_output=True, text=True, timeout=900, check=True)
        ans = json.loads(op.read_text())['answers']
    return {r['id']: ans.get(f'r{n}') for n, r in enumerate(batch)}


BRIDGE = [sys.executable, str(Path.home() / 'gemini-linkedin-extension' / 'cli' / 'antigravity-web-cli.py'),
          '--domain', 'gemini.google.com']


def _bridge(*args, timeout=120):
    p = subprocess.run(BRIDGE + list(args), capture_output=True, text=True, timeout=timeout, check=True)
    return json.loads(p.stdout) if p.stdout.strip().startswith('{') else {}


def _gemini_vote(batch):
    """Gemini Argon on gemini.google.com via the owner's browser bridge, in a temporary chat."""
    cats, _ = v1.categories()
    _bridge('--navigate', 'https://gemini.google.com/app')
    time.sleep(4)
    tree = _bridge('--observe', '--light', '--max', '80')['a11yTree']
    if 'No momento: Argon' not in tree:
        raise RuntimeError('Gemini mode is not Argon')
    temp = re.search(r'\[(e\d+)\] \(button\) "Chat momentâneo"', tree)
    if temp:
        _bridge('--click', temp.group(1))
        time.sleep(2)
        tree = _bridge('--observe', '--light', '--max', '80')['a11yTree']
    box = re.search(r'\[(e\d+)\] \(div\) "Insira um comando para o Gemini"', tree).group(1)
    msg = (v2.teacher_system() + '\n\nREQUESTS:\n'
           + json.dumps({f'r{n}': {'previous_agent_turn': r.get('prev_agent'), 'request': r['goal']}
                         for n, r in enumerate(batch)}, ensure_ascii=False)
           + '\n\nReply with JSON only, one line: {"answers": {"r0": "<category id>", ...}}')
    # Trusted typing fires real input events; plain --type leaves Gemini's send button hidden.
    _bridge('--trusted-type', msg, '--target', box, timeout=600)
    time.sleep(2)
    sent = _bridge('--cdp-eval', '(() => { const b = [...document.querySelectorAll("button")]'
                   '.find(x => x.getAttribute("aria-label") === "Enviar mensagem"); '
                   'if (!b) return "no-button"; b.click(); return "ok"; })()').get('result')
    if sent != 'ok':
        raise RuntimeError(f'Gemini send failed: {sent}')
    last = ('(() => { const r = [...document.querySelectorAll("model-response")]; '
            'return r.length ? r[r.length - 1].innerText : ""; })()')
    for _ in range(60):
        time.sleep(6)
        m = re.search(r'\{"answers"\s*:\s*\{[^{}]*\}\s*\}', _bridge('--cdp-eval', last).get('result') or '')
        if m:
            try:
                ans = json.loads(m.group(0))['answers']
            except ValueError:
                continue  # still streaming
            if len(ans) >= len(batch):
                return {r['id']: (ans.get(f'r{n}') if ans.get(f'r{n}') in cats else None) for n, r in enumerate(batch)}
    raise RuntimeError('no Gemini answer')


def external_draw():
    if not v1._committed(OUT / 'FREEZE.json'):
        raise SystemExit('FREEZE.json must be committed and pushed before the external gold is drawn')
    recs, ids = public(), external_sample()
    votes_path = BASE / 'gold' / 'votes.json'
    votes_path.parent.mkdir(exist_ok=True)
    votes = json.loads(votes_path.read_text()) if votes_path.exists() else {'claude': {}, 'codex': {}, 'gemini': {}}
    argv = v2.teacher_argv()
    for voter, fn in (('claude', lambda b: v2._call(argv, b)), ('codex', _codex_vote), ('gemini', _gemini_vote)):
        todo = [i for i in ids if i not in votes[voter]]
        for k in range(0, len(todo), v1.BATCH):
            votes[voter].update(fn([recs[i] for i in todo[k:k + v1.BATCH]]))
            v1._write_private(votes_path, votes)
            print(f'{voter}: {len(votes[voter])}/{len(ids)}', flush=True)
    _external_page(ids, recs, votes)
    summary = {'items': len(ids), 'cc_public': sum(recs[i]['source'] == 'cc_public' for i in ids),
               'wildchat_pt': sum(recs[i].get('wc_language') == 'Portuguese' for i in ids),
               'wildchat_en': sum(recs[i].get('wc_language') == 'English' for i in ids),
               'votes_missing': {v: sum(votes[v].get(i) is None for i in ids) for v in votes},
               'all_three_agree': sum(len({votes[v].get(i) for v in votes}) == 1 for i in ids)}
    (OUT / 'external-draw.json').write_text(json.dumps(summary, indent=1) + '\n')
    print(json.dumps(summary))


EXTERNAL_PAGE = """<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Gabarito externo</title>
<style>:root{--bg:#fafafa;--fg:#222;--card:#fff;--line:#ddd;--goal:#f3f3f3;--muted:#555;--ok:#2a9d4a;--vote:#eef4ff}
@media (prefers-color-scheme:dark){:root{--bg:#161616;--fg:#eee;--card:#222;--line:#333;--goal:#2b2b2b;--muted:#aaa;--vote:#1f2a3a}}
body{font:16px/1.5 system-ui;max-width:860px;margin:0 auto;padding:16px;background:var(--bg);color:var(--fg)}
.item{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:12px 16px;margin:12px 0}
.done{border-left:6px solid var(--ok)}.goal{white-space:pre-wrap;word-break:break-word;background:var(--goal);padding:8px;border-radius:6px}
.prev{opacity:.75;font-size:14px}.def{color:var(--muted);font-size:14px}select{margin-top:8px;width:100%;font-size:16px;padding:6px}
.votes{background:var(--vote);padding:8px;border-radius:6px;margin-top:8px;font-size:14px}
#bar{position:sticky;top:0;background:var(--bg);padding:8px 0;border-bottom:1px solid var(--line)}
button{font-size:16px;padding:8px 16px}details{background:var(--card);padding:8px 12px;border-radius:8px}</style></head><body>
<h1>Gabarito externo: pedidos de outras pessoas</h1>
<p>São __N__ pedidos de outras pessoas (dados públicos). Para cada um: <b>1)</b> escolha a categoria do pedido, usando o
turno do assistente só como contexto; <b>2)</b> aí aparecem os votos de Claude, Codex e Gemini; confirme ou mude.
O progresso fica salvo no navegador. No fim, clique <b>Baixar resultado</b>.</p>
<details><summary><b>As categorias</b> (clique para abrir)</summary><ul>__GLOSSARY__</ul></details>
<div id="bar"><span id="count"></span> <button onclick="save()">Baixar resultado</button></div>
<div id="items"></div>
<script>
const ITEMS=__ITEMS__, CATS=__CATS__, KEY='intake-v3-external';
const NAME=Object.fromEntries(CATS.map(c=>[c.id,c.name]));NAME.unsure='Não sei';
let st={};try{st=JSON.parse(localStorage.getItem(KEY))||{}}catch(e){}
function persist(){try{localStorage.setItem(KEY,JSON.stringify(st))}catch(e){}render()}
function esc(s){return String(s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]))}
function sel(id,k,v){return `<select onchange="setv('${id}','${k}',this.value)"><option value="">${k==='blind'?'Escolha…':'Confirme ou mude…'}</option>
 ${CATS.map(c=>`<option value="${c.id}" ${v===c.id?'selected':''}>${esc(c.name)}</option>`).join('')}
 <option value="unsure" ${v==='unsure'?'selected':''}>Não sei</option></select>`}
function render(){let n=0;document.getElementById('items').innerHTML=ITEMS.map((it,i)=>{const s=st[it.id]||{};if(s.final)n++;
 return `<div class="item ${s.final?'done':''}"><div>${i+1}.</div>
 ${it.prev?`<div class="def">Último turno do assistente (final):</div><div class="goal prev">${esc(it.prev)}</div><div class="def">Pedido:</div>`:''}
 <div class="goal">${esc(it.goal)}</div>${sel(it.id,'blind',s.blind)}
 ${s.blind?`<div class="votes">Claude: <b>${esc(NAME[it.votes.claude]||'—')}</b> · Codex: <b>${esc(NAME[it.votes.codex]||'—')}</b> · Gemini: <b>${esc(NAME[it.votes.gemini]||'—')}</b></div>${sel(it.id,'final',s.final)}`:''}
 </div>`}).join('');document.getElementById('count').textContent=`${n}/${ITEMS.length} finalizados`}
function setv(id,k,v){st[id]=Object.assign(st[id]||{},{[k]:v});if(k==='blind'&&!st[id].final)st[id].final=v;persist()}
function save(){const lines=['id,blind,final'].concat(ITEMS.map(it=>{const s=st[it.id]||{};return `"${it.id}","${s.blind||''}","${s.final||''}"`}));
 const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([lines.join('\\n')],{type:'text/csv'}));
 a.download='intake-v3-external.csv';a.click()}
render();
</script></body></html>
"""


def _external_page(ids, recs, votes):
    import html
    _, tax = v1.categories()
    cats = [{'id': x['id'], 'name': x['name_pt'], 'definition': x['definition_pt']} for x in tax['categories']]
    cats.append({'id': 'UNKNOWN', 'name': 'Não dá para saber', 'definition': 'Fragmento, colagem sem instrução ou texto quase todo redigido.'})
    items = [{'id': i, 'goal': recs[i]['goal'], 'prev': recs[i].get('prev_agent') or '',
              'votes': {v: votes[v].get(i) for v in votes}} for i in ids]
    glossary = ''.join(f"<li><b>{html.escape(x['name'])}</b>: {html.escape(x['definition'])}</li>" for x in cats)
    body = (EXTERNAL_PAGE.replace('__GLOSSARY__', glossary).replace('__N__', str(len(items)))
            .replace('__ITEMS__', json.dumps(items, ensure_ascii=False).replace('</', '<\\/'))
            .replace('__CATS__', json.dumps(cats, ensure_ascii=False).replace('</', '<\\/')))
    out = BASE / 'gold' / 'gabarito-externo.html'
    out.write_text(body, encoding='utf-8')
    os.chmod(out, 0o600)
    print(out)


# --- one-shot evaluation ----------------------------------------------------------------------------------------
def _bootstrap(groups, fn, n=2000):
    rng = random.Random(SEED)
    keys = sorted(groups)
    vals = sorted(fn([i for k in (rng.choice(keys) for _ in keys) for i in groups[k]]) for _ in range(n))
    return round(vals[int(0.025 * n)], 4), round(vals[int(0.975 * n) - 1], 4)


def _view(gold, arms, group_of):
    ids = sorted(gold)
    groups = defaultdict(list)
    for i in ids:
        groups[group_of(i)].append(i)
    acc = lambda a, s: sum(arms[a].get(i) == gold[i] for i in s) / len(s)  # noqa: E731
    res = {'items': len(ids), 'groups': len(groups),
           'arms': {a: {'accuracy': round(acc(a, ids), 4),
                        'macro_f1': round(v1.macro_f1([gold[i] for i in ids], [arms[a].get(i) for i in ids]), 4)}
                    for a in arms},
           'diffs': {f'v3-{o}': {'accuracy': round(acc('v3', ids) - acc(o, ids), 4),
                                 'accuracy_ci': _bootstrap(groups, lambda s, o=o: acc('v3', s) - acc(o, s))}
                     for o in arms if o != 'v3'}}
    return res


def evaluate(external_csv, owner_csvs, shipped):
    import csv as _csv
    # One-shot per held-out (amendment 4): external now, owner gold when its trigger is reached.
    out = OUT / ('owner-test-results.json' if owner_csvs else 'external-test-results.json')
    if out.exists():
        raise SystemExit(f'spent: {out.name} exists')
    from research.intake_judge import Judge as JudgeV1
    from research.intake_judge_v2 import Judge
    freeze = json.loads((OUT / 'FREEZE.json').read_text())
    v3 = Judge.load(BASE / 'pick.json')
    v2j = Judge.load(v2.BASE / 'pick.json')
    j1 = JudgeV1.load(v1.BASE / 'model.json')
    res = {'shipped': shipped, 'views': {}}

    def arms_for(items):
        a = {'v3': {i: v3.predict(r['goal'], r.get('prev_agent'))[0] for i, r in items.items()},
             'v2_pick': {i: v2j.predict(r['goal'], r.get('prev_agent'))[0] for i, r in items.items()},
             'v1': {i: j1.predict(r['goal'])[0] for i, r in items.items()},
             'keyword': {i: v1.keyword_classify(r['goal']) for i, r in items.items()},
             'majority': dict.fromkeys(items, freeze['majority_class'])}
        a['shipped'] = a['v2_pick' if shipped == 'v2' else 'v1']
        return a

    if owner_csvs:
        passes = [v1._read_gold(p) for p in owner_csvs]
        excl = {i for g in passes for i, v in g.items() if v in ('', 'unsure')}
        gold = {i: v for i, v in passes[0].items() if i not in excl and all(g.get(i) == v for g in passes[1:])}
        orecs = v2.records()
        oitems = {i: orecs[i] for i in gold}
        res['views']['owner_primary_agree'] = _view(gold, arms_for(oitems), lambda i: orecs[i]['session_hash'])
        for n, g in enumerate(passes):
            pg = {i: v for i, v in g.items() if v not in ('', 'unsure')}
            res['views'][f'owner_pass{n + 1}'] = _view(pg, arms_for({i: orecs[i] for i in pg}),
                                                       lambda i: orecs[i]['session_hash'])
        ci = res['views']['owner_primary_agree']['diffs']['v3-shipped']['accuracy_ci']
        res['acceptance'] = {'1_owner_non_inferior': ci[0] > -0.03}
        out.write_text(json.dumps(res, indent=1) + '\n')
        print(json.dumps({'acceptance': res['acceptance'], 'owner': res['views']['owner_primary_agree']['arms']}, indent=1))
        return
    # external
    recs, votes = public(), json.loads((BASE / 'gold' / 'votes.json').read_text())
    with open(external_csv, newline='', encoding='utf-8') as fh:
        rows = list(_csv.DictReader(fh))
    final = {r['id']: r['final'] for r in rows if r['final'] not in ('', 'unsure')}
    blind = {r['id']: r['blind'] for r in rows if r['blind'] not in ('', 'unsure')}
    items = {i: recs[i] for i in set(final) | set(blind)}
    arms = arms_for(items)
    arms['opus'] = votes['claude']
    non_teacher = {}
    for i in blind:
        c = Counter([votes['codex'].get(i), votes['gemini'].get(i), blind[i]]).most_common(1)[0]
        if c[1] >= 2:
            non_teacher[i] = c[0]
    agree3 = {i: votes['claude'][i] for i in items if len({votes[v].get(i) for v in votes}) == 1}
    group = lambda i: recs[i]['group']  # noqa: E731
    ext = {'final': final, 'blind': blind, 'codex_gemini_owner_blind_majority': non_teacher, 'all_three_models_agree': agree3}
    for name, gold in ext.items():
        if gold:
            res['views'][f'external_{name}'] = _view(gold, arms, group)
    for src in ('cc_public', 'wildchat'):
        g = {i: v for i, v in final.items() if recs[i]['source'] == src}
        if g:
            res['views'][f'external_final_{src}'] = _view(g, arms, group)
    changed = [i for i in final if i in blind and final[i] != blind[i]]
    res['external_blind_to_final_changes'] = {'n': len(changed), 'toward': {
        v: sum(final[i] == votes[v].get(i) for i in changed) for v in votes}}
    res['voter_pairwise_agreement'] = {f'{a}-{b}': round(sum(votes[a].get(i) == votes[b].get(i) for i in items) / len(items), 3)
                                       for a, b in (('claude', 'codex'), ('claude', 'gemini'), ('codex', 'gemini'))}
    cost = v2._bench(BASE / 'pick.json', [[r['goal'], r.get('prev_agent')] for r in items.values()], 'B')
    med, p90, max_bytes, max_rss = v2.BUDGET['B']
    res['cost'] = cost
    ext_ci = res['views']['external_final']['diffs']['v3-shipped']['accuracy_ci']
    res['acceptance'] = {
        '2_external_superior': ext_ci[0] > 0,
        '2b_external_superior_on_blind': res['views']['external_blind']['diffs']['v3-shipped']['accuracy_ci'][0] > 0,
        '3_cost': (cost['median_ms'] <= med and cost['p90_ms'] <= p90 and cost['peak_rss_mb'] <= max_rss
                   and freeze['pick']['files_bytes'] <= max_bytes)}
    out.write_text(json.dumps(res, indent=1) + '\n')
    print(json.dumps({'acceptance': res['acceptance'], 'external_final': res['views']['external_final']['arms']}, indent=1))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('command', choices=('build', 'teacher', 'train', 'external-draw', 'eval'))
    ap.add_argument('--external')
    ap.add_argument('--owner', nargs='*', default=[])
    ap.add_argument('--shipped', choices=('v1', 'v2'), default='v1')
    a = ap.parse_args(argv)
    if a.command == 'eval':
        evaluate(a.external, a.owner, a.shipped)
    else:
        globals()[a.command.replace('-', '_')]()


if __name__ == '__main__':
    sys.exit(main())
