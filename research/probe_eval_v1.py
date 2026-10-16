"""Probe eval v1: Factory-style probes taken from what the agent did next, answered from each arm's context.

Protocol: research/goal-engine-2026-10-04/probe-eval-v1/PROTOCOL.md (prompt texts frozen there by sha256; every
phase that calls a model checks them). Private root ~/.lcc/bench/probe-eval-v1/<set>/; the repo gets counts only.

Sets: pilot (<= 10 TRAIN items), D (next-action DEV), J (frozen-60 jev-overlap items).
Model calls go through the owner's subscription CLIs only (claude -p, agy), ANTHROPIC_* stripped, no tools,
cwd an empty scratch dir. Every invocation is logged in calls.jsonl; the run refuses to pass 3,000. A usage limit
stops the run (rerun resumes from cache); a transport failure gets 1 retry, then a failure record is cached.

    # build and gold (lcc of the label build, for block ids):
    PYTHONPATH=/Users/Master/.lcc/bench/real-context-v0/lcc-main/src:/Users/Master/Downloads/LCC-judge \\
    /Users/Master/LCC/.venv/bin/python -m research.probe_eval_v1 {select|build|probes|arm|answer|judge|agree|score} --set pilot
    # the rules arms import lcc at the pin:
    PYTHONPATH=/Users/Master/.lcc/bench/lcc-af412b6/src:... -m research.probe_eval_v1 arm --set pilot --arm lcc_lossless
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
from research import real_context_bench as rcb

REPO = rcb.REPO
PROTOCOL = REPO / 'research' / 'goal-engine-2026-10-04' / 'probe-eval-v1' / 'PROTOCOL.md'
ROOT = Path('/Users/Master/.lcc/bench/probe-eval-v1')
V1, V2 = Path('/Users/Master/.lcc/bench/next-action-v1'), Path('/Users/Master/.lcc/bench/next-action-v2')
PIN = dict(worktree='/Users/Master/.lcc/bench/lcc-af412b6', commit='af412b6fdbce78630fa56c3da2bde8dead006383')
SEED = 20261016
MAX_CTX_TOKENS = 150_000
CALL_CAP = 3000
TIMEOUT_S = 1200
ARMS = ('full', 'native', 'lcc_lossless', 'lcc_recoverable')
ARMS_J = ARMS + ('jev_block',)
KIND_RANK = ('hex', 'num', 'ident', 'quoted', 'line')
DIMS = ('accuracy', 'context_awareness', 'artifact_trail', 'completeness', 'continuity', 'instruction_following')
TEXT_SHA = {
    'A': '627757be019d5f12987c0d47ae50eefa459b1eeed237c9c1b838fbb1c76ef831',
    'K': 'caeb0cc9c00c5f2f89c89777d48948ef237f01d2766dc92af208a9a634c2bbff',
    'Q': '794b78435fdeac124751562a1a43356983699452c44cbb7b13dae98c8373d9a5',
    'S': 'ea72d62fb0091811dce1ffcc8f2decbb08a028e8790cbbc6f6250399275550e6',
    'G': '9b48e06117261ec5424255ce6f68216b5afc872393c2809e2df0fa0c91d7379e',
    'R': '17ea9fee061cdb4bdcbd6a4f6845fa77b34456d8c16a585468f735a26fd5c7e3',
}
READ_TOOLS = {'Read', 'read_file', 'view', 'open_file'}
CLEARED = '[Old tool result content cleared]'
MASK_RE = re.compile(r'\[Old tool result content cleared\]|\bsummar(?:y|ies|ized|ised)\b|\bcompact\w*\b|'
                     r'\blcc\b|\bpointer\b|\belided\b|\bomitted\b|\bre-attached\b', re.I)


# --- frozen texts ----------------------------------------------------------------------------------------
def frozen_texts():
    """{letter: text} from PROTOCOL.md, each checked against its frozen sha256."""
    md = PROTOCOL.read_text()
    out = {}
    for m in re.finditer(r'^### ([AKQSGR]) — [^\n]*\(sha256 `([0-9a-f]{64})`\)\n\n```\n(.*?\n)```', md, re.M | re.S):
        letter, want, body = m.groups()
        if hashlib.sha256(body.encode()).hexdigest() != want or want != TEXT_SHA[letter]:
            raise SystemExit(f'frozen text {letter} changed: refusing to run')
        out[letter] = body.rstrip('\n')
    if set(out) != set(TEXT_SHA):
        raise SystemExit('frozen texts missing from PROTOCOL.md')
    return out


# --- gold (pure; tested) ----------------------------------------------------------------------------------
def usable(e):
    return not e['refetched'] and not e['generic'] and bool(e['blocks'])


def is_file_path(v):
    """Amendment 1: question A asks for files, so URLs, routes and extension-less fragments are not artifact gold."""
    parts = v.split('/')
    host_like = len(parts) > 1 and '.' in parts[0] and not v.startswith(('/', '~', '.'))  # github.com/org/x.py
    return '://' not in v and not host_like and bool(nal.EXT_RE.search(parts[-1]))


def artifact_gold(sets):
    """File-path evidence used by path_op / edit_anchor -> groups of keys, one group per file (its longest key heads
    it; a shorter key that ends the head after a '/' joins that group)."""
    vals = sorted({e['value'] for e in sets if usable(e) and e['kind'] == 'path' and is_file_path(e['value'])
                   and {'path_op', 'edit_anchor'} & set(e['rules'])}, key=lambda v: (-len(v), v))
    groups = []
    for v in vals:
        g = next((g for g in groups if g[0] == v or g[0].endswith('/' + v)), None)
        if g:
            g.append(v)
        else:
            groups.append([v])
    return [sorted(set(g) | set(nal._path_keys(g[0])), key=lambda v: (-len(v), v)) for g in groups]


def recall_ranked(sets, seed=SEED):
    """Recall targets in rank order: kind hex > num > ident > quoted > line, shuffled within kind by Random(seed)."""
    rng = random.Random(seed)
    out = []
    for kind in KIND_RANK:
        vals = sorted({e['value'] for e in sets if usable(e) and e['kind'] == kind
                       and {'call_value', 'text_ref'} & set(e['rules'])})
        rng.shuffle(vals)
        out += [(kind, v) for v in vals]
    return out


def first_call(events):
    """First agent tool call of the window -> dict(name, input, target, target_kind) or None."""
    for e in events:
        if e[0] != 'call':
            continue
        name, inp = e[1], e[2]
        cmd = next((s for k, s in nal._strings(inp if isinstance(inp, (dict, list)) else dict(input=inp))
                    if k in ('command', 'cmd')), None)
        if cmd:  # a shell call: its head, not the paths inside it ('cd <root> &&' stripped)
            head = ' '.join(nal.CD_RE.sub('', nal.collapse(cmd)).split()[:2])
            return dict(name=name, input=inp, target=head, target_kind='command')
        paths = [f[1] for r, f in nal.call_evidence(inp) if r == 'path_op']
        if paths:
            return dict(name=name, input=inp, target=max(paths, key=len), target_kind='path')
        return dict(name=name, input=inp, target=None, target_kind=None)
    return None


def leaks(question, gold_values):
    """True when the question contains a gold value, or carries a feature equal to / inside / around one."""
    q = nal.collapse(question).lower()
    if any(nal.collapse(g).lower() in q for g in gold_values):
        return True
    feats = {v for _, v in nal.features(question)}
    return any(f == g or f in g or g in f for f in feats for g in gold_values)


def path_recall(groups, answer):
    """Fraction of gold groups whose keys meet the answer's path features."""
    have = {v for k, v in nal.features(answer or '') if k == 'path'}
    hit = sum(bool(set(g) & have) for g in groups)
    return hit / len(groups) if groups else None


def hallucinated_paths(answer, context, goal):
    out = set()
    for m in nal.PATH_RE.finditer(answer or ''):
        keys = nal._path_keys(m.group(0))
        if keys and is_file_path(keys[0]) and keys[0] not in context and keys[0] not in goal:
            out.add(keys[0])
    return sorted(out)


def exact(target, answer):
    return nal.collapse(target) in nal.collapse(answer or '')


def target_match(cont, answer):
    if not cont or not cont['target']:
        return None
    if cont['target_kind'] == 'path':
        return bool(set(nal._path_keys(cont['target']) or [cont['target']])
                    & {v for k, v in nal.features(answer or '') if k == 'path'})
    return cont['target'] in nal.collapse(answer or '')


def mask(text):
    return MASK_RE.sub('[masked]', text or '')


def quote_ok(quote, context, goal):
    q = nal.collapse(quote or '')
    return 24 <= len(q) <= 300 and q in nal.collapse(context) and q not in nal.collapse(goal)


# --- paths / io ------------------------------------------------------------------------------------------
def sdir(s, *parts):
    p = ROOT / s
    for x in parts:
        p = p / x
    p.mkdir(parents=True, exist_ok=True)
    return p


def wj(path, obj):
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, default=str))


def rj(path):
    return json.loads(Path(path).read_text())


def ids_of(s):
    return rj(ROOT / s / 'ids.json')['ids']


def item(s, iid):
    return rj(ROOT / s / 'items' / f'{iid}.json')


# --- select ----------------------------------------------------------------------------------------------
def load_labels(iid):
    return rj(V2 / 'items' / f'{iid}.json')


def ctx_tokens(it):
    return sum(b['tokens'] for b in it['blocks'])


def jev_items():
    from research import matched_budget_v2 as mb
    return mb.jev_overlap()[0]


def select(s):
    splits = rj(V1 / 'splits.json')['items']
    if s == 'J':
        its = [it for it in jev_items() if ctx_tokens(it) <= MAX_CTX_TOKENS]
        ids = sorted(it['item_id'] for it in its)
    else:
        want = {'D': 'dev', 'pilot': 'train'}[s]
        jset = {it['item_id'] for it in jev_items()} if s == 'pilot' else set()
        ids = []
        for iid in sorted(i for i, sp in splits.items() if sp == want):
            it = load_labels(iid)
            if (it['evidence'] == 'actions' and ctx_tokens(it) <= MAX_CTX_TOKENS and artifact_gold(it['evidence_sets'])
                    and iid not in jset and not (s == 'pilot' and it.get('content_linked'))):
                ids.append(iid)
        if s == 'pilot':
            ids = sorted(random.Random(SEED).sample(ids, 10))
    if any(splits.get(i) == 'test' for i in ids):
        raise SystemExit('a test item was selected: refusing')
    if s == 'D':
        stores = {ln.split()[0] for ln in (V1 / 'manifest-dev-texts.txt').read_text().splitlines() if ln.strip()}
        if any(load_labels(i)['text_store'] not in stores for i in ids):
            raise SystemExit('a D item is outside the DEV texts manifest: refusing')
    held = REPO / 'research' / 'goal-engine-2026-10-04' / 'specialist-v1' / 'heldout-v3-receipt.json'
    if held.exists():
        raise SystemExit('heldout-v3 receipt exists: add its session check before selecting')
    wj(sdir(s) / 'ids.json', dict(set=s, ids=ids, n=len(ids)))
    return dict(set=s, n=len(ids))


# --- build ---------------------------------------------------------------------------------------------------
# Raw transcripts are not all still on disk (Codex rotated its rollouts after the 2026-10-12 label build), so the
# context is rebuilt from the private block-text store the label build wrote (texts/<store>.json), for every item
# alike. Dossier blocks are parsed back from their render headers; tool_use ids are synthetic (FIFO pairing of a
# result with the oldest open call of the same tool), and blank-line runs inside a block become one blank line.
# Fidelity is checked per item (block ids of the re-render equal the labelled ones) and, where the transcript
# still exists, against a fresh rebuild (`fidelity`).
HEADER_LINE = re.compile(r'^\[m(\d{4}) (user|assistant) ([a-z_]+)(?: ([^\]\n]+))?\]$', re.M)


def rejoin(parts, ids, max_fixes=2000):
    """Block texts -> one text whose lcc split gives `ids`. Blocks are joined by a blank line, except the pieces of
    an oversized span (contiguous in the original): where the split first diverges, the separator after or before
    that block becomes '' or '\\n', whichever moves the first divergence forward."""
    seps = [''] + ['\n\n'] * (len(parts) - 1)

    def first_bad(sp):
        txt = ''.join(s + p for s, p in zip(sp, parts))
        got = [x[0] for x in nal.lcc_split(txt)]
        return next((k for k, (a, b) in enumerate(zip(got, ids)) if a != b),
                    None if len(got) == len(ids) else min(len(got), len(ids))), txt

    bad, txt = first_bad(seps)
    for _ in range(max_fixes):
        if bad is None:
            return txt
        best = None
        for after, before in ((a, b) for a in ('\n\n', '', '\n') for b in ('\n\n', '', '\n')):
            trial = list(seps)
            if bad + 1 < len(parts):
                trial[bad + 1] = after
            if bad > 0:
                trial[bad] = before
            if trial == seps:
                continue
            b2, t2 = first_bad(trial)
            if b2 is None or b2 > bad:
                best = (trial, b2, t2)
                break
        if not best:
            raise ValueError(f'cannot rejoin the store texts at block {bad}')
        seps, bad, txt = best
    raise ValueError('too many separator fixes')


def from_store(it, texts):
    """Item (v2 labels) + its store's {block id: text} -> dossier blocks, or raise ValueError."""
    t = rejoin([texts[b['id']] for b in it['blocks']], [b['id'] for b in it['blocks']])
    n_dossier = max(b['src'][1] for b in it['blocks']) + 1
    attrs = {}
    for b in it['blocks']:
        if b['src'][0] == b['src'][1]:
            attrs.setdefault(b['src'][0], (b['m'], b['role'], b['kind'], b['tool'], b['is_error']))
    heads = list(HEADER_LINE.finditer(t))
    # keep only headers that open a dossier block in order: m never decreases (content can quote a header)
    picked, last_m = [], -1
    for h in heads:
        m = int(h.group(1))
        j = len(picked)
        if m < last_m or (j in attrs and (m, h.group(2), h.group(3), h.group(4)) != attrs[j][:4]):
            continue
        picked.append(h)
        last_m = m
    if len(picked) != n_dossier or (picked and picked[0].start() != 0):
        raise ValueError(f'parsed {len(picked)} dossier blocks, expected {n_dossier}')
    blocks, open_calls, k = [], defaultdict(list), 0
    for j, h in enumerate(picked):
        end = picked[j + 1].start() if j + 1 < len(picked) else len(t)
        content = t[h.end() + 1:end]
        content = content[:-2] if j + 1 < len(picked) and content.endswith('\n\n') else content
        kind, tool = h.group(3), h.group(4)
        tid = None
        m = int(h.group(1))
        if kind == 'tool_use':
            k += 1
            tid = f'toolu_syn_{k:05d}'
            open_calls[tool].append((m, tid))
        elif kind == 'tool_result':
            # oldest open call of this tool in the latest earlier message that has one; a call whose result never
            # came (interrupt) is left behind instead of shifting every later pair
            prior = [x for x in open_calls[tool] if x[0] < m]
            if prior:
                last_m = max(x[0] for x in prior)
                pick = next(x for x in open_calls[tool] if x[0] == last_m)
                open_calls[tool].remove(pick)
                tid = pick[1]
            else:
                tid = f'toolu_orphan_{j:05d}'
        blocks.append(dict(m=int(h.group(1)), role=h.group(2), kind=kind, tool_name=tool, tool_use_id=tid,
                           is_error=bool(attrs.get(j, (0, 0, 0, 0, False))[4]), content=content))
    if [x[0] for x in nal.lcc_split(rcb.render(blocks))] != [b['id'] for b in it['blocks']]:
        raise ValueError('re-rendered block ids differ from the labelled ones')
    return blocks


class Rebuilder(nal.Builder):
    """next_action_labels.Builder that only renders the contexts of wanted items (stores filtered before the
    generators run) and keeps their dossier blocks; nothing is written to the label stores."""

    def __init__(self, want, scratch):
        super().__init__(scratch)
        self.want, self.got = want, {}

    def run_store(self, source, store, prompts):
        if store not in self.want:
            return
        for key, session, goal, db, ev, ended in prompts:
            iid = nal.h16(f'{source}\0{key}')
            if iid in self.want[store]:
                self.got[iid] = dict(goal=goal, blocks=db)


def build(s):
    rcb.check_lcc(rcb.load_protocol())
    out = sdir(s, 'items')
    c, store = Counter(), {}
    for i in ids_of(s):  # ids are sorted; items of one store are not contiguous, so cache by store name
        if (out / f'{i}.json').exists() or (out / f'{i}.failed.json').exists():
            continue
        it = load_labels(i)
        st = it['text_store']
        if st not in store:
            store = {st: (rj(V1 / 'texts' / f'{st}.json'), rj(V1 / 'windows' / f'{st}.json'))}
        texts, windows = store[st]
        try:
            db = from_store(it, texts)
        except ValueError as e:
            wj(out / f'{i}.failed.json', dict(item_id=i, error=str(e)))
            continue
        ev = windows[i]
        sets = it['evidence_sets']
        wj(out / f'{i}.json', dict(
            item_id=i, source=it['source'], session=it['session'], group=it['group'], split=it['split'],
            category=it['category'], goal=it['goal'], blocks=db, text=rcb.render(db), tokens=ctx_tokens(it),
            window=ev, gold=dict(artifact=artifact_gold(sets), recall=recall_ranked(sets),
                                 continuation=first_call(ev))))
    for i in ids_of(s):
        if (out / f'{i}.failed.json').exists():
            c['build_failed'] += 1
            continue
        g = item(s, i)['gold']
        c['items'] += 1
        c['artifact'] += bool(g['artifact'])
        c['recall_candidates'] += bool(g['recall'])
        c['continuation'] += bool(g['continuation'])
    return dict(c)


def built_ids(s):
    return [i for i in ids_of(s) if (ROOT / s / 'items' / f'{i}.json').exists()]


def fidelity(s):
    """Store rebuild vs a fresh transcript rebuild, on the items whose transcript is still on disk: same blocks
    (whitespace-collapsed content) and the same call/result pairing."""
    rcb.check_lcc(rcb.load_protocol())
    labels = {i: load_labels(i) for i in built_ids(s)}
    want = defaultdict(set)
    for i, it in labels.items():
        want[it['text_store']].add(i)
    rb = Rebuilder(want, Path(tempfile.mkdtemp(prefix='probe-eval-rebuild-')))
    for src in sorted({it['source'] for it in labels.values()}):
        getattr(rb, src)()
    c = Counter()
    for i in sorted(labels):
        if i not in rb.got:
            c['transcript_gone'] += 1
            continue
        a, b = item(s, i)['blocks'], rb.got[i]['blocks']
        key = lambda x: (x['m'], x['role'], x['kind'], x['tool_name'], x['is_error'], nal.collapse(x['content']))  # noqa: E731
        pair = lambda bl: [[n for n, x in enumerate(bl) if x['tool_use_id'] == y['tool_use_id']]  # noqa: E731
                           for y in bl if y['kind'] == 'tool_result']
        same = [key(x) for x in a] == [key(x) for x in b]
        c['same_blocks' if same else 'blocks_differ'] += 1
        c['same_pairing' if pair(a) == pair(b) else 'pairing_differs'] += 1
    return dict(c)


# --- model calls -----------------------------------------------------------------------------------------
class LimitHit(RuntimeError):
    pass


LIMIT_RE = re.compile(r'usage limit|rate.?limit|quota|resource.?exhausted|too many requests|\b429\b|limit reached|'
                      r'hit your limit|credit balance|out of (?:extra )?usage', re.I)


def n_calls():
    p = ROOT / 'calls.jsonl'
    return sum(1 for _ in p.open()) if p.exists() else 0


def log_call(**kw):
    ROOT.mkdir(parents=True, exist_ok=True)
    with (ROOT / 'calls.jsonl').open('a') as f:
        f.write(json.dumps(kw) + '\n')


def _find_obj(x, key, depth=0):
    if depth > 6:
        return None
    if isinstance(x, dict):
        if x.get(key) is not None:
            return x
        for k in ('structured_output', 'result', 'response', 'output', 'text', 'content', 'message'):
            if k in x:
                v = x[k]
                r = _find_obj(_loads(v) if isinstance(v, str) else v, key, depth + 1)
                if r is not None:
                    return r
    if isinstance(x, list):
        for v in x:
            r = _find_obj(_loads(v) if isinstance(v, str) else v, key, depth + 1)
            if r is not None:
                return r
    return None


def _loads(t):
    t = re.sub(r'^```(?:json)?\s*|\s*```$', '', (t or '').strip())
    for cand in (t, *re.findall(r'\{.*\}', t, re.S)):
        try:
            return json.loads(cand)
        except ValueError:
            continue
    return None


def cli(role, model, system, prompt, schema, key, effort=None):
    """One subscription call -> parsed JSON object holding `key`. Raises LimitHit / RuntimeError."""
    if n_calls() >= CALL_CAP:
        raise SystemExit(f'call cap {CALL_CAP} reached')
    if model == 'gemini':
        argv = ['agy', '--model', 'Gemini 3.8 Flash (High)', '--mode', 'plan', '--sandbox',
                '--print-timeout', f'{TIMEOUT_S}s', '--output-format', 'json', '--json-schema', json.dumps(schema),
                '--disable-slash-commands', f'--print={system}\n\n{prompt}\n\nDo not use any tools. Reply with the JSON object only.']
        stdin = None
    else:
        argv = ['claude', '-p', '--model', model, '--tools', '', '--output-format', 'json',
                '--json-schema', json.dumps(schema), '--no-session-persistence', '--disable-slash-commands',
                '--strict-mcp-config', '--permission-prompts', 'none', '--setting-sources', '',
                '--exclude-dynamic-system-prompt-sections', '--system-prompt', system]
        if effort:
            argv += ['--effort', effort]
        stdin = prompt
    assert not any('dangerously' in a for a in argv), 'never skip permissions'
    with tempfile.TemporaryDirectory(prefix='probe-eval-cwd-') as cwd:
        try:
            r = subprocess.run(argv, input=stdin, capture_output=True, text=True, cwd=cwd, timeout=TIMEOUT_S + 60,
                               env={k: v for k, v in os.environ.items() if not k.startswith(('PYTHON', 'ANTHROPIC_'))})
            out, err, rc = r.stdout, r.stderr, r.returncode
        except subprocess.TimeoutExpired:
            out, err, rc = '', 'timeout', -9
    env = _loads(out)
    is_error = rc != 0 or (isinstance(env, dict) and env.get('is_error') is True)
    obj = None if is_error else _find_obj(env, key)
    log_call(role=role, model=model, key=key, ok=obj is not None, rc=rc)
    if obj is None:
        (ROOT / 'failures').mkdir(parents=True, exist_ok=True)
        wj(ROOT / 'failures' / f'{role}-{n_calls():05d}.json', dict(rc=rc, stdout=out[-20000:], stderr=err[-5000:]))
        # only an error envelope can be a usage limit: a model's own text may mention rate limits
        msg = f'{out[-2000:]}\n{err[-2000:]}' if is_error else ''
        if LIMIT_RE.search(msg):
            raise LimitHit(LIMIT_RE.search(msg).group(0))
        raise RuntimeError(f'{role}: no {key} (exit {rc})')
    return obj


def cached_call(path, fn):
    """Cached result at path; a transport failure is retried once, then cached as a failure record."""
    if path.exists():
        return rj(path)
    for attempt in (1, 2):
        try:
            res = dict(ok=True, **fn())
            break
        except RuntimeError as e:
            if isinstance(e, LimitHit):
                raise
            res = dict(ok=False, error=str(e)[:300], attempts=attempt)
    wj(path, res)
    return res


# --- probes ----------------------------------------------------------------------------------------------
GEN_SCHEMA = {'type': 'object', 'required': ['recall', 'decision'], 'properties': {
    'recall': {'type': 'object', 'required': ['question'], 'properties': {'question': {'type': 'string'}}},
    'decision': {'type': ['object', 'null'], 'properties': {
        'question': {'type': 'string'}, 'answer': {'type': 'string'}, 'quote': {'type': 'string'}}}}}


def recall_excerpts(it, value, n=3, half=600):
    out = []
    for b in it['blocks']:
        t = b['content'] or ''
        k = t.find(value)
        if k >= 0:
            out.append(t[max(0, k - half):k + len(value) + half])
            if len(out) == n:
                break
    return out


def decision_excerpt(it, max_tokens=30_000):
    pieces = []
    tool_uses = [b for b in it['blocks'] if b['kind'] == 'tool_use'][-3:]
    for b in it['blocks']:
        if (b['kind'] == 'text' and b['role'] in ('user', 'assistant')) or b in tool_uses:
            pieces.append(f"{rcb.header(b)}\n{b['content']}")
    while pieces and rcb.lcc_count('\n\n'.join(pieces))[0] > max_tokens:
        pieces = pieces[max(1, len(pieces) // 10):]  # ponytail: drop the oldest 10% per pass; exact enough
    return '\n\n'.join(pieces)


def window_text(ev, max_chars=20_000):
    parts = []
    for e in ev:
        if e[0] == 'call':
            parts.append(f'[call {e[1]}] {json.dumps(e[2], ensure_ascii=False)[:2000]}')
        elif e[0] == 'text':
            parts.append(f'[agent text] {e[1]}')
        elif e[0] in ('result', 'user'):
            parts.append(f'[{e[0]}] {(e[-1] or "")[:1500]}')
    return '\n'.join(parts)[:max_chars]


def gold_values(g, extra=()):
    vals = {v for grp in g['artifact'] for v in grp} | set(extra)
    if g['continuation'] and g['continuation']['target']:
        vals.add(g['continuation']['target'])
    return vals


def probes(s):
    T = frozen_texts()
    c = Counter()
    for iid in built_ids(s):
        it = item(s, iid)
        out = sdir(s, 'probes') / f'{iid}.json'
        if out.exists():
            continue
        g = it['gold']
        ranked = g['recall']
        res, recall, decision, tries = None, None, None, 0
        for kind, value in ranked[:2]:  # the target, then one regeneration with the next-ranked feature
            tries += 1
            prompt = json.dumps(dict(
                recall_target=value,
                recall_excerpts=recall_excerpts(it, value),
                earlier_context_excerpt=decision_excerpt(it),
                next_request=it['goal'],
                what_the_agent_did_next=window_text(it['window'])), ensure_ascii=False)
            res = cached_call(sdir(s, 'gen') / f'{iid}-{tries}.json',
                              lambda: cli('generator', 'claude-opus-5-5', T['G'], prompt, GEN_SCHEMA, 'recall', 'high'))
            if not res['ok']:
                break
            q = (res.get('recall') or {}).get('question') or ''
            all_gold = gold_values(g, [value])
            if q and not leaks(q, all_gold):
                recall = dict(kind=kind, target=value, question=q)
            d = res.get('decision')
            if decision is None and d and quote_ok(d.get('quote'), it['text'], it['goal']) \
                    and not leaks(d.get('question') or '', all_gold):
                decision = dict(question=d['question'], answer=d.get('answer') or '', quote=d['quote'])
            if recall:
                break
        ps = []
        if g['artifact']:
            ps.append(dict(type='artifact', question=T['A'], gold=g['artifact']))
        if recall:
            ps.append(dict(type='recall', question=recall['question'], gold=recall['target'], kind=recall['kind']))
        if g['continuation']:
            cont = g['continuation']
            ps.append(dict(type='continuation', question=T['K'], gold=cont,
                           reference=f"{cont['name']}: {json.dumps(cont['input'], ensure_ascii=False)[:400]}"))
        if decision:
            ps.append(dict(type='decision', question=decision['question'], gold=decision['answer'],
                           quote=decision['quote']))
        wj(out, dict(item_id=iid, probes=ps, generator_ok=bool(res and res['ok']), tries=tries))
        for p in ps:
            c[p['type']] += 1
        c['items'] += 1
        c['recall_dropped'] += bool(ranked) and not recall
        c['generator_failed'] += bool(res) and not res['ok']
    return dict(c)


# --- arms ------------------------------------------------------------------------------------------------
SUMMARY_SCHEMA = {'type': 'object', 'required': ['summary'], 'properties': {'summary': {'type': 'string'}}}


def reattach(blocks, per=5000, total=50000, n=5):
    """Up to n most recently read files (newest first), from the last read result of each path in C."""
    uses = {b['tool_use_id']: b for b in blocks if b['kind'] == 'tool_use' and b['tool_name'] in READ_TOOLS}
    seen, out, used = set(), [], 0
    for b in reversed(blocks):
        if b['kind'] != 'tool_result' or b['tool_use_id'] not in uses:
            continue
        inp = _loads(uses[b['tool_use_id']]['content']) or {}
        path = next((v for k, v in nal._strings(inp) if k in ('file_path', 'path', 'filename')), None)
        if not path or path in seen or b['is_error']:
            continue
        seen.add(path)
        body, tok = b['content'], rcb.lcc_count(b['content'])[0]
        if tok > per:
            body = body[:int(len(body) * per / tok)]
            tok = per
        if used + tok > total:
            break
        out.append((path, body))
        used += tok
        if len(out) == n:
            break
    return out


def arm_native(s, iid, it, T):
    res = cached_call(sdir(s, 'summaries') / f'{iid}.json', lambda: cli(
        'summarizer', 'claude-opus-5-5', 'You compress a coding-agent conversation, given as a transcript in the '
        'user message, so that work can continue from your output alone.',
        f"TRANSCRIPT:\n{it['text']}\n\n{T['S']}\n\nReturn JSON: {{\"summary\": \"<the <summary> section only>\"}}",
        SUMMARY_SCHEMA, 'summary', 'high'))
    if not res['ok']:
        return dict(ok=False, error=res['error'])
    summary = re.sub(r'<analysis>.*?</analysis>', '', res['summary'], flags=re.S).strip()
    files = reattach(it['blocks'])
    parts = ['This session continues from an earlier conversation that ran out of context. The summary below '
             'covers it.\n\n' + summary]
    parts += [f'[Re-read file: {p}]\n{body}' for p, body in files]
    return dict(ok=True, text='\n\n'.join(parts), reattached=len(files))


def arm_rules(it, mode):
    from lcc.relevance import TranscriptCompactionRequest, compact_transcript, messages_to_payload
    from lcc.relevance.transcript import verify_lossless
    from lcc.relevance.transcript_recoverable import verify_recoverable
    from research import real_context_bench_v02 as v02
    from research.lossless_dedup_measure import independent_check as dedupe_check
    from research.recoverable_check_v4 import independent_check_v4
    payload = v02.rules_payload(it['blocks'])
    try:
        r = compact_transcript(TranscriptCompactionRequest(payload=payload, question=it['goal'], provider='rules',
                                                           rules_mode=mode))
    except Exception as e:  # noqa: BLE001 -- counted, never hidden
        return dict(ok=False, error=f'{type(e).__name__}: {e}'[:300])
    text = rcb.apply_transcript(it['blocks'], r.decisions, r.messages)
    viol = (verify_recoverable if mode == 'recoverable' else verify_lossless)(payload, messages_to_payload(r.messages))
    indep = independent_check_v4(it['blocks'], r.decisions, text) + dedupe_check(it['blocks'], r.decisions, text)
    bad = bool(viol or indep or r.report['lossless_violations'])
    return dict(ok=not bad, text=text, violations=len(viol), independent=len(indep),
                runtime_fail_safe=bool(r.report['lossless_violations']), degraded=bool(r.report['degraded']),
                error='verification violation' if bad else None)


def arm_jev(it):
    from research import matched_budget_v2 as mb  # noqa: F401  (J mapping lives there)
    root = rcb.PRIVATE
    for f in sorted((root / 'dossiers').glob('*.json')):
        d = json.loads(f.read_text())
        if d['goal'].strip() == it['goal'].strip():
            rec = json.loads((root / 'runs' / 'jev_block' / f.name).read_text())
            if rec.get('status') not in (None, 'ok') or not rec.get('output'):
                return dict(ok=False, error=f"saved jev run status {rec.get('status')}")
            return dict(ok=True, text=rec['output'])
    return dict(ok=False, error='no frozen-60 dossier for this goal')


def arm(s, name):
    if name.startswith('lcc_'):
        from research import real_context_bench_v02 as v02
        v02.check_lcc_rules(PIN)
        os.environ.update(rcb.load_protocol(REPO / 'research' / 'goal-engine-2026-10-04' / 'real-context-bench-v0.5'
                                            / 'protocol.json')['privacy']['env'])
    T = frozen_texts() if name == 'native' else None
    c = Counter()
    for iid in built_ids(s):
        out = sdir(s, 'arms', name) / f'{iid}.json'
        if out.exists():
            c['cached'] += 1
            continue
        it = item(s, iid)
        if name == 'full':
            res = dict(ok=True, text=it['text'])
        elif name == 'native':
            res = arm_native(s, iid, it, T)
        elif name == 'jev_block':
            res = arm_jev(it)
        else:
            with rcb.network_guard():
                res = arm_rules(it, name.removeprefix('lcc_'))
        if res.get('ok'):
            res['tokens'] = rcb.lcc_count(res['text'])[0]
        wj(out, res)
        c['ok' if res.get('ok') else 'failed'] += 1
    return dict(c)


# --- answers ---------------------------------------------------------------------------------------------
ANSWER_SCHEMA = {'type': 'object', 'required': ['answers'], 'properties': {
    'answers': {'type': 'object', 'additionalProperties': {'type': 'string'}}}}


def answer_prompt(ctx, goal, ps, T):
    qs = '\n'.join(f'{n}. {p["question"]}' for n, p in enumerate(ps, 1))
    return (f'SESSION CONTEXT:\n{ctx}\n\nTHE USER\'S NEXT REQUEST:\n{goal}\n\n{T["Q"]}\n\nQUESTIONS:\n{qs}\n\n'
            'Return JSON: {"answers": {"1": "...", "2": "..."}} with one entry per question number.')


def answer(s, name):
    T = frozen_texts()
    c = Counter()
    for iid in built_ids(s):
        ps = rj(ROOT / s / 'probes' / f'{iid}.json')['probes']
        a = rj(ROOT / s / 'arms' / name / f'{iid}.json')
        path = sdir(s, 'answers', name) / f'{iid}.json'
        if not a.get('ok') or not ps:
            if not path.exists():
                wj(path, dict(ok=False, error='arm failed' if not a.get('ok') else 'no probes'))
            c['skipped'] += 1
            continue
        it = item(s, iid)
        res = cached_call(path, lambda: cli('answerer', 'claude-sonnet-5-5', 'You answer questions about a coding '
                                            'session from the context you are given. You have no tools.',
                                            answer_prompt(a['text'], it['goal'], ps, T), ANSWER_SCHEMA,
                                            'answers', 'medium'))
        c['ok' if res['ok'] else 'failed'] += 1
    return dict(c)


# --- judge -----------------------------------------------------------------------------------------------
JUDGE_SCHEMA = {'type': 'object', 'required': ['scores'], 'properties': {'scores': {
    'type': 'object', 'additionalProperties': {'type': 'object', 'required': list(DIMS) + ['reason'], 'properties': {
        **{d: {'type': 'integer', 'minimum': 0, 'maximum': 5} for d in DIMS}, 'reason': {'type': 'string'}}}}}}


def reference(p):
    if p['type'] == 'artifact':
        return 'Files: ' + '; '.join(g[0] for g in p['gold'])
    if p['type'] == 'continuation':
        return p['reference']
    return p['gold'] if isinstance(p['gold'], str) else json.dumps(p['gold'])


def judge_records(s, iid, arms):
    """-> [(rid, arm, probe index, record)] shuffled by Random(SEED) with item-local random ids."""
    ps = rj(ROOT / s / 'probes' / f'{iid}.json')['probes']
    recs = []
    for name in arms:
        a = rj(ROOT / s / 'answers' / name / f'{iid}.json')
        if not a.get('ok'):
            continue
        for n, p in enumerate(ps, 1):
            recs.append((name, n - 1, dict(question=p['question'], reference=reference(p),
                                           quote=p.get('quote', ''), answer=mask(a['answers'].get(str(n), '')))))
    rng = random.Random(SEED)
    rng.shuffle(recs)
    return [(f'r{k:02d}', name, pi, rec) for k, (name, pi, rec) in enumerate(recs, 1)]


def judge_prompt(recs):
    return 'RECORDS:\n' + json.dumps({rid: rec for rid, _, _, rec in recs}, ensure_ascii=False) + \
        '\n\nReturn JSON: {"scores": {"<record id>": {"accuracy": 0-5, ..., "reason": "..."}}}.'


def judge(s, model='claude-opus-5-5', sub='judge', sample=None):
    T = frozen_texts()
    arms = ARMS_J if s == 'J' else ARMS
    c = Counter()
    for iid in built_ids(s):
        if sample is not None and iid not in sample:
            continue
        if not all((ROOT / s / 'answers' / a / f'{iid}.json').exists() for a in arms):
            c['not_answered'] += 1
            continue
        recs = judge_records(s, iid, arms)
        if not recs:
            continue
        path = sdir(s, sub) / f'{iid}.json'
        res = cached_call(path, lambda: cli(sub, model, T['R'], judge_prompt(recs), JUDGE_SCHEMA, 'scores',
                                            'high' if model != 'gemini' else None))
        if res['ok'] and 'key' not in res:
            res['key'] = {rid: [name, pi] for rid, name, pi, _ in recs}
            wj(path, res)
        c['ok' if res['ok'] else 'failed'] += 1
    return dict(c)


def agree(s):
    ids = built_ids(s)
    k = max(1, round(len(ids) * 0.10))
    sample = set(random.Random(SEED).sample(ids, k))
    return judge(s, model='gemini', sub='judge-gemini', sample=sample)


# --- score -----------------------------------------------------------------------------------------------
def wilson(k, n, z=1.96):
    if not n:
        return None
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / d
    return [round(k / n, 4), round(c - h, 4), round(c + h, 4)]


def cluster_boot(diffs, groups, level=0.95, n=2000, seed=SEED):
    """Paired cluster bootstrap of mean(diffs) over groups -> [mean, lo, hi]."""
    by = defaultdict(list)
    for d, g in zip(diffs, groups):
        by[g].append(d)
    keys = sorted(by)
    if not keys:
        return None
    rng = random.Random(seed)
    means = []
    for _ in range(n):
        pick = [by[keys[rng.randrange(len(keys))]] for _ in keys]
        flat = [x for p in pick for x in p]
        means.append(sum(flat) / len(flat))
    means.sort()
    a = (1 - level) / 2
    return [round(sum(diffs) / len(diffs), 4), round(means[int(a * n)], 4), round(means[int((1 - a) * n) - 1], 4)]


def qwk(a, b, k=6):
    """Quadratic-weighted kappa of two 0..k-1 ratings lists."""
    n = len(a)
    if not n:
        return None
    obs = [[0] * k for _ in range(k)]
    for x, y in zip(a, b):
        obs[x][y] += 1
    ra, rb = [sum(r) for r in obs], [sum(obs[i][j] for i in range(k)) for j in range(k)]
    w = lambda i, j: (i - j) ** 2 / (k - 1) ** 2  # noqa: E731
    num = sum(w(i, j) * obs[i][j] for i in range(k) for j in range(k))
    den = sum(w(i, j) * ra[i] * rb[j] / n for i in range(k) for j in range(k))
    return round(1 - num / den, 4) if den else None


def agreement(s, dim='artifact_trail'):
    a, b = [], []
    for f in sorted((ROOT / s / 'judge-gemini').glob('*.json')) if (ROOT / s / 'judge-gemini').exists() else ():
        g, o = rj(f), ROOT / s / 'judge' / f.name
        if not (g.get('ok') and o.exists() and rj(o).get('ok')):
            continue
        o = rj(o)
        for rid, sc in g['scores'].items():
            if rid in o['scores']:
                a.append(int(o['scores'][rid][dim]))
                b.append(int(sc[dim]))
    return dict(dim=dim, records=len(a), qwk=qwk(a, b))


def item_scores(s, iid, arms):
    it = item(s, iid)
    ps = rj(ROOT / s / 'probes' / f'{iid}.json')['probes']
    out = {}
    for name in arms:
        a = rj(ROOT / s / 'answers' / name / f'{iid}.json')
        arm_rec = rj(ROOT / s / 'arms' / name / f'{iid}.json')
        if not a.get('ok'):
            out[name] = None
            continue
        r = dict(tokens=arm_rec.get('tokens'))
        halluc = []
        for n, p in enumerate(ps, 1):
            ans = a['answers'].get(str(n), '')
            halluc += hallucinated_paths(ans, it['text'], it['goal'])
            if p['type'] == 'artifact':
                r['artifact_recall'] = path_recall(p['gold'], ans)
            elif p['type'] == 'recall':
                r['recall_exact'] = exact(p['gold'], ans)
            elif p['type'] == 'continuation':
                r['continuation_target'] = target_match(p['gold'], ans)
        r['hallucinated_paths'] = len(set(halluc))
        out[name] = r
    jp = ROOT / s / 'judge' / f'{iid}.json'
    if jp.exists() and rj(jp).get('ok'):
        j = rj(jp)
        for rid, (name, pi) in j['key'].items():
            sc = j['scores'].get(rid)
            if out.get(name) is not None and sc:
                out[name].setdefault('judge', {})[ps[pi]['type']] = {d: sc[d] for d in DIMS}
    return it['group'], out


def score(s):
    arms = ARMS_J if s == 'J' else ARMS
    rows = [(iid, *item_scores(s, iid, arms)) for iid in built_ids(s)]
    full = [(i, g, o) for i, g, o in rows if all(o.get(a) is not None for a in arms)]
    res = dict(set=s, items=len(rows), build_failed=len(ids_of(s)) - len(rows), items_all_arms=len(full),
               dropped=len(rows) - len(full), judge_agreement=agreement(s), arms={})
    for a in arms:
        ar = [o[a] for _, _, o in full]
        rec = [x['artifact_recall'] for x in ar if x.get('artifact_recall') is not None]
        ex = [x['recall_exact'] for x in ar if 'recall_exact' in x]
        jd = defaultdict(list)
        for x in ar:
            for _, dims in (x.get('judge') or {}).items():
                for d in DIMS:
                    jd[d].append(dims[d])
        res['arms'][a] = dict(
            artifact_recall_mean=round(statistics.mean(rec), 4) if rec else None, artifact_n=len(rec),
            artifact_all=wilson(sum(v == 1 for v in rec), len(rec)),
            recall_exact=wilson(sum(ex), len(ex)),
            items_with_hallucinated_path=wilson(sum(x['hallucinated_paths'] > 0 for x in ar), len(ar)),
            tokens_pooled=sum(x['tokens'] or 0 for x in ar),
            judge_mean={d: round(statistics.mean(v), 3) for d, v in jd.items()} if jd else None)
    pairs = [('lcc_lossless', 'native', 0.975), ('lcc_recoverable', 'native', 0.975),
             ('lcc_lossless', 'full', 0.95), ('lcc_recoverable', 'full', 0.95)]
    if s == 'J':
        pairs += [('jev_block', 'native', 0.95), ('jev_block', 'full', 0.95)]
    res['contrasts'] = {}
    for a, b, lvl in pairs:
        d = [(o[a]['artifact_recall'] - o[b]['artifact_recall'], g) for _, g, o in full
             if o[a].get('artifact_recall') is not None and o[b].get('artifact_recall') is not None]
        res['contrasts'][f'{a}-{b}'] = dict(level=lvl, n=len(d), groups=len({g for _, g in d}),
                                            ci=cluster_boot([x for x, _ in d], [g for _, g in d], lvl))
    return res


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('phase', choices=('select', 'build', 'fidelity', 'probes', 'arm', 'answer', 'judge', 'agree', 'score'))
    ap.add_argument('--set', required=True, choices=('pilot', 'D', 'J'))
    ap.add_argument('--arm')
    a = ap.parse_args(argv)
    fn = {'select': select, 'build': build, 'fidelity': fidelity, 'probes': probes, 'judge': judge, 'agree': agree, 'score': score}
    try:
        res = (arm(a.set, a.arm) if a.phase == 'arm' else answer(a.set, a.arm) if a.phase == 'answer'
               else fn[a.phase](a.set))
    except LimitHit as e:
        print(json.dumps(dict(stopped='usage limit', detail=str(e), calls=n_calls())))
        return 2
    print(json.dumps(dict(res, calls=n_calls()), indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main())
