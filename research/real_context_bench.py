"""Real-context bench v0: harness for the frozen protocol in
research/goal-engine-2026-10-04/real-context-bench-v0/protocol.json.

Phases (private data never leaves PRIVATE; the repo gets aggregate counts only):

    sample  verify the pinned private files, re-derive the frozen 60-id allocation, write
            PRIVATE/dossiers/<id>.json (goal + rendered context)
    run     one arm over every dossier -> PRIVATE/<runs>/<arm>/<id>.json (output, kept/dropped
            LCC block ids, sizes, latency). Remote arms are refused unless --allow-remote, and even
            then no client is wired in v0.
    score   probes + metrics -> PRIVATE/score.json and a counts-only copy next to protocol.json

Run with the pinned interpreter, never -I, from the repo root:

    PYTHONPATH=/Users/Master/.lcc/bench/real-context-v0/lcc-main/src:/Users/Master/Downloads/LCC-judge \\
    HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 /Users/Master/LCC/.venv/bin/python \\
        -m research.real_context_bench {sample | run --arm full|mechanical|specialist | score}

lcc is imported lazily so the probe/score logic is testable with the stdlib alone.
"""
import argparse
import contextlib
import hashlib
import importlib.util
import json
import math
import os
import random
import re
import signal
import socket
import statistics
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
BENCH_DIR = REPO / 'research' / 'goal-engine-2026-10-04' / 'real-context-bench-v0'
PROTOCOL = BENCH_DIR / 'protocol.json'
PRIVATE = Path('/Users/Master/.lcc/bench/real-context-v0')
SPECIALIST_HEAD = REPO / 'models' / 'exp02-specialist-head'
HF_HOME = REPO / 'release-staging' / 'linux-ml' / 'hf'
TIMEOUT_S = 600
LOCAL_ARMS = ('full', 'mechanical', 'specialist')
DIAGNOSTIC = 'specialist_rank_at_mechanical_budget'
MECH_KW = dict(threshold=0.4, min_block_chars=40, max_block_chars=6000, trim_head_chars=300, model='gpt-4.1')


def sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_protocol(path=PROTOCOL):
    path = Path(path)
    want = (path.parent / 'protocol.json.sha256').read_text().split()[0]
    got = sha256_file(path)
    if got != want:
        raise SystemExit(f'protocol.json sha256 {got[:12]} != frozen {want[:12]}: refusing to run')
    return json.loads(path.read_text())


# --- network guard -------------------------------------------------------------------------------
GUARD = {'trips': 0}


class NetworkBlocked(ConnectionRefusedError):
    pass


def _blocked(*args, **kwargs):
    GUARD['trips'] += 1
    raise NetworkBlocked('real-context bench: network is blocked for the whole run')


@contextlib.contextmanager
def network_guard():
    saved = socket.socket.connect, socket.create_connection
    socket.socket.connect, socket.create_connection = _blocked, _blocked
    try:
        yield GUARD
    finally:
        socket.socket.connect, socket.create_connection = saved


# --- sample: allocation + context dossiers --------------------------------------------------------
def allocate(pool, extra, seed, n, per_stratum=4):
    """Frozen allocation: label precedence owner_v1 > pool label (v2 pass / owner v2) > bench labels.

    Eligible: >=1 assistant record before the prompt and confidence != low. 4 per stratum (capped),
    leftover round-robin over alphabetical strata. One Random(seed) instance shuffles each stratum's
    sorted ids in alphabetical stratum order (this reproduces the frozen sample.json exactly).
    """
    strata = defaultdict(list)
    for rid, v in pool.items():
        if 'owner_v1' in v:
            label, conf = v['owner_v1'], v.get('confidence')
        elif 'label' in v:
            label, conf = v['label'], v.get('confidence')
        elif rid in extra:
            label, conf = extra[rid]['label'], extra[rid].get('confidence')
        else:
            continue
        if v.get('ctx_assistant', 0) >= 1 and conf != 'low':
            strata[label].append(rid)
    rng = random.Random(seed)
    order = {}
    for k in sorted(strata):
        ids = sorted(strata[k])
        rng.shuffle(ids)
        order[k] = ids
    chosen = {k: ids[:per_stratum] for k, ids in order.items()}
    left = n - sum(map(len, chosen.values()))
    while left > 0 and any(len(chosen[k]) < len(order[k]) for k in order):
        for k in sorted(order):
            if left and len(chosen[k]) < len(order[k]):
                chosen[k].append(order[k][len(chosen[k])])
                left -= 1
    return [i for k in sorted(order) for i in chosen[k]], {k: len(v) for k, v in sorted(strata.items())}


def claude_text(content):
    """Same extraction as research.import_agent_requests._claude_text (not imported: that module
    puts ~/LCC/src first on sys.path, which would shadow the pinned lcc)."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        if any(isinstance(b, dict) and b.get('type') == 'tool_result' for b in content):
            return None
        parts = [b.get('text', '') for b in content if isinstance(b, dict) and b.get('type') == 'text']
        return '\n'.join(parts) if parts else None
    return None


def context_records(path, uuid):
    """(prompt record, context records oldest-first): walk parentUuid from the prompt's parent until
    None, a missing uuid or a compact_boundary; keep user/assistant; the prompt is excluded."""
    recs = {}
    with open(path, encoding='utf-8', errors='replace') as fh:
        for line in fh:
            try:
                d = json.loads(line)
            except ValueError:
                continue
            if isinstance(d, dict) and d.get('uuid'):
                recs[d['uuid']] = d
    prompt, out, seen = recs[uuid], [], set()
    cur = prompt.get('parentUuid')
    while cur and cur in recs and cur not in seen:
        seen.add(cur)
        r = recs[cur]
        if r.get('type') == 'system' and r.get('subtype') == 'compact_boundary':
            break
        if r.get('type') in ('user', 'assistant'):
            out.append(r)
        cur = r.get('parentUuid')
    return prompt, out[::-1]


def _result_text(content):
    if isinstance(content, str):
        return content
    parts = []
    for p in content or ():
        if isinstance(p, dict) and p.get('type') == 'text':
            parts.append(p.get('text') or '')
        elif isinstance(p, dict) and p.get('type') == 'image':
            parts.append('[image omitted]')
    return '\n'.join(parts)


def render_blocks(records):
    """One block per content block; thinking dropped; m = record index in the context."""
    blocks, names = [], {}

    def add(m, role, kind, content, tool_name=None, tool_use_id=None, is_error=False):
        blocks.append(dict(m=m, role=role, kind=kind, tool_name=tool_name, tool_use_id=tool_use_id,
                           is_error=is_error, content=content))

    for m, r in enumerate(records):
        msg = r.get('message') if isinstance(r.get('message'), dict) else {}
        role = msg.get('role') or r.get('type')
        content = msg.get('content')
        parts = [dict(type='text', text=content)] if isinstance(content, str) else content or []
        for b in parts if isinstance(parts, list) else ():
            t = b.get('type') if isinstance(b, dict) else None
            if t == 'text':
                add(m, role, 'text', b.get('text') or '')
            elif t == 'tool_use':
                names[b.get('id')] = b.get('name')
                add(m, role, 'tool_use', json.dumps(b.get('input'), ensure_ascii=False, sort_keys=True),
                    b.get('name'), b.get('id'))
            elif t == 'tool_result':
                add(m, role, 'tool_result', _result_text(b.get('content')), names.get(b.get('tool_use_id')),
                    b.get('tool_use_id'), bool(b.get('is_error')))
            elif t == 'image':
                add(m, role, 'image', '[image omitted]')
    return blocks


def header(b):
    return f"[m{b['m']:04d} {b['role']} {b['kind']}" + (f" {b['tool_name']}" if b['tool_name'] else '') + ']'


def render(blocks):
    return '\n\n'.join(f"{header(b)}\n{b['content']}" for b in blocks)


def build_dossier(item, redact):
    prompt, records = context_records(item['path'], item['uuid'])
    goal = (claude_text((prompt.get('message') or {}).get('content')) or '').strip()
    rid = hashlib.sha256(f'claude\0{redact(goal)[:1000]}'.encode()).hexdigest()[:16]
    blocks = render_blocks(records)
    return dict(id=item['id'], id_ok=rid == item['id'], category=item['category'],
                label_source=item['label_source'], confidence=item['confidence'],
                session_hash=item['session_hash'], goal=goal, blocks=blocks, text=render(blocks))


def load_request_log(prefix):
    path = PRIVATE / 'rl' / 'lcc' / 'request_log.py'
    spec = importlib.util.spec_from_file_location('bench_request_log', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    if not mod.RULESET_SHA256.startswith(prefix):
        raise SystemExit(f'request_log ruleset {mod.RULESET_SHA256[:12]} != pinned {prefix}')
    return mod


def load_sample(root, proto):
    for name, want in proto['sample']['private_files_sha256'].items():
        if sha256_file(root / name) != want:
            raise SystemExit(f'{name} does not match its pinned sha256: refusing to run')
    return json.loads((root / 'sample.json').read_text())


def sample_phase(root=PRIVATE):
    proto = load_protocol()
    sample = load_sample(root, proto)
    pool = json.loads((root / 'pool.json').read_text())
    extra = {}
    for line in (root / 'labels-claude-extra.jsonl').read_text().splitlines():
        if line.strip():
            d = json.loads(line)
            extra[d['id']] = d
    ids, eligible = allocate(pool, extra, proto['sample']['seed'], proto['sample']['n'])
    if ids != [it['id'] for it in sample['items']] or eligible != proto['sample']['eligible_per_stratum']:
        raise SystemExit('re-derived allocation differs from the frozen sample.json')
    rl = load_request_log(proto['pins']['request_log_ruleset_sha256_prefix'])
    out = root / 'dossiers'
    out.mkdir(exist_ok=True)
    sizes, bad_id, empty = [], 0, 0
    for item in sample['items']:
        d = build_dossier(item, rl.redact)
        bad_id += not d['id_ok']
        empty += not d['blocks']
        sizes.append(sum(len(b['content'].encode()) for b in d['blocks'] if b['kind'] != 'image'))
        (out / f"{d['id']}.json").write_text(json.dumps(d, ensure_ascii=False))
    return dict(dossiers=len(sizes), id_mismatch=bad_id, empty_context=empty,
                visible_bytes=dict(median=statistics.median(sizes), max=max(sizes), sum=sum(sizes)))


# --- probes ---------------------------------------------------------------------------------------
ERROR_RE = re.compile(r'Traceback \(most recent call last\)|\bError\b|\bERROR\b|\bFAILED?\b|\bexit code [1-9]|Exception')
GIT_RE = re.compile(r'\bgit\s+(status|diff|log)\b')
REF_RES = (re.compile(r'https?://\S+'), re.compile(r'[\w.~-]*/[\w.-]+(?:/[\w.-]+)*'),
           re.compile(r'\b[\w-]+\.(?:py|ts|tsx|js|jsx|md|json|toml|ya?ml|sql|css|html|sh|go|rs)\b'))
TASK_TOOLS = {'TodoWrite', 'TaskCreate', 'TaskUpdate', 'ExitPlanMode', 'update_plan'}
EDIT_TOOLS = {'Write', 'Edit', 'MultiEdit', 'NotebookEdit'}


def collapse(s):
    return ' '.join(s.split())


def _latest(blocks, pred):
    return next((b for b in reversed(blocks) if pred(b)), None)


def _bash_command(blocks, tool_use_id):
    b = _latest(blocks, lambda b: b['kind'] == 'tool_use' and b['tool_use_id'] == tool_use_id)
    if not b or b['tool_name'] != 'Bash':
        return ''
    try:
        return str((json.loads(b['content']) or {}).get('command') or '')
    except (ValueError, AttributeError):
        return ''


def probe_targets(name, blocks, goal, min_chars):
    """Texts that must survive for this probe, or None when NOT APPLICABLE."""
    if name == 'NAMED_REFS':
        refs = list(dict.fromkeys(m.group(0) for rx in REF_RES for m in rx.finditer(goal)))
        hits = [_latest(blocks, lambda b, r=r: r in b['content']) for r in refs]
        found = list(dict.fromkeys(b['content'] for b in hits if b))
    else:
        if name == 'ERROR_RESULT' and ERROR_RE.search(goal):
            return None  # pasted error: the goal itself is never compacted
        pred = {
            'LAST_AGENT_TURN': lambda b: b['role'] == 'assistant' and (
                b['kind'] == 'text' or (b['kind'] == 'tool_use' and b['tool_name'] in ('AskUserQuestion', 'ExitPlanMode'))),
            'TASK_STATE': lambda b: b['kind'] == 'tool_use' and b['tool_name'] in TASK_TOOLS,
            'LAST_TOOL_RESULT': lambda b: b['kind'] == 'tool_result',
            'ERROR_RESULT': lambda b: b['kind'] == 'tool_result' and (b['is_error'] or bool(ERROR_RE.search(b['content']))),
            'GIT_STATE': lambda b: b['kind'] == 'tool_result' and bool(GIT_RE.search(_bash_command(blocks, b['tool_use_id']))),
            'LATEST_SUMMARY': lambda b: b['role'] == 'assistant' and b['kind'] == 'text' and len(b['content']) >= 500,
            'LAST_ARTIFACT_EDIT': lambda b: b['kind'] == 'tool_use' and b['tool_name'] in EDIT_TOOLS,
        }[name]
        b = _latest(blocks, pred)
        found = [b['content']] if b else []
    found = [t for t in found if len(collapse(t)) >= min_chars]
    return found or None


def probes_for(category, goal, proto):
    names = list(proto['probes']['per_category'][category])
    if len(goal.split()) < 15:  # short_goal_rule
        names += ['LAST_AGENT_TURN', 'TASK_STATE']
    return list(dict.fromkeys(names))


def score_item(dossier, run, proto):
    """{probe: True|False|None(NA)} and item_pass (None when no probe applies)."""
    out = collapse(run.get('output') or '') if run and run.get('status') == 'ok' else None
    probes = {}
    for name in probes_for(dossier['category'], dossier['goal'], proto):
        targets = probe_targets(name, dossier['blocks'], dossier['goal'], proto['probes']['min_chars'])
        probes[name] = None if targets is None else (out is not None and all(collapse(t) in out for t in targets))
    applicable = [v for v in probes.values() if v is not None]
    return dict(probes=probes, item_pass=all(applicable) if applicable else None)


# --- metrics --------------------------------------------------------------------------------------
def wilson(k, n, z=1.96):
    if not n:
        return None, None
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return round(max(0.0, c - h), 4), round(min(1.0, c + h), 4)


def quantile(xs, q):
    xs = sorted(x for x in xs if x is not None)
    return xs[max(0, math.ceil(q * len(xs)) - 1)] if xs else None


def _rate(k, n):
    lo, hi = wilson(k, n)
    return dict(k=k, n=n, rate=round(k / n, 4) if n else None, wilson95=[lo, hi])


def at_budget(blocks, protected, ranking, budget, count):
    """Keep protected blocks, then ranked blocks until kept tokens reach budget; original order."""
    text = dict(blocks)
    kept = set(protected)
    total = sum(count(text[b]) for b in kept)
    for bid in ranking:
        if total >= budget:
            break
        if bid in text and bid not in kept:
            kept.add(bid)
            total += count(text[bid])
    return '\n\n'.join(t for bid, t in blocks if bid in kept)


def aggregate(dossiers, runs, proto):
    items, arms, failures = [], {}, {}
    per = {arm: [] for arm in runs}
    for d in dossiers:
        row = dict(id=d['id'], category=d['category'], arms={})
        for arm in runs:
            r = runs[arm].get(d['id']) or dict(status='missing')
            s = score_item(d, r, proto)
            row['arms'][arm] = dict(status=r.get('status'), **s)
            per[arm].append((d, r, s))
        items.append(row)
    for arm, rows in per.items():
        scored = [s['item_pass'] for _, _, s in rows if s['item_pass'] is not None]
        probe_vals = [v for _, _, s in rows for v in s['probes'].values() if v is not None]
        ok = lambda r: r.get('status') == 'ok'  # noqa: E731  # a failed arm counts as no reduction
        red = {}
        for unit, i_key, o_key in (('bytes', 'in_bytes', 'out_bytes'), ('tokens', 'in_tokens', 'out_tokens')):
            ins = [r.get(i_key) or 0 for d, r, _ in rows]
            outs = [(r.get(o_key) if ok(r) else r.get(i_key)) or 0 for d, r, _ in rows]
            each = [1 - o / i for i, o in zip(ins, outs) if i]
            red[unit] = dict(pooled=round(1 - sum(outs) / sum(ins), 4) if sum(ins) else None,
                             median_item=round(statistics.median(each), 4) if each else None)
        cats = defaultdict(lambda: [0, 0])
        for d, _, s in rows:
            if s['item_pass'] is not None:
                cats[d['category']][0] += s['item_pass']
                cats[d['category']][1] += 1
        lat = [r.get('latency_ms') for _, r, _ in rows]
        failures[arm] = [dict(id=d['id'], status=r.get('status'), error=r.get('error'))
                         for d, r, _ in rows if not ok(r)]
        arms[arm] = dict(
            items=len(rows), retention_item=_rate(sum(scored), len(scored)),
            retention_probe=_rate(sum(probe_vals), len(probe_vals)),
            reduction_bytes=red['bytes'], reduction_tokens=red['tokens'],
            token_methods=sorted({r.get('token_method') for _, r, _ in rows if r.get('token_method')}),
            latency_ms=dict(median=statistics.median([x for x in lat if x is not None]) if any(x is not None for x in lat) else None,
                            p90=quantile(lat, 0.9)),
            failures=len(failures[arm]), guard_trips=sum(r.get('guard_trips') or 0 for _, r, _ in rows),
            per_category={c: _rate(k, n) for c, (k, n) in sorted(cats.items())})
    probe_counts = defaultdict(lambda: dict(applicable=0, not_applicable=0))
    for row in items:
        first = next(iter(row['arms'].values()), {'probes': {}})
        for name, v in first['probes'].items():
            probe_counts[name]['not_applicable' if v is None else 'applicable'] += 1
    trips = sum(a['guard_trips'] for a in arms.values())
    full = arms.get('full', {}).get('retention_item', {})
    mech = arms.get('mechanical')
    verdict = {}
    for arm, spec in proto['arms'].items():
        if isinstance(spec, dict) and spec['kind'].startswith('learned') and arm in arms and mech:
            a = arms[arm]
            ret_ok = (a['retention_item']['rate'] or 0) >= (mech['retention_item']['rate'] or 0)
            red_ok = (a['reduction_tokens']['pooled'] or 0) > (mech['reduction_tokens']['pooled'] or 0)
            verdict[arm] = dict(retention_ge_mechanical=ret_ok, token_reduction_gt_mechanical=red_ok,
                                zero_guard_trips=trips == 0, wins=ret_ok and red_ok and trips == 0)
    return dict(schema='real-context-bench-score/0.1', protocol_sha256=sha256_file(PROTOCOL),
                n_items=len(dossiers), void=full.get('n', 0) > 0 and full.get('rate') != 1.0,
                guard_trips=trips, arms=arms, probe_counts=dict(probe_counts), verdict=verdict,
                remote_arms={a: dict(enabled=s['enabled'], estimate=s['estimate'])
                             for a, s in proto['arms'].items() if isinstance(s, dict) and 'enabled' in s},
                failures=failures, items=items)


def counts_only(score):
    """Repo copy: no ids, no per-item rows."""
    public = {k: v for k, v in score.items() if k not in ('items', 'failures')}
    public['failure_counts'] = {a: len(f) for a, f in score['failures'].items()}
    return public


# --- run ------------------------------------------------------------------------------------------
def check_arm(arm, proto, allow_remote):
    spec = proto['arms'].get(arm)
    if not isinstance(spec, dict):
        raise SystemExit(f'{arm!r} is not a runnable arm of this protocol')
    if 'remote' in spec['kind'] and not allow_remote:
        raise SystemExit(f"{arm} is a remote arm (enabled={spec.get('enabled')}, est. "
                         f"${spec['estimate']['total_usd_one_pass']} per pass); refusing without --allow-remote")


def check_lcc(proto):
    import lcc
    src = Path(proto['pins']['lcc_worktree']) / 'src'
    if src.resolve() not in Path(lcc.__file__).resolve().parents:
        raise SystemExit(f'lcc imported from {lcc.__file__}, not the pinned worktree')
    tree = lambda rev: subprocess.run(  # noqa: E731
        ['git', '-C', proto['pins']['lcc_worktree'], 'rev-parse', f'{rev}^{{tree}}'],
        capture_output=True, text=True, check=True).stdout.strip()
    if tree('HEAD') != tree(proto['pins']['lcc_commit']):
        raise SystemExit('lcc worktree tree differs from the pinned lcc_commit')


def lcc_count(text):
    from lcc.token_budget.counters import count_tokens
    c = count_tokens(text, 'gpt-4.1')
    return c.value, f'{c.method.value}:{c.counter}'


def _report(res):
    rep = res.report
    keep = ('provider_used', 'degraded', 'degradation_reason', 'semantic_guarantee', 'calls', 'compilation_ms',
            'tokens_before', 'tokens_after', 'token_count_method', 'blocks_total', 'blocks_protected',
            'blocks_dropped', 'blocks_trimmed', 'reduction_ratio')
    out = {k: getattr(rep, k) for k in keep}
    out['report_latency_ms'] = rep.latency_ms
    out['decisions'] = [dict(id=d.id, decision=d.decision, source=d.source, score=d.score, chars=d.chars,
                             chars_after=d.chars_after) for d in rep.decisions]
    for kind in ('keep', 'trim', 'drop'):
        out[f'{kind}_ids'] = [d.id for d in rep.decisions if d.decision == kind]
    if rep.specialist_ranking:
        sr = rep.specialist_ranking
        out['specialist_ranking'] = dict(ranking=sr.get('ranking'), model=sr.get('model'), items=[
            {k: i.get(k) for k in ('id', 'status', 'logit', 'actual_tokens', 'reason', 'truncated')}
            for i in sr.get('items') or ()])
    return out


def make_runner(arm):
    """(runner(text, goal) -> (output, extra), model_load_ms)."""
    if arm == 'full':
        return (lambda text, goal: (text, {})), None
    from lcc.relevance import RelevanceCompactionRequest, compact_context
    if arm == 'mechanical':
        def run(text, goal):
            res = compact_context(RelevanceCompactionRequest(text=text, question=goal, provider='mechanical', **MECH_KW))
            return res.compacted_text, _report(res)
        return run, None
    if arm == 'specialist':
        from lcc_engine import ContextEngine
        t0 = time.perf_counter()
        engine = ContextEngine(str(SPECIALIST_HEAD), device='cpu', max_len=512)
        engine.rank_context('warm up', [dict(id='w', text='load the model')])  # weights load lazily
        load_ms = round((time.perf_counter() - t0) * 1000)

        def run(text, goal):
            res = compact_context(RelevanceCompactionRequest(text=text, question=goal, provider='specialist',
                                                             client=engine, **MECH_KW))
            return res.compacted_text, _report(res)
        return run, load_ms
    raise SystemExit(f'{arm}: remote arms need an explicit injected client; none is wired in v0')


class ItemTimeout(Exception):
    pass


def _alarm(signum, frame):
    raise ItemTimeout()


def run_item(arm, dossier, runner, count, timeout=TIMEOUT_S):
    text, goal = dossier['text'], dossier['goal']
    trips, status, error, out, extra = GUARD['trips'], 'ok', None, None, {}
    old = signal.signal(signal.SIGALRM, _alarm)
    signal.alarm(timeout)
    t0 = time.perf_counter()
    try:
        out, extra = runner(text, goal)
    except ItemTimeout:
        status, error = 'timeout', f'> {timeout} s'
    except Exception as exc:  # an arm error is a fail on every applicable probe, and is reported
        status, error = 'error', f'{type(exc).__name__}: {exc}'[:300]
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old)
    latency = round((time.perf_counter() - t0) * 1000)
    in_tok, method = count(text)
    out_tok = count(out)[0] if out is not None else None
    return dict(id=dossier['id'], arm=arm, status=status, error=error, latency_ms=latency,
                in_bytes=len(text.encode()), out_bytes=len(out.encode()) if out is not None else None,
                in_tokens=in_tok, out_tokens=out_tok, token_method=method,
                guard_trips=GUARD['trips'] - trips, output=out, **extra)


def run_phase(arm, root=PRIVATE, runs='runs', ids=None, allow_remote=False):
    proto = load_protocol()
    check_arm(arm, proto, allow_remote)
    sample = load_sample(root, proto)
    os.environ.update(proto['privacy']['env'])
    if arm == 'specialist':
        os.environ['HF_HOME'] = str(HF_HOME)
    check_lcc(proto)
    out = root / runs / arm
    out.mkdir(parents=True, exist_ok=True)
    todo = [it['id'] for it in sample['items'] if not ids or it['id'] in ids]
    with network_guard():
        runner, load_ms = make_runner(arm)
        if load_ms is not None:
            (out / '_model_load.json').write_text(json.dumps(dict(model_load_ms=load_ms)))
        counts = defaultdict(int)
        for rid in todo:
            d = json.loads((root / 'dossiers' / f'{rid}.json').read_text())
            rec = run_item(arm, d, runner, lcc_count)
            counts[rec['status']] += 1
            (out / f'{rid}.json').write_text(json.dumps(rec, ensure_ascii=False))
    return dict(arm=arm, items=len(todo), status=dict(counts), guard_trips=GUARD['trips'], model_load_ms=load_ms)


# --- score ----------------------------------------------------------------------------------------
def score_phase(root=PRIVATE, runs='runs', public=True):
    proto = load_protocol()
    sample = load_sample(root, proto)
    dossiers = [json.loads((root / 'dossiers' / f"{it['id']}.json").read_text()) for it in sample['items']]
    recs = {arm: {} for arm in LOCAL_ARMS}
    for arm in LOCAL_ARMS:
        for d in dossiers:
            p = root / runs / arm / f"{d['id']}.json"
            if p.exists():
                recs[arm][d['id']] = json.loads(p.read_text())
    recs[DIAGNOSTIC] = diagnostic_runs(dossiers, recs['mechanical'], recs['specialist'])
    score = aggregate(dossiers, recs, proto)
    score['diagnostic_arms'] = [DIAGNOSTIC]
    load = root / runs / 'specialist' / '_model_load.json'
    score['specialist_model_load_ms'] = json.loads(load.read_text())['model_load_ms'] if load.exists() else None
    name = 'score.json' if runs == 'runs' else f'score-{runs}.json'
    (root / name).write_text(json.dumps(score, ensure_ascii=False, indent=1))
    if public and runs == 'runs':
        (BENCH_DIR / 'score.json').write_text(json.dumps(counts_only(score), indent=1) + '\n')
    return counts_only(score)


def diagnostic_runs(dossiers, mech, spec):
    from lcc.relevance.blocks import split_blocks
    count = lambda s: lcc_count(s)[0]  # noqa: E731
    out = {}
    for d in dossiers:
        m, s = mech.get(d['id']), spec.get(d['id'])
        if not (m and s and m['status'] == s['status'] == 'ok' and s.get('specialist_ranking')):
            out[d['id']] = dict(status='error', error='mechanical or specialist run missing/failed')
            continue
        blocks = [(b.id, b.text) for b in split_blocks(d['text'], min_block_chars=MECH_KW['min_block_chars'],
                                                        max_block_chars=MECH_KW['max_block_chars'])]
        protected = {x['id'] for x in s['decisions'] if x['source'] == 'protected'}
        text = at_budget(blocks, protected, s['specialist_ranking']['ranking'], m['out_tokens'], count)
        out[d['id']] = dict(status='ok', output=text, in_bytes=s['in_bytes'], out_bytes=len(text.encode()),
                            in_tokens=s['in_tokens'], out_tokens=count(text), token_method=s['token_method'],
                            latency_ms=None, guard_trips=0)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    sub = ap.add_subparsers(dest='phase', required=True)
    sub.add_parser('sample')
    r = sub.add_parser('run')
    r.add_argument('--arm', required=True)
    r.add_argument('--ids', help='comma-separated subset (smoke runs)')
    r.add_argument('--allow-remote', action='store_true')
    r.add_argument('--runs', default='runs', help='run dir name under the private root')
    s = sub.add_parser('score')
    s.add_argument('--runs', default='runs')
    s.add_argument('--no-public', action='store_true', help='do not write the repo counts-only copy')
    a = ap.parse_args(argv)
    if a.phase == 'sample':
        res = sample_phase()
    elif a.phase == 'run':
        res = run_phase(a.arm, runs=a.runs, ids=set(a.ids.split(',')) if a.ids else None,
                        allow_remote=a.allow_remote)
    else:
        res = score_phase(runs=a.runs, public=not a.no_public)
    json.dump(res, sys.stdout, indent=1, default=str)
    print()


if __name__ == '__main__':
    main()
