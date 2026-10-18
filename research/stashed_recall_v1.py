"""Stashed recall v1 (protocol: research/goal-engine-2026-10-04/stashed-recall-v1/PROTOCOL.md).

Reuses probe-eval-v1's frozen items and probes read-only (its ROOT, never written) and its frozen helpers
(gold scoring, judge text R, cluster bootstrap). Writes only under ~/.lcc/bench/stashed-recall-v1.
Model calls: subscription `claude -p` / `agy` only, hard cap 900 calls (pilot included), never --dangerously*.

    PYTHONPATH=/Users/Master/.lcc/bench/lcc-4719fde/src:/Users/Master/Downloads/LCC-judge \\
    HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 /Users/Master/LCC/.venv/bin/python \\
        -m research.stashed_recall_v1 {toolcheck|compact|locate|run --arm A|judge|agree|score} --set pilot|D
"""
import argparse
import hashlib
import json
import os
import random
import re
import statistics
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict
from pathlib import Path

from research import next_action_labels as nal
from research import probe_eval_v1 as pev
from research import real_context_bench as rcb

REPO = rcb.REPO
PROTOCOL = REPO / 'research' / 'goal-engine-2026-10-04' / 'stashed-recall-v1' / 'PROTOCOL.md'
PUBLIC = PROTOCOL.parent
ROOT = Path('/Users/Master/.lcc/bench/stashed-recall-v1')
SHIM = Path(__file__).with_name('recall_mcp_shim.py')
PIN = dict(worktree='/Users/Master/.lcc/bench/lcc-4719fde', commit='4719fde')
SEED = 20261017
CALL_CAP = 900
TIMEOUT_S = 1200
ARMS = ('full_t', 'stashed_t', 'stashed_0')
TOOL_ARMS = ('full_t', 'stashed_t')
QT_SHA = '9331ffd9330871359bf60cdb75252f1def6bac9547f3dcbc64a38b368465de38'  # frozen by Amendment 3
NOTE_RE = re.compile(r'\[removed: (\d+) tokens · lcc recall ([0-9a-f]{12})\]')
MASK_EXTRA = re.compile(r'\[removed: \d+ tokens · lcc recall [0-9a-f]{12}\]|\brecall(?:ed|ing|s)?\b', re.I)
SYSTEM_TOOL = ('You answer questions about a coding session from the context you are given. '
               'You have one tool, recall.')
SYSTEM_NOTOOL = 'You answer questions about a coding session from the context you are given. You have no tools.'


# --- io --------------------------------------------------------------------------------------------------
def sdir(s, *parts):
    p = ROOT.joinpath(s, *parts)
    p.mkdir(parents=True, exist_ok=True)
    return p


def ids_of(s):
    return pev.built_ids(s)  # probe-eval-v1's built items (read-only)


def probes_of(s, iid):
    return pev.rj(pev.ROOT / s / 'probes' / f'{iid}.json')['probes']


def qt_text():
    md = PROTOCOL.read_text()
    m = re.search(r'^### Q-T — [^\n]*\n\n```\n(.*?\n)```', md, re.M | re.S)
    if not m:
        raise SystemExit('Q-T missing from PROTOCOL.md')
    if QT_SHA is not None and hashlib.sha256(m.group(1).encode()).hexdigest() != QT_SHA:
        raise SystemExit('frozen text Q-T changed: refusing to run')
    return m.group(1).rstrip('\n')


def own_frozen():
    """Every `research/...` / `tests/...` | sha256 pair in this protocol's tables must match."""
    bad = []
    for row in PROTOCOL.read_text().splitlines():
        if row.startswith('|'):
            for p, h in zip(re.findall(r'`((?:research|tests)/[^`]+)`', row), re.findall(r'`([0-9a-f]{64})`', row)):
                f = REPO / p
                if not f.exists() or hashlib.sha256(f.read_bytes()).hexdigest() != h:
                    bad.append(p)
    if bad:
        raise SystemExit(f'frozen files changed: {bad}: refusing to run')


def check_frozen(s):
    if s != 'pilot':
        pev.frozen_files()  # probe-eval-v1's harness, probes builder and private manifests unchanged
        own_frozen()
        if QT_SHA is None:
            raise SystemExit('harness not frozen yet (QT_SHA unset): only the pilot may run')


# --- model calls -----------------------------------------------------------------------------------------
def n_calls():
    p = ROOT / 'calls.jsonl'
    return sum(1 for _ in p.open()) if p.exists() else 0


def log_call(**kw):
    ROOT.mkdir(parents=True, exist_ok=True)
    with (ROOT / 'calls.jsonl').open('a') as f:
        f.write(json.dumps(kw) + '\n')


def mcp_config(stash, log):
    env = {'LCC_STASH_DIR': str(stash), 'RECALL_LOG': str(log), 'PYTHONPATH': f"{PIN['worktree']}/src",
           'HF_HUB_OFFLINE': '1', 'TRANSFORMERS_OFFLINE': '1'}
    return {'mcpServers': {'stash': {'type': 'stdio', 'command': sys.executable, 'args': [str(SHIM)],
                                     'env': env}}}


def cli(role, model, system, prompt, schema, key, effort=None, tool=None):
    """One subscription call -> parsed JSON object holding `key`. tool=(stash_dir, log_path) enables recall."""
    if n_calls() >= CALL_CAP:
        raise SystemExit(f'call cap {CALL_CAP} reached')
    with tempfile.TemporaryDirectory(prefix='stashed-recall-cwd-') as cwd:
        if model == 'gemini':
            argv = ['agy', '--model', 'Gemini 3.8 Flash (High)', '--mode', 'plan', '--sandbox',
                    '--print-timeout', f'{TIMEOUT_S}s', '--output-format', 'json', '--json-schema',
                    json.dumps(schema), '--disable-slash-commands',
                    f'--print={system}\n\n{prompt}\n\nDo not use any tools. Reply with the JSON object only.']
            stdin = None
        else:
            argv = ['claude', '-p', '--model', model, '--tools', '', '--output-format', 'json',
                    '--json-schema', json.dumps(schema), '--no-session-persistence', '--disable-slash-commands',
                    '--strict-mcp-config', '--permission-prompts', 'none', '--setting-sources', '',
                    '--exclude-dynamic-system-prompt-sections', '--system-prompt', system]
            if tool:
                cfg = Path(cwd) / 'mcp.json'
                cfg.write_text(json.dumps(mcp_config(*tool)))
                argv += ['--mcp-config', str(cfg), '--allowedTools', 'mcp__stash__recall']
            if effort:
                argv += ['--effort', effort]
            stdin = prompt
        assert not any('dangerously' in a for a in argv), 'never skip permissions'
        try:
            r = subprocess.run(argv, input=stdin, capture_output=True, text=True, cwd=cwd, timeout=TIMEOUT_S + 60,
                               env={k: v for k, v in os.environ.items() if not k.startswith(('PYTHON', 'ANTHROPIC_'))})
            out, err, rc = r.stdout, r.stderr, r.returncode
        except subprocess.TimeoutExpired:
            out, err, rc = '', 'timeout', -9
    env = pev._loads(out)
    is_error = rc != 0 or (isinstance(env, dict) and env.get('is_error') is True)
    obj = None if is_error else pev._find_obj(env, key)
    turns = env.get('num_turns') if isinstance(env, dict) else None
    log_call(role=role, model=model, key=key, ok=obj is not None, rc=rc, turns=turns)
    if obj is None:
        (ROOT / 'failures').mkdir(parents=True, exist_ok=True)
        pev.wj(ROOT / 'failures' / f'{role}-{n_calls():05d}.json', dict(rc=rc, stdout=out[-20000:], stderr=err[-5000:]))
        msg = f'{out[-2000:]}\n{err[-2000:]}' if is_error else ''
        if pev.LIMIT_RE.search(msg):
            raise pev.LimitHit(pev.LIMIT_RE.search(msg).group(0))
        raise RuntimeError(f'{role}: no {key} (exit {rc})')
    if isinstance(env, dict):  # envelope facts: tool availability and real cost, never used as an outcome
        usage = env.get('usage') or {}
        obj = dict(obj, _turns=turns, _denials=len(env.get('permission_denials') or []),
                   _in_tokens=sum(usage.get(k) or 0 for k in ('input_tokens', 'cache_creation_input_tokens',
                                                              'cache_read_input_tokens')),
                   _out_tokens=usage.get('output_tokens'))
    return obj


def cached_call(path, fn, before_attempt=None):
    if path.exists():
        return pev.rj(path)
    for attempt in (1, 2):
        if before_attempt:
            before_attempt()
        try:
            res = dict(ok=True, **fn())
            break
        except RuntimeError as e:
            if isinstance(e, pev.LimitHit):
                raise
            res = dict(ok=False, error=str(e)[:300], attempts=attempt)
    pev.wj(path, res)
    return res


# --- V4: the tool path works end to end -----------------------------------------------------------------
def toolcheck(s):
    secret = f'stashed-recall-toolcheck-{SEED}-' + hashlib.sha256(str(SEED).encode()).hexdigest()[:16]
    stash = sdir(s, 'toolcheck', 'stash')
    os.environ['LCC_STASH_DIR'] = str(stash)
    from lcc.relevance.transcript_stash import put
    digest = put(secret + '\n')
    log = sdir(s, 'toolcheck') / 'recall.jsonl'
    log.unlink(missing_ok=True)
    prompt = (f'An old tool result was removed: [removed: 9 tokens · lcc recall {digest[:12]}]\n'
              'Use the recall tool on that id and return its exact text.\n'
              'Return JSON: {"answers": {"1": "<the recalled text>"}}.')
    res = cli('toolcheck', 'claude-sonnet-5-5', SYSTEM_TOOL, prompt, pev.ANSWER_SCHEMA, 'answers', 'medium',
              tool=(stash, log))
    calls = [json.loads(x) for x in log.read_text().splitlines()] if log.exists() else []
    ok = secret in json.dumps(res) and any(c.get('ok') for c in calls)
    out = dict(v4_pass=ok, recall_calls=len(calls), turns=res.get('_turns'))
    pev.wj(sdir(s) / 'toolcheck.json', out)
    return out


# --- compact (stashed at the pin) ------------------------------------------------------------------------
def independent_stash_check(blocks, out_texts, stash):
    """Every pointer names the sha256 of the exact original bytes, and that blob hashes to its name. No lcc code."""
    orig = {b['tool_use_id']: b['content'] for b in blocks if b['kind'] == 'tool_result'}
    bad = []
    for tid, text in out_texts.items():
        if text == orig.get(tid):
            continue
        m = NOTE_RE.fullmatch(text or '')
        if not m:
            continue
        digest = hashlib.sha256(orig[tid].encode('utf-8')).hexdigest()
        blob = Path(stash) / digest
        if not digest.startswith(m.group(2)):
            bad.append(dict(id=tid, why='sha_mismatch'))
        elif not blob.is_file() or hashlib.sha256(blob.read_bytes()).hexdigest() != digest:
            bad.append(dict(id=tid, why='blob_missing_or_corrupt'))
    return bad


def compact_item(it, stash):
    from lcc.relevance import TranscriptCompactionRequest, compact_transcript, messages_to_payload
    from lcc.relevance.transcript_stash import verify_stashed
    from research import real_context_bench_v02 as v02
    from research.lossless_dedup_measure import independent_check as dedupe_check
    os.environ['LCC_STASH_DIR'] = str(stash)
    payload = v02.rules_payload(it['blocks'])
    try:
        r = compact_transcript(TranscriptCompactionRequest(payload=payload, question=it['goal'], provider='rules',
                                                           rules_mode='stashed'))
    except Exception as e:  # noqa: BLE001 -- counted, never hidden
        return dict(ok=False, error=f'{type(e).__name__}: {e}'[:300])
    text = rcb.apply_transcript(it['blocks'], r.decisions, r.messages)
    texts = {x.id: x.text for m in r.messages for x in m.tool_results}
    viol = verify_stashed(payload, messages_to_payload(r.messages))
    indep = (independent_stash_check(it['blocks'], texts, stash)
             + dedupe_check(it['blocks'], r.decisions, text))
    bad = bool(viol or indep or r.report['lossless_violations'])
    stashed = {d['stash']['sha256']: d['id'] for d in r.decisions if d.get('decision') == 'replace' and 'stash' in d}
    return dict(ok=not bad, text=text, stashed=stashed,
                stashed_tokens=sum(d['stash']['tokens'] for d in r.decisions if 'stash' in d),
                violations=len(viol), independent=len(indep), degraded=bool(r.report['degraded']),
                error='verification violation' if bad else None)


def compact(s):
    from research import real_context_bench_v02 as v02
    v02.check_lcc_rules(dict(worktree=PIN['worktree'], commit=subprocess.run(
        ['git', '-C', PIN['worktree'], 'rev-parse', PIN['commit']], capture_output=True, text=True,
        check=True).stdout.strip()))
    os.environ.update(rcb.load_protocol(REPO / 'research' / 'goal-engine-2026-10-04' / 'real-context-bench-v0.5'
                                        / 'protocol.json')['privacy']['env'])
    c = Counter()
    with rcb.network_guard():
        for iid in ids_of(s):
            out = sdir(s, 'arms', 'stashed') / f'{iid}.json'
            if out.exists():
                c['cached'] += 1
                continue
            res = compact_item(pev.item(s, iid), sdir(s, 'stash', iid))
            if res.get('ok'):
                res['tokens'] = rcb.lcc_count(res['text'])[0]
            pev.wj(out, res)
            c['ok' if res.get('ok') else 'failed'] += 1
    return dict(c, guard_trips=rcb.GUARD['trips'])


# --- gold location ---------------------------------------------------------------------------------------
def gold_features(p, it):
    """[(label, [variant strings])] of one probe: any variant found counts as the feature found."""
    if p['type'] == 'artifact':
        return [(g[0], list(g)) for g in p['gold']]
    if p['type'] == 'recall':
        return [(p['gold'], [p['gold']])]
    if p['type'] == 'decision':
        return [(p['quote'], [p['quote']])] if p.get('quote') else []
    cont = p['gold'] if isinstance(p['gold'], dict) else {}
    t = cont.get('target')
    return [(t, list(nal._path_keys(t) or [t]) if cont.get('target_kind') == 'path' else [t])] if t else []


def where(variants, view, blobs):
    """in_view | stash_only (with the blob shas holding it) | neither."""
    vs = [nal.collapse(v) for v in variants if v]
    if any(v and v in view for v in vs):
        return 'in_view', []
    hits = sorted(sha for sha, txt in blobs.items() if any(v and v in txt for v in vs))
    return ('stash_only', hits) if hits else ('neither', [])


def locate_item(s, iid):
    it = pev.item(s, iid)
    arm = pev.rj(ROOT / s / 'arms' / 'stashed' / f'{iid}.json')
    if not arm.get('ok'):
        return None
    view = nal.collapse(NOTE_RE.sub(' ', arm['text']))
    stash = ROOT / s / 'stash' / iid
    blobs = {sha: nal.collapse((stash / sha).read_text()) for sha in arm['stashed']}
    out = []
    for n, p in enumerate(probes_of(s, iid), 1):
        feats = [(lab, *where(vs, view, blobs)) for lab, vs in gold_features(p, it)]
        locs = [f[1] for f in feats]
        out.append(dict(n=n, type=p['type'], features=[dict(loc=loc, blobs=b) for _, loc, b in feats],
                        stash_dependent=bool(locs) and 'in_view' not in locs and 'stash_only' in locs))
    return out


def locate(s):
    c = Counter()
    for iid in ids_of(s):
        loc = locate_item(s, iid)
        if loc is None:
            c['arm_failed'] += 1
            continue
        pev.wj(sdir(s, 'locations') / f'{iid}.json', loc)
        for p in loc:
            c[f"{p['type']}:{'stash_dependent' if p['stash_dependent'] else 'other'}"] += 1
            for f in p['features']:
                c[f"feature:{f['loc']}"] += 1
    rec = dict(set=s, items=len(ids_of(s)), counts=dict(sorted(c.items())))
    if s != 'pilot':
        pev.wj(PUBLIC / 'location-receipt.json', rec)
    return rec


# --- stash probes (Amendment 2) -------------------------------------------------------------------------
STASH_KINDS = ('hex', 'num', 'ident', 'quoted')
STASH_SEED = 20261018


def stash_candidates(blobs, view, goal, seed=STASH_SEED):
    """[(kind, value, [shas])]: features of stashed blobs found nowhere in view (C' outside markers) nor in P,
    in kind rank order, shuffled within kind by Random(seed) over sorted values."""
    rng = random.Random(seed)
    g = nal.collapse(goal or '')
    out = []
    for kind in STASH_KINDS:
        holders = defaultdict(set)
        for sha, txt in blobs.items():
            for k, v in nal.features(txt):
                if k == kind:
                    holders[v].add(sha)
        vals = sorted(v for v in holders if nal.collapse(v) not in view and nal.collapse(v) not in g)
        rng.shuffle(vals)
        out += [(kind, v, sorted(holders[v])) for v in vals]
    return out


def stash_probe_path(s, iid):
    return ROOT / s / 'stash-probes' / f'{iid}.json'


def stashprobes(s):
    check_frozen(s)
    G = pev.frozen_texts()['G']
    c = Counter()
    for iid in ids_of(s):
        out = stash_probe_path(s, iid)
        if out.exists():
            c['cached'] += 1
            continue
        arm = pev.rj(ROOT / s / 'arms' / 'stashed' / f'{iid}.json')
        if not arm.get('ok'):
            c['arm_failed'] += 1
            continue
        it = pev.item(s, iid)
        stash = ROOT / s / 'stash' / iid
        blobs = {sha: (stash / sha).read_text() for sha in arm['stashed']}
        view = nal.collapse(NOTE_RE.sub(' ', arm['text']))
        cands = stash_candidates(blobs, view, it['goal'])
        probe, tries = None, 0
        for kind, value, shas in cands[:2]:
            tries += 1
            prompt = json.dumps(dict(recall_target=value, recall_excerpts=pev.recall_excerpts(it, value),
                                     earlier_context_excerpt='', next_request=it['goal'],
                                     what_the_agent_did_next=''), ensure_ascii=False)
            res = cached_call(sdir(s, 'gen-stash') / f'{iid}-{tries}.json',
                              lambda: cli('stash-generator', 'claude-opus-5-5', G, prompt, pev.GEN_SCHEMA, 'recall',
                                          'high'))
            if not res['ok']:
                c['generator_failed'] += 1
                break
            q = (res.get('recall') or {}).get('question') or ''
            if q and not pev.leaks(q, [value]):
                probe = dict(type='stash', question=q, gold=value, kind=kind, blobs=shas)
                break
        sdir(s, 'stash-probes')
        pev.wj(out, dict(item_id=iid, probe=probe, candidates=len(cands), tries=tries))
        c['probe' if probe else ('no_candidate' if not cands else 'dropped')] += 1
    if s != 'pilot':
        files = sorted((ROOT / s / 'stash-probes').glob('*.json'))
        h = hashlib.sha256(b''.join(f.read_bytes() for f in files)).hexdigest()
        pev.wj(PUBLIC / 'stash-probe-receipt.json', dict(set=s, files=len(files), sha256=h, counts=dict(c)))
    return dict(c)


def stash_probe(s, iid):
    p = stash_probe_path(s, iid)
    return pev.rj(p).get('probe') if p.exists() else None


# --- answers ---------------------------------------------------------------------------------------------
def answer(s, name):
    check_frozen(s)
    Q = pev.frozen_texts()['Q'] if name == 'stashed_0' else qt_text()
    c = Counter()
    for iid in ids_of(s):
        ps = probes_of(s, iid)
        src = pev.rj(ROOT / s / 'arms' / 'stashed' / f'{iid}.json')
        path = sdir(s, 'answers', name) / f'{iid}.json'
        if not src.get('ok') or not ps:  # a stashed void drops the item from every arm (paired)
            if not path.exists():
                pev.wj(path, dict(ok=False, error='stashed arm failed' if not src.get('ok') else 'no probes'))
            c['skipped'] += 1
            continue
        it = pev.item(s, iid)
        sp = stash_probe(s, iid)
        ps = ps + ([sp] if sp else [])
        ctx = it['text'] if name == 'full_t' else src['text']
        prompt = pev.answer_prompt(ctx, it['goal'], ps, dict(Q=Q))
        tool = None
        if name in TOOL_ARMS:
            stash = sdir(s, 'stash', iid) if name == 'stashed_t' else sdir(s, 'empty', iid)
            tool = (stash, sdir(s, 'recall-log', name) / f'{iid}.jsonl')
        reset = (lambda t=tool: t[1].unlink(missing_ok=True)) if tool else None
        res = cached_call(path, lambda: cli('answerer', 'claude-sonnet-5-5',
                                            SYSTEM_TOOL if tool else SYSTEM_NOTOOL, prompt, pev.ANSWER_SCHEMA,
                                            'answers', 'medium', tool=tool), before_attempt=reset)
        c['ok' if res['ok'] else 'failed'] += 1
    return dict(c)


# --- judge -----------------------------------------------------------------------------------------------
def mask(text):
    return pev.mask(MASK_EXTRA.sub('[masked]', text or ''))


def judge_records(s, iid):
    ps = probes_of(s, iid)
    recs = []
    for name in ARMS:
        a = pev.rj(ROOT / s / 'answers' / name / f'{iid}.json')
        if not a.get('ok'):
            continue
        for n, p in enumerate(ps, 1):
            recs.append((name, n - 1, dict(question=p['question'], reference=pev.reference(p),
                                           quote=p.get('quote', ''), answer=mask(a['answers'].get(str(n), '')))))
    random.Random(SEED).shuffle(recs)
    return [(f'r{k:02d}', name, pi, rec) for k, (name, pi, rec) in enumerate(recs, 1)]


def judge(s, model='claude-opus-5-5', sub='judge', sample=None):
    check_frozen(s)
    R = pev.frozen_texts()['R']
    c = Counter()
    for iid in ids_of(s):
        if sample is not None and iid not in sample:
            continue
        if not all((ROOT / s / 'answers' / a / f'{iid}.json').exists() for a in ARMS):
            c['not_answered'] += 1
            continue
        recs = judge_records(s, iid)
        if not recs:
            continue
        path = sdir(s, sub) / f'{iid}.json'
        res = cached_call(path, lambda: cli(sub, model, R, pev.judge_prompt(recs), pev.JUDGE_SCHEMA, 'scores',
                                            'high' if model != 'gemini' else None))
        if res['ok'] and 'key' not in res:
            res['key'] = {rid: [name, pi] for rid, name, pi, _ in recs}
            pev.wj(path, res)
        c['ok' if res['ok'] else 'failed'] += 1
    return dict(c)


def agree(s):
    ids = ids_of(s)
    sample = set(random.Random(SEED).sample(ids, max(1, round(len(ids) * 0.10))))
    return judge(s, model='gemini', sub='judge-gemini', sample=sample)


# --- score -----------------------------------------------------------------------------------------------
def recall_log(s, name, iid):
    p = ROOT / s / 'recall-log' / name / f'{iid}.jsonl'
    return [json.loads(x) for x in p.read_text().splitlines()] if p.exists() else []


def behaviour(s, iid, arm, loc, extra_blobs=()):
    """R1-R6 inputs for one item of stashed_t."""
    log = recall_log(s, 'stashed_t', iid)
    ok = [r for r in log if r.get('ok')]
    got = {sha for r in ok for sha in arm['stashed'] if sha.startswith(str(r['id']))}
    gold_blobs = {b for p in loc for f in p['features'] for b in f['blobs']} | set(extra_blobs)
    dep = [p for p in loc if p['stash_dependent']]
    needed_hit = [any(set(f['blobs']) & got for f in p['features']) for p in dep]
    return dict(calls=len(log), ok_calls=len(ok), cap_hits=sum(r.get('error') == 'cap' for r in log),
                errors=sum(not r.get('ok') for r in log),
                useful_calls=sum(any(sha.startswith(str(r['id'])) for sha in gold_blobs) for r in ok),
                recalled_tokens=sum(r.get('tokens') or 0 for r in ok), stashed_tokens=arm['stashed_tokens'],
                dependent=len(dep), needed_hit=sum(needed_hit))


def item_scores(s, iid):
    it = pev.item(s, iid)
    ps = probes_of(s, iid)
    loc = pev.rj(ROOT / s / 'locations' / f'{iid}.json')
    arm = pev.rj(ROOT / s / 'arms' / 'stashed' / f'{iid}.json')
    out = {}
    for name in ARMS:
        a = pev.rj(ROOT / s / 'answers' / name / f'{iid}.json')
        if not a.get('ok'):
            out[name] = None
            continue
        r = dict(tokens=it['tokens'] if name == 'full_t' else arm['tokens'], dep={})
        halluc = []
        for n, p in enumerate(ps, 1):
            ans = a['answers'].get(str(n), '')
            halluc += pev.hallucinated_paths(ans, it['text'], it['goal'])
            if p['type'] == 'artifact':
                v = r['artifact_recall'] = pev.path_recall(p['gold'], ans)
            elif p['type'] == 'recall':
                v = r['recall_exact'] = pev.exact(p['gold'], ans)
            else:
                v = None
            if loc[n - 1]['stash_dependent'] and v is not None:
                r['dep'][p['type']] = float(v)
        r['hallucinated_paths'] = len(set(halluc))
        sp = stash_probe(s, iid)
        if sp and str(len(ps) + 1) in a['answers']:  # an answer without that number was never asked it
            r['stash_exact'] = float(pev.exact(sp['gold'], a['answers'][str(len(ps) + 1)]))
        out[name] = r
    if out.get('stashed_t') is not None:
        sp = stash_probe(s, iid)
        out['stashed_t']['behaviour'] = b = behaviour(s, iid, arm, loc, sp['blobs'] if sp else ())
        if sp and 'stash_exact' in out['stashed_t']:
            got = {str(r['id']) for r in recall_log(s, 'stashed_t', iid) if r.get('ok')}
            b['stash_probe_hit'] = any(sha.startswith(x) for sha in sp['blobs'] for x in got)
    if out.get('full_t') is not None:
        out['full_t']['false_recalls'] = len(recall_log(s, 'full_t', iid))
    jp = ROOT / s / 'judge' / f'{iid}.json'
    if jp.exists() and pev.rj(jp).get('ok'):
        j = pev.rj(jp)
        for rid, (name, pi) in j['key'].items():
            sc = j['scores'].get(rid)
            if out.get(name) is not None and sc:
                out[name].setdefault('judge', {})[ps[pi]['type']] = {d: sc[d] for d in pev.DIMS}
    return it['group'], out


def boot(rows, a, b, key, level=0.95):
    d = [(o[a][key] - o[b][key], g) for g, o in rows if o[a].get(key) is not None and o[b].get(key) is not None]
    return dict(n=len(d), groups=len({g for _, g in d}),
                ci=pev.cluster_boot([x for x, _ in d], [g for _, g in d], level, seed=SEED))


def score(s):
    check_frozen(s)
    rows = [item_scores(s, iid) for iid in ids_of(s)]
    full = [(g, o) for g, o in rows if all(o.get(a) is not None for a in ARMS)]
    res = dict(set=s, items=len(rows), items_all_arms=len(full), dropped=len(rows) - len(full), arms={})
    for a in ARMS:
        ar = [o[a] for _, o in full]
        rec = [x['artifact_recall'] for x in ar if x.get('artifact_recall') is not None]
        ex = [x['recall_exact'] for x in ar if 'recall_exact' in x]
        jd = defaultdict(list)
        for x in ar:
            for dims in (x.get('judge') or {}).values():
                for d in pev.DIMS:
                    jd[d].append(dims[d])
        res['arms'][a] = dict(artifact_recall_mean=round(statistics.mean(rec), 4) if rec else None,
                              recall_exact=pev.wilson(sum(ex), len(ex)),
                              items_with_hallucinated_path=pev.wilson(sum(x['hallucinated_paths'] > 0 for x in ar),
                                                                      len(ar)),
                              tokens_pooled=sum(x['tokens'] or 0 for x in ar),
                              judge_mean={d: round(statistics.mean(v), 3) for d, v in jd.items()} or None)
    bh = [o['stashed_t']['behaviour'] for _, o in full]
    dep, hit = sum(b['dependent'] for b in bh), sum(b['needed_hit'] for b in bh)
    ok_calls = sum(b['ok_calls'] for b in bh)
    eff = [((o['stashed_t']['tokens'] + o['stashed_t']['behaviour']['recalled_tokens']) / o['full_t']['tokens'])
           for _, o in full if o['full_t']['tokens']]
    res['behaviour'] = dict(
        R1_needed_recall=pev.wilson(hit, dep), stash_dependent_probes=dep,
        R2_precision=pev.wilson(sum(b['useful_calls'] for b in bh), ok_calls),
        R3_calls_mean=round(statistics.mean(b['calls'] for b in bh), 3) if bh else None,
        R3_items_zero_calls=sum(b['calls'] == 0 for b in bh), R3_cap_hits=sum(b['cap_hits'] for b in bh),
        R4_recalled_share=round(sum(b['recalled_tokens'] for b in bh) / max(1, sum(b['stashed_tokens'] for b in bh)), 4),
        R5_effective_ratio_median=round(statistics.median(eff), 4) if eff else None,
        R6_errors=sum(b['errors'] for b in bh), full_t_false_recalls=sum(o['full_t']['false_recalls'] for _, o in full))
    res['V'] = dict(V1_full_t_artifact=res['arms']['full_t']['artifact_recall_mean'],
                    V2_dropped_share=round(res['dropped'] / max(1, res['items']), 4), V3_dependent=dep)
    res['H1'] = boot(full, 'stashed_t', 'full_t', 'artifact_recall')
    res['H1']['pass'] = res['H1']['ci'] is not None and res['H1']['ci'][1] > -0.05
    dep_rows = [(g, {a: dict(v=statistics.mean(o[a]['dep'].values()) if o[a]['dep'] else None) for a in ARMS})
                for g, o in full]
    sp_hits = [b['stash_probe_hit'] for b in bh if 'stash_probe_hit' in b]
    res['behaviour']['R1_stash_probe_recall'] = pev.wilson(sum(sp_hits), len(sp_hits))
    res['behaviour']['R1_needed_recall_descriptive'] = res['behaviour'].pop('R1_needed_recall')
    res['V']['V3_stash_probes'] = len(sp_hits)
    for a in ARMS:
        ex = [o[a]['stash_exact'] for _, o in full if 'stash_exact' in o[a]]
        res['arms'][a]['stash_exact'] = pev.wilson(int(sum(ex)), len(ex))
    res['H2'] = boot(full, 'stashed_t', 'stashed_0', 'stash_exact')
    res['S3b_dependent_t_vs_0'] = boot(dep_rows, 'stashed_t', 'stashed_0', 'v')
    res['H2']['pass'] = res['H2']['ci'] is not None and res['H2']['ci'][1] > 0
    exact_rows = [(g, {x: dict(e=float(o[x]['recall_exact']) if 'recall_exact' in o[x] else None) for x in ARMS})
                  for g, o in full]
    res['S2_recall_exact'] = boot(exact_rows, 'stashed_t', 'full_t', 'e')
    res['S3_dependent'] = boot(dep_rows, 'stashed_t', 'full_t', 'v')
    pev.wj(sdir(s) / 'results.json', res)
    if s != 'pilot':
        pev.wj(PUBLIC / 'results.json', res)
    return res


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('phase', choices=('toolcheck', 'compact', 'locate', 'stashprobes', 'run', 'judge', 'agree', 'score'))
    ap.add_argument('--set', required=True, choices=('pilot', 'D'))
    ap.add_argument('--arm', choices=ARMS)
    a = ap.parse_args(argv)
    fn = dict(toolcheck=toolcheck, compact=compact, locate=locate, stashprobes=stashprobes, judge=judge, agree=agree, score=score)
    try:
        res = answer(a.set, a.arm) if a.phase == 'run' else fn[a.phase](a.set)
    except pev.LimitHit as e:
        print(json.dumps(dict(stopped='usage limit', detail=str(e), calls=n_calls())))
        return 2
    print(json.dumps(dict(res, calls=n_calls()), indent=1, default=str))
    return 0


if __name__ == '__main__':
    sys.exit(main())
