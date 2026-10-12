"""Specialist v2: a CPU feature-model judge for LCC block relevance (which context blocks to keep).

Why a feature model and not a bigger transformer: on the next-action labels the strongest signals are
structural (recency in messages, block kind, whether the block's identifiers and paths come back later or
match the goal / last turns, duplicates, re-reads) and the v1 512-token cross-encoder lost to plain
recency on dev while needing ~1.6 GB RSS and ~30 s per item. A model over 50 cheap per-block features,
including LCC's own mechanical overlap / protection flags, runs in ~0.1 s per item (numpy + lcc, no torch).

Shipped: weighted logistic regression trained on "USED or goal-shared" (model.json, 4 KB). A GBDT (numpy
histogram boosting, depth 4) is ~1 pt higher on dev recall but fits the label prior and fails the edge
suite, so it is kept only as model-gbdt.json; see pick_phase and DEV_RESULTS.md.

Inference contract (live LCC): goal + the ordered block texts (as LCC splits the rendered context; block
role / kind / tool come from the render headers '[m0003 user tool_result Bash]', carried forward to the
blocks that continue a message). No labels, no transcript metadata, no network, no GPU.

    Judge.load(path).score(goal, texts) -> [float]   higher = keep

Data: research.next_action_labels v2 labels (train + dev only; TEST is never opened by this module).
Training excludes (a) train items content-linked to dev (fork quarantine, labels-v2) and (b) the lineage
groups of the jev-overlap items and their forks, so the Jev comparison is on items the model never saw.

Phases (artifacts and private text under ART; the repo gets code and counts only):
    features   -> ART/cache/<split>/<item>.npz (resumable) -> ART/features-{train,dev}.npz, ART/jev-overlap.json
    train      --arm lr|lrg|d4|d4g (one process each; g = USED-or-goal-shared target)
               -> ART/model-<arm>.json, ART/log-<arm>.json
    pick       -> ART/model.json (LR, shipped), ART/model-gbdt.json, ART/train-log.json
    refit      -> same outputs, FROZEN_RECIPE settings (no selection; used after a feature-code change)
    eval       -> ART/dev-results.json, OUT/dev-results.json, OUT/DEV_RESULTS.md (counts only)
    bench      latency / RSS of Judge on dev items in a fresh process (called by eval)

    PYTHONPATH=/Users/Master/.lcc/bench/real-context-v0/lcc-main/src:/Users/Master/Downloads/LCC-judge \\
    /Users/Master/LCC/.venv/bin/python -m research.specialist_v2 {features|train --arm A|pick|eval}
"""
import argparse
import hashlib
import json
import math
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

ART = Path('/Users/Master/.lcc/bench/specialist-v2')
LABELS = Path('/Users/Master/.lcc/bench/next-action-v2')
TEXTS = Path('/Users/Master/.lcc/bench/next-action-v1')
OUT = Path(__file__).resolve().parent / 'goal-engine-2026-10-04' / 'specialist-v1'
SEED = 20261012
NEG_KEEP = 0.25  # train rows: every USED block + this share of the others (re-weighted 1/NEG_KEEP)

HEADER_RE = re.compile(r'^\[m(\d{4,}) (user|assistant) ([a-z_]+)(?: ([^\]\n]*))?\]$', re.M)
# Anchored, single-line: a header is trusted only at offset 0 of a block (see block_meta).
LEAD_HEADER_RE = re.compile(r'\[m(\d{4,}) (user|assistant) ([a-z_]+)(?: ([^\]\n]*))?\](?:\n|$)')
TOKEN_RE = re.compile(r'\w+', re.U)  # BM25 terms (same as research.matched_budget)
KEY_RE = re.compile(r'[\w./~@-]{6,}')
CAMEL_RE = re.compile(r'[a-z][A-Z]')
ERROR_RE = re.compile(r'Traceback \(most recent|\b(?:Error|Exception|FAILED|FATAL|panic):|\berror(?:\[| TS\d|:)|'
                      r'exit code [1-9]|Exit code [1-9]|\bfailed\b|command not found|No such file', re.I)
GIT_RE = re.compile(r'^diff --git|^commit [0-9a-f]{7}|^@@ |\bgit (?:status|diff|log|commit|push|add|checkout|rebase)\b',
                    re.M)
CODE_RE = re.compile(r'[{};=()<>\[\]]')
TOOL_GROUPS = (
    ('read', ('Read', 'read_file', 'view_image', 'NotebookRead', 'cat')),
    ('edit', ('Edit', 'MultiEdit', 'Write', 'write_file', 'patch', 'apply_patch', 'NotebookEdit', 'str_replace')),
    ('shell', ('Bash', 'exec_command', 'terminal', 'execute_code', 'write_stdin', 'shell', 'BashOutput')),
    ('search', ('Grep', 'Glob', 'search_files', 'ToolSearch', 'tool_search', 'LS', 'list_files')),
    ('web', ('WebFetch', 'WebSearch', 'web_search', 'web_fetch', 'browser', 'chrome', 'playwright', 'vision')),
    ('agent', ('Agent', 'Task', 'delegate_task', 'subagent')),
    ('plan', ('TodoWrite', 'update_plan', 'ExitPlanMode', 'AskUserQuestion', 'todo')),
    ('skill', ('skill_view', 'Skill', 'skill_manage')),
)
KINDS = ('user:text', 'assistant:text', 'assistant:tool_use', 'user:tool_result')
GROUPS = tuple(g for g, _ in TOOL_GROUPS) + ('mcp', 'other')
FEATURES = (
    'pos', 'from_end_log', 'tok_after_frac', 'msg_from_end_log', 'msg_pos', 'log_chars', 'n_lines_log',
    *(f'kind_{k}' for k in KINDS), 'kind_unknown', *(f'tool_{g}' for g in GROUPS), 'has_header',
    'is_error', 'is_git', 'code_frac',
    'bm25_goal', 'bm25_goal_rank', 'bm25_recent', 'bm25_recent_rank',
    'keys_log', 'goal_hits', 'recent_hits', 'later_ref', 'later_ref_frac', 'later_asst_ref', 'latest_holder',
    'unique_keys', 'superseded_path', 'dup_later', 'dup_earlier', 'same_kind_after_log', 'turns_after_log',
    'goal_chars_log', 'goal_keys', 'goal_question', 'n_blocks_log', 'goal_bm25_max_log',
    'lcc_overlap', 'lcc_protected',
)


# --- features ---------------------------------------------------------------------------------------
def tool_group(tool):
    if not tool:
        return None
    if tool.startswith('mcp__'):
        for g, names in TOOL_GROUPS:
            if g == 'web' and any(n.lower() in tool.lower() for n in names):
                return 'web'
        return 'mcp'
    for g, names in TOOL_GROUPS:
        if tool in names or any(n.lower() in tool.lower() for n in names if len(n) > 4):
            return g
    return 'other'


def block_meta(texts):
    """[(m, role, kind, tool, has_header)] per block. Only a render header at offset 0 of a block is trusted
    (block text is untrusted: a tool output can contain a line shaped like a header), and its message index
    must not go backwards; otherwise the block inherits the previous trusted header (a continuation)."""
    out, cur = [], (0, None, None, None)
    for t in texts:
        h = LEAD_HEADER_RE.match(t)
        trusted = bool(h) and int(h.group(1)) >= cur[0]
        if trusted:
            cur = (int(h.group(1)), h.group(2), h.group(3), h.group(4) or None)
        out.append((*cur, trusted))
    return out


def keys(text):
    """Identifier-like strings (paths, dotted / snake / camel names, ids with digits) + path basenames."""
    out = set()
    for t in KEY_RE.findall(text):
        t = t.strip('.,-~')
        if len(t) < 6:
            continue
        if '/' in t:
            out.add(t)
            b = t.rsplit('/', 1)[-1]
            if len(b) >= 6:
                out.add(b)
        elif '_' in t or '.' in t or CAMEL_RE.search(t) or (any(c.isdigit() for c in t) and any(c.isalpha() for c in t)):
            out.add(t)
    return out


def bm25(q_terms, postings, lens, avg, k1=1.5, b=0.75):
    """Okapi BM25 of the unique query terms over one item's blocks (postings: term -> [(block, tf)])."""
    n = len(lens)
    out = np.zeros(n)
    for t in set(q_terms):
        post = postings.get(t)
        if not post:
            continue
        idf = math.log(1 + (n - len(post) + 0.5) / (len(post) + 0.5))
        for i, f in post:
            out[i] += idf * f * (k1 + 1) / (f + k1 * (1 - b + b * lens[i] / avg))
    return out


def rank01(x):
    """Rank in [0, 1] within the item (ties share the lowest rank); all-equal -> 0."""
    if len(x) < 2:
        return np.zeros(len(x))
    r = np.searchsorted(np.sort(x), x, side='left')
    return r / (len(x) - 1)


def lcc_mechanical(goal, texts):
    """LCC's own local pass (lexical overlap with the goal + deterministic protection / dependency
    closure), as the runtime computes it: [(overlap, protected)] per block. Needs lcc importable."""
    from lcc.relevance.blocks import TextBlock
    from lcc.relevance.compactor import _score_mechanically
    res = _score_mechanically([TextBlock(id=str(i), index=i, text=t, character_start=0, character_end=0, line_start=0,
                                         line_end=0) for i, t in enumerate(texts)], goal)
    return [(res[str(i)][0], res[str(i)][2] is not None) for i in range(len(texts))]


def featurize(goal, texts):
    """goal + ordered block texts -> float32 matrix (n_blocks, len(FEATURES))."""
    n = len(texts)
    meta = block_meta(texts)
    bodies = [HEADER_RE.sub('', t).strip() for t in texts]
    chars = np.array([max(1, len(t)) for t in texts], dtype=np.float64)
    ks = [keys(b) for b in bodies]
    goal_k = keys(goal)
    text_idx = [i for i, m in enumerate(meta) if m[2] == 'text' and m[1] in ('user', 'assistant')]
    recent_idx = text_idx[-3:]
    recent = '\n'.join(bodies[i] for i in recent_idx)
    recent_k = set().union(*(ks[i] for i in recent_idx)) if recent_idx else set()
    last, lastA, lastRW, df_k = {}, {}, {}, Counter()
    for i, k in enumerate(ks):
        df_k.update(k)
        for x in k:
            last[x] = i
        if meta[i][1] == 'assistant' and meta[i][2] == 'text':
            for x in k:
                lastA[x] = i
        if meta[i][2] == 'tool_use' and tool_group(meta[i][3]) in ('read', 'edit'):
            for x in k:
                if '/' in x or '.' in x:
                    lastRW[x] = i
    hashes = [hashlib.blake2b(b.encode(), digest_size=8).digest() if len(b) >= 40 else None for b in bodies]
    first_h, last_h = {}, {}
    for i, h in enumerate(hashes):
        if h is not None:
            first_h.setdefault(h, i)
            last_h[h] = i
    postings, lens = defaultdict(list), []
    for i, b in enumerate(bodies):
        ts = TOKEN_RE.findall(b.lower())
        lens.append(len(ts))
        for t, f in Counter(ts).items():
            postings[t].append((i, f))
    avg = (sum(lens) / n or 1) if n else 1
    bg = bm25(TOKEN_RE.findall(goal.lower()), postings, lens, avg)
    br = bm25(TOKEN_RE.findall(recent.lower()), postings, lens, avg)
    m_arr = np.array([m[0] for m in meta], dtype=np.float64)
    m_last = m_arr.max() if n else 0
    tok_after = np.concatenate([np.cumsum(chars[::-1])[::-1][1:], [0.0]]) / chars.sum() if n else chars
    kind_count_after = Counter()
    same_after, turns_after = np.zeros(n), np.zeros(n)
    for i in range(n - 1, -1, -1):
        kk = (meta[i][1], meta[i][2], meta[i][3])
        same_after[i] = kind_count_after[kk]
        turns_after[i] = kind_count_after[('user', 'text', None)]  # user messages after this block
        if meta[i][4] or i == 0 or meta[i][0] != meta[i - 1][0]:
            kind_count_after[kk] += 1
    X = np.zeros((n, len(FEATURES)), dtype=np.float32)
    col = {f: j for j, f in enumerate(FEATURES)}
    X[:, col['pos']] = np.arange(n) / max(1, n - 1)
    X[:, col['from_end_log']] = np.log1p(np.arange(n)[::-1])
    X[:, col['tok_after_frac']] = tok_after
    X[:, col['msg_from_end_log']] = np.log1p(m_last - m_arr)
    X[:, col['msg_pos']] = m_arr / max(1.0, m_last)
    X[:, col['log_chars']] = np.log(chars)
    X[:, col['bm25_goal']] = np.log1p(bg)
    X[:, col['bm25_goal_rank']] = rank01(bg)
    X[:, col['bm25_recent']] = np.log1p(br)
    X[:, col['bm25_recent_rank']] = rank01(br)
    X[:, col['same_kind_after_log']] = np.log1p(same_after)
    X[:, col['turns_after_log']] = np.log1p(turns_after)
    X[:, col['goal_chars_log']] = math.log1p(len(goal))
    X[:, col['goal_keys']] = math.log1p(len(goal_k))
    X[:, col['goal_question']] = float('?' in goal)
    X[:, col['n_blocks_log']] = math.log1p(n)
    X[:, col['goal_bm25_max_log']] = math.log1p(bg.max()) if n else 0.0
    X[:, [col['lcc_overlap'], col['lcc_protected']]] = np.array(lcc_mechanical(goal, texts), dtype=np.float32)
    for i in range(n):
        m, role, kind, tool, has = meta[i]
        k, body = ks[i], bodies[i]
        rk = f'{role}:{kind}'
        X[i, col[f'kind_{rk}'] if rk in KINDS else col['kind_unknown']] = 1
        g = tool_group(tool)
        if g:
            X[i, col[f'tool_{g}']] = 1
        X[i, col['has_header']] = has
        X[i, col['n_lines_log']] = math.log1p(body.count('\n'))
        X[i, col['is_error']] = bool(ERROR_RE.search(body))
        X[i, col['is_git']] = bool(GIT_RE.search(body))
        lines = body.splitlines() or ['']
        X[i, col['code_frac']] = sum(bool(CODE_RE.search(x)) for x in lines) / len(lines)
        X[i, col['keys_log']] = math.log1p(len(k))
        if k:
            later = sum(last[x] > i for x in k)
            X[i, col['goal_hits']] = math.log1p(len(k & goal_k))
            X[i, col['recent_hits']] = math.log1p(len(k & recent_k))
            X[i, col['later_ref']] = math.log1p(later)
            X[i, col['later_ref_frac']] = later / len(k)
            X[i, col['later_asst_ref']] = math.log1p(sum(lastA.get(x, -1) > i for x in k))
            X[i, col['latest_holder']] = math.log1p(sum(last[x] == i and df_k[x] > 1 for x in k))
            X[i, col['unique_keys']] = math.log1p(sum(df_k[x] == 1 for x in k))
            X[i, col['superseded_path']] = any(lastRW.get(x, -1) > i for x in k if '/' in x or '.' in x)
        h = hashes[i]
        if h is not None:
            X[i, col['dup_later']] = last_h[h] > i
            X[i, col['dup_earlier']] = first_h[h] < i
    return X


# --- models (numpy only) ------------------------------------------------------------------------------
def fit_gbdt(X, y, w, n_trees=300, depth=6, lr=0.1, lam=1.0, min_hess=5.0, n_bins=64, subsample=0.7,
             seed=SEED, every=50, callback=None):
    """Histogram gradient boosting, binary logloss, depth-wise complete trees.
    Split rule: x <= thr goes left. callback(model, n_trees_so_far) every `every` trees."""
    rng = np.random.default_rng(seed)
    n, F = X.shape
    edges = []
    for f in range(F):
        qs = np.unique(np.quantile(X[rng.choice(n, min(n, 200_000), replace=False), f],
                                   np.linspace(0, 1, n_bins + 1)[1:-1]))
        edges.append(qs)
    NB = n_bins
    Bn = np.stack([np.searchsorted(edges[f], X[:, f], side='left') for f in range(F)], 1).astype(np.uint8)
    p0 = np.clip(np.average(y, weights=w), 1e-4, 1 - 1e-4)
    base = float(np.log(p0 / (1 - p0)))
    raw = np.full(n, base)
    model = dict(kind='gbdt', features=list(FEATURES), base=base, depth=depth, trees=[])
    for t in range(n_trees):
        p = 1 / (1 + np.exp(-raw))
        g, h = (p - y) * w, np.maximum(p * (1 - p), 1e-6) * w
        rows = np.flatnonzero(rng.random(n) < subsample)
        Bs = Bn[rows].astype(np.int64)
        node = np.zeros(len(rows), np.int64)
        feats, thrs = [], []
        for level in range(depth):
            nn = 1 << level
            gr, hr = g[rows], h[rows]
            Gt = np.bincount(node, gr, minlength=nn)
            Ht = np.bincount(node, hr, minlength=nn)
            best = np.zeros(nn)
            bf, bs = np.zeros(nn, np.int64), np.full(nn, -1)
            parent = Gt ** 2 / (Ht + lam)
            for f in range(F):
                idx = node * NB + Bs[:, f]
                G = np.bincount(idx, gr, minlength=nn * NB).reshape(nn, NB).cumsum(1)
                H = np.bincount(idx, hr, minlength=nn * NB).reshape(nn, NB).cumsum(1)
                GR, HR = Gt[:, None] - G, Ht[:, None] - H
                gain = G ** 2 / (H + lam) + GR ** 2 / (HR + lam) - parent[:, None]
                gain[(H < min_hess) | (HR < min_hess)] = 0
                gain[:, len(edges[f]):] = 0  # bins past the last edge: no threshold
                s = gain.argmax(1)
                v = gain[np.arange(nn), s]
                better = v > best
                best[better], bf[better], bs[better] = v[better], f, s[better]
            thr = np.array([edges[bf[k]][bs[k]] if bs[k] >= 0 else np.inf for k in range(nn)])
            feats.append(bf.tolist())
            thrs.append(thr.tolist())
            go = Bs[np.arange(len(rows)), bf[node]] > np.where(bs >= 0, bs, NB)[node]
            node = node * 2 + go
        nl = 1 << depth
        G = np.bincount(node, g[rows], minlength=nl)
        H = np.bincount(node, h[rows], minlength=nl)
        leaf = (-G / (H + lam) * lr)
        tree = dict(f=feats, t=thrs, v=leaf.tolist())
        model['trees'].append(tree)
        raw += _tree_predict(tree, X)
        if callback and (t + 1) % every == 0:
            callback(model, t + 1)
    return model


def _flat(tree):
    """Per-level split lists -> (features, thresholds) heap-ordered (level k starts at 2**k - 1), leaves."""
    return (np.concatenate([np.asarray(x, np.int64) for x in tree['f']]),
            np.concatenate([np.asarray(x, np.float64) for x in tree['t']]), np.asarray(tree['v']), len(tree['f']))


def _walk(flat, X, r):
    F, T, V, depth = flat
    node = np.zeros(len(X), np.int64)
    for level in range(depth):
        k = (1 << level) - 1 + node
        node = node * 2 + (X[r, F[k]] > T[k])
    return V[node]


def _tree_predict(tree, X):
    return _walk(_flat(tree), X, np.arange(len(X)))


def fit_lr(X, y, w, l2=1e-3, iters=400, lr=0.5):
    """Weighted logistic regression on standardised features (full-batch gradient descent, numpy)."""
    mu, sd = X.mean(0), X.std(0) + 1e-6
    Z = (X - mu) / sd
    beta, b0 = np.zeros(X.shape[1]), 0.0
    W = w / w.sum()
    for _ in range(iters):
        p = 1 / (1 + np.exp(-(Z @ beta + b0)))
        e = (p - y) * W
        beta -= lr * (Z.T @ e + l2 * beta)
        b0 -= lr * e.sum()
    return dict(kind='lr', features=list(FEATURES), mu=mu.tolist(), sd=sd.tolist(), beta=beta.tolist(), b0=float(b0))


def predict(model, X):
    if model['kind'] == 'lr':
        return ((X - np.asarray(model['mu'])) / np.asarray(model['sd'])) @ np.asarray(model['beta']) + model['b0']
    raw = np.full(len(X), model['base'])
    for tree in model['trees'][:model.get('n_trees', len(model['trees']))]:
        raw += _tree_predict(tree, X)
    return raw


class Judge:
    """Live scorer: Judge.load(path).score(goal, texts) -> [float] (higher = keep)."""

    def __init__(self, model):
        self.model = model
        self.trees = [_flat(t) for t in model.get('trees', [])[:model.get('n_trees', len(model.get('trees', [])))]]

    @classmethod
    def load(cls, path=None):
        return cls(json.loads(Path(path or ART / 'model.json').read_text()))

    def score(self, goal, texts):
        if not texts:
            return []
        X = featurize(goal, texts)
        if self.model['kind'] == 'lr':
            s = predict(self.model, X)
        else:
            s = np.full(len(X), self.model['base'])
            r = np.arange(len(X))
            for flat in self.trees:
                s += _walk(flat, X, r)
        s = s - self.model.get('alpha', 0.0) * X[:, FEATURES.index('log_chars')]
        return s.tolist()


# --- data (train / dev only) --------------------------------------------------------------------------
def split_of():
    return json.loads((LABELS / 'splits.json').read_text())


def load_items(ids):
    """Yield (item, [block text]) grouped by text store. Refuses test ids."""
    sp = split_of()['items']
    if any(sp.get(i) not in ('train', 'dev') for i in ids):
        raise SystemExit('specialist_v2 reads train/dev items only')
    by_store = defaultdict(list)
    for iid in ids:
        it = json.loads((LABELS / 'items' / f'{iid}.json').read_text())
        by_store[it['text_store']].append(iid)
    for store in sorted(by_store):
        texts = json.loads((TEXTS / 'texts' / f'{store}.json').read_text())
        for iid in by_store[store]:
            it = json.loads((LABELS / 'items' / f'{iid}.json').read_text())
            yield it, [texts.get(b['id']) or '' for b in it['blocks']]


def jev_overlap_ids():
    """Item ids (and lineage groups) of the jev-overlap subset, cached privately."""
    p = ART / 'jev-overlap.json'
    if not p.exists():
        from research import matched_budget_v2 as mb
        items, _, skip = mb.jev_overlap()
        p.write_text(json.dumps(dict(items=sorted(it['item_id'] for it in items),
                                     groups=sorted({it['group'] for it in items}), skip=dict(skip))))
    return json.loads(p.read_text())


def item_rows(name, it, texts, quarantine, jev):
    """One item -> (rows dict, None) or (None, exclusion reason). Train keeps every USED / goal-shared block
    and a seeded NEG_KEEP share of the rest (weights 1/p); every item weighs the same in total."""
    if it['evidence'] != 'actions':
        return None, 'no_agent_action'
    if name == 'train':
        if it['item_id'] in quarantine:
            return None, 'quarantined_dev_fork'
        if it['group'] in jev['groups'] or set(it.get('content_linked', ())) & set(jev['items']):
            return None, 'jev_overlap_group_or_fork'
    cand = [j for j, b in enumerate(it['blocks']) if not b['protected']]
    y = np.array([it['blocks'][j]['used'] for j in cand], dtype=np.float32)
    if name == 'train' and not y.any():
        return None, 'no_used_candidate'
    X = featurize(it['goal'], texts)[cand]
    gs = np.array([it['blocks'][j]['goal_shared'] > 0 for j in cand], dtype=np.float32)
    sel = np.asarray(cand)
    if name == 'train':
        rng = np.random.default_rng([SEED, int(it['item_id'], 16)])
        keep = (y > 0) | (gs > 0) | (rng.random(len(y)) < NEG_KEEP)
        w = np.where((y > 0) | (gs > 0), 1.0, 1 / NEG_KEEP) / len(y)
        X, y, gs, w, sel = X[keep], y[keep], gs[keep], w[keep], sel[keep]
    else:
        w = np.full(len(y), 1 / len(y))
    return dict(X=X, y=y, w=w, goal_shared=gs, block=sel, tokens=np.array([it['blocks'][j]['tokens'] for j in sel]),
                item=np.array([it['item_id']] * len(y))), None


def features_phase(splits=('train', 'dev')):
    """Per-item cache under ART/cache/<split>/ (a killed run resumes), then one npz per split."""
    ART.mkdir(parents=True, exist_ok=True)
    sp = split_of()
    jev = jev_overlap_ids()
    quarantine = set(sp['train_quarantined_dev_overlap'])
    out = {}
    for name in splits:
        cache = ART / 'cache' / name
        cache.mkdir(parents=True, exist_ok=True)
        ids = sorted(i for i, s in sp['items'].items() if s == name)
        todo = [i for i in ids if not (cache / f'{i}.npz').exists() and not (cache / f'{i}.skip').exists()]
        t0 = time.time()
        for k, (it, texts) in enumerate(load_items(todo)):
            rows, why = item_rows(name, it, texts, quarantine, jev)
            if rows is None:
                (cache / f"{it['item_id']}.skip").write_text(why)
            else:
                np.savez(cache / f"{it['item_id']}.tmp.npz", **rows)
                (cache / f"{it['item_id']}.tmp.npz").rename(cache / f"{it['item_id']}.npz")
            if k % 200 == 0:
                print(name, k, len(todo), round(time.time() - t0), flush=True)
        parts, excl = [], Counter()
        for i in ids:
            if (cache / f'{i}.skip').exists():
                excl[(cache / f'{i}.skip').read_text()] += 1
            else:
                parts.append(dict(np.load(cache / f'{i}.npz')))
        np.savez_compressed(ART / f'features-{name}.npz', **{k: np.concatenate([p[k] for p in parts]) for k in parts[0]})
        out[name] = dict(rows=int(sum(len(p['y']) for p in parts)), items=len(parts), excluded=dict(excl))
    (ART / 'features-meta.json').write_text(json.dumps(out, indent=1))
    return out


# --- dev metrics (matched-budget v2 definitions) --------------------------------------------------------
def dev_items():
    from research import matched_budget_v2 as mb
    items, skip = mb.eligible_dev()
    return items, skip


def curve(items, scores, groups):
    from research import matched_budget_v2 as mb
    return mb.aggregate({it['item_id']: mb.item_metrics(it, scores[it['item_id']], groups=groups[it['item_id']])
                         for it in items})


def item_scores(items, D, raw):
    """Dev feature rows (item, block index) + raw scores -> {item_id: {block_id: score}}."""
    by = defaultdict(dict)
    blocks = {it['item_id']: it['blocks'] for it in items}
    for iid, j, s in zip(D['item'], D['block'], raw):
        if iid in blocks:
            by[iid][blocks[iid][j]['id']] = float(s)
    return by


ALPHAS = (0.0, 0.25, 0.5)


def train_phase(arm):
    """arm: 'lr' | 'd<depth>' (GBDT), suffix 'g' = target USED or goal-shared (the block holds something the
    agent used after the prompt AND the goal named: v2 labels drop it as evidence by construction, so a
    model of strict USED alone learns that goal matches barely matter). Dev is always scored on strict USED.
    Dev AUCs logged every 50 trees and per size penalty alpha. One process per arm; pick_phase chooses."""
    from research import matched_budget_v2 as mb
    T = np.load(ART / 'features-train.npz')
    D = np.load(ART / 'features-dev.npz')
    y = np.maximum(T['y'], T['goal_shared']) if arm.endswith('g') else T['y']
    items, _ = dev_items()
    groups = {it['item_id']: mb.evidence_groups(it) for it in items}
    lc = FEATURES.index('log_chars')
    log = []

    def evaluate(raw, **kw):
        for a in ALPHAS:
            r = dict(kw, alpha=a, **curve(items, item_scores(items, D, raw - a * D['X'][:, lc]), groups)['auc'])
            log.append(r)
            print(arm, r, flush=True)

    t0 = time.time()
    if arm.startswith('lr'):
        m = fit_lr(T['X'], y, T['w'])
        evaluate(predict(m, D['X']), arm=arm)
    else:
        depth = int(arm[1:].rstrip('g'))
        m = fit_gbdt(T['X'], y, T['w'], n_trees=400, depth=depth,
                     callback=lambda model, k: evaluate(predict(dict(model, n_trees=k), D['X']), arm=arm, trees=k))
    m['train_s'] = round(time.time() - t0)
    (ART / f'model-{arm}.json').write_text(json.dumps(m))
    (ART / f'log-{arm}.json').write_text(json.dumps(log, indent=1))
    return dict(best=max(log, key=pick_key), train_s=m['train_s'])


def pick_key(r):
    return r['recall'] + 0.25 * r['all_kept']


def pick_phase():
    """Best config per family on dev (max recall AUC + 0.25 x all-kept AUC) -> model.json = logistic regression
    (shipped), model-gbdt.json = GBDT (alternative). Why LR ships although GBDT is ~1 pt higher on dev recall:
    the GBDT fits the label prior (recency x structure interactions) and drops to 15/11/5 on the edge suite
    (below random at 70%), while the LR is the strongest edge arm (24/21/18) and still beats Jev on
    jev-overlap and every baseline on dev. This choice looked at the edge suite: its pass counts for the two
    candidates are not held-out evidence."""
    logs = {p.stem[4:]: json.loads(p.read_text()) for p in ART.glob('log-*.json')}
    gb = [r for k, v in logs.items() if not k.startswith('lr') for r in v]
    pick_gb, pick = max(gb, key=pick_key), max((r for k, v in logs.items() if k.startswith('lr') for r in v), key=pick_key)
    m = json.loads((ART / f"model-{pick_gb['arm']}.json").read_text())
    m.update(n_trees=pick_gb['trees'], alpha=pick_gb['alpha'], trees=m['trees'][:pick_gb['trees']])
    (ART / 'model-gbdt.json').write_text(json.dumps(m))
    lr = json.loads((ART / f"model-{pick['arm']}.json").read_text())
    lr['alpha'] = pick['alpha']
    (ART / 'model.json').write_text(json.dumps(lr))
    out = dict(pick=pick, pick_gbdt=pick_gb, rule='per family: max dev recall AUC + 0.25 x all-kept AUC; LR ships',
               best_per_arm={k: max(v, key=pick_key) for k, v in logs.items()})
    (ART / 'train-log.json').write_text(json.dumps(out, indent=1))
    return out


FROZEN_RECIPE = dict(lr=dict(arm='lrg', alpha=0.5), gbdt=dict(arm='d4', trees=350, alpha=0.5))


def refit_phase():
    """Re-fit after a feature-code change with the recipe already chosen on dev by pick_phase (FROZEN_RECIPE):
    no selection, the dev log rows at the frozen settings are only reported."""
    logs = {k: json.loads((ART / f"log-{v['arm']}.json").read_text()) for k, v in FROZEN_RECIPE.items()}
    at = {k: next(r for r in logs[k] if all(r.get(f) == v for f, v in FROZEN_RECIPE[k].items())) for k in logs}
    lr = json.loads((ART / f"model-{FROZEN_RECIPE['lr']['arm']}.json").read_text())
    lr['alpha'] = FROZEN_RECIPE['lr']['alpha']
    (ART / 'model.json').write_text(json.dumps(lr))
    g = FROZEN_RECIPE['gbdt']
    m = json.loads((ART / f"model-{g['arm']}.json").read_text())
    m.update(n_trees=g['trees'], alpha=g['alpha'], trees=m['trees'][:g['trees']])
    (ART / 'model-gbdt.json').write_text(json.dumps(m))
    tl = json.loads((ART / 'train-log.json').read_text())
    out = dict(pick=at['lr'], pick_gbdt=at['gbdt'], best_per_arm={k: at[k] for k in at},
               rule='refit with the frozen recipe (no selection); ' + tl['rule'],
               previous_pick=tl.get('previous_pick', dict(pick=tl['pick'], pick_gbdt=tl['pick_gbdt'])))
    (ART / 'train-log.json').write_text(json.dumps(out, indent=1))
    return out


# --- eval (dev, dev-model subset, jev-overlap, edge suite, cost) ---------------------------------------
EDGE_KIND = {'tool_call': 'tool_use'}


def edge_texts(case):
    """Edge fixtures carry role/kind/tool as fields; render what LCC would show the live judge: a header on
    the first block of each message, none on the blocks that continue it (an oversized message split)."""
    return [(f"[m{b['msg']:04d} {b['role'] if b['role'] != 'tool' else 'user'} {EDGE_KIND.get(b['kind'], b['kind'])}"
             + (f" {b['tool']}" if b.get('tool') else '') + ']\n' if b['part'] == 0 else '') + b['text']
            for b in case['blocks']]


def judge_scores(judge, items):
    """{item_id: {block_id: score}} over candidate blocks, scoring each item from its full block list."""
    out = {}
    for it, texts in load_items([it['item_id'] for it in items]):
        sc = judge.score(it['goal'], texts)
        out[it['item_id']] = {b['id']: sc[j] for j, b in enumerate(it['blocks']) if not b['protected']}
    return out


BENCH = """
import json, resource, sys, time
t0 = time.perf_counter()
from research.specialist_v2 import Judge
j = Judge.load(sys.argv[1])
load_ms = (time.perf_counter() - t0) * 1000
rss0 = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
rows = []
for line in open(sys.argv[2]):
    d = json.loads(line)
    t = time.perf_counter(); j.score(d['goal'], d['texts']); rows.append((len(d['texts']), (time.perf_counter() - t) * 1000))
    del d
div = 1 << 20 if sys.platform == 'darwin' else 1 << 10
print(json.dumps(dict(load_ms=load_ms, rss_after_load_mb=rss0 / div,
                      peak_rss_mb=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / div, rows=rows)))
"""


def bench(model_path, items, n=40):
    """Latency / RSS of Judge in a fresh process (numpy + this module only), one item in memory at a time."""
    import os
    import subprocess
    import statistics
    # Fresh name, created 0600 atomically (no truncating a stale file, no following a symlink).
    import tempfile
    fd, tmp = tempfile.mkstemp(prefix='bench-items-', suffix='.jsonl', dir=ART)  # private: dev block text, owner-only and always removed
    tmp = Path(tmp)
    try:
        with os.fdopen(fd, 'w') as f:
            for k, (it, texts) in enumerate(load_items([it['item_id'] for it in items[:n]])):
                f.write(json.dumps(dict(goal=it['goal'], texts=texts), ensure_ascii=False) + '\n')
        path = os.pathsep.join([str(Path(__file__).resolve().parent.parent)]
                               + [p for p in sys.path if p.endswith('src')])
        env = dict(os.environ, PYTHONPATH=path, OMP_NUM_THREADS='1',
                   OPENBLAS_NUM_THREADS='1', VECLIB_MAXIMUM_THREADS='1')
        r = json.loads(subprocess.run([sys.executable, '-c', BENCH, str(model_path), str(tmp)], env=env,
                                      check=True, capture_output=True, text=True).stdout)
    finally:
        tmp.unlink(missing_ok=True)
    ms = [x[1] for x in r['rows']]
    nb = [x[0] for x in r['rows']]
    near400 = [m for b, m in r['rows'] if 250 <= b <= 600]
    q = lambda xs, p: sorted(xs)[max(0, math.ceil(p * len(xs)) - 1)]  # noqa: E731
    return dict(items=len(ms), blocks_median=statistics.median(nb), ms_median=round(statistics.median(ms), 1),
                ms_p90=round(q(ms, 0.9), 1), ms_max=round(max(ms), 1),
                ms_median_250_600_blocks=round(statistics.median(near400), 1) if near400 else None,
                n_250_600_blocks=len(near400), blocks_per_s=round(sum(nb) / (sum(ms) / 1000)),
                load_ms=round(r['load_ms']), rss_after_load_mb=round(r['rss_after_load_mb'], 1),
                peak_rss_mb=round(r['peak_rss_mb'], 1), load_avg_1m=round(os.getloadavg()[0], 1),
                model_file_kb=round(Path(model_path).stat().st_size / 1024))


def eval_phase():
    import os
    import random
    import statistics
    from research import edge_suite as es
    from research import matched_budget_v2 as mb
    os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1')
    judge, judge_gb = Judge.load(ART / 'model.json'), Judge.load(ART / 'model-gbdt.json')
    items, skip = mb.eligible_dev()
    groups = {it['item_id']: mb.evidence_groups(it) for it in items}
    arms = defaultdict(dict)
    for it in items:
        pairs = list(mb.texts_for(it).items())
        for a, sc in mb.cheap_scores(it['goal'], pairs, it['item_id']).items():
            arms[a][it['item_id']] = sc
    arms['specialist_v2'] = judge_scores(judge, items)
    arms['specialist_v2_gbdt'] = judge_scores(judge_gb, items)
    dev_curves, dev_ties = mb.evaluate(items, arms, groups)
    by_src = {a: mb.by_source(items, arms[a], groups) for a in ('recency', 'bm25', 'mechanical', 'specialist_v2')}
    by_cat = {}
    for cat in sorted({it.get('category') or 'unlabelled' for it in items}):
        sub = [it for it in items if (it.get('category') or 'unlabelled') == cat]
        if len(sub) >= 8:
            by_cat[cat] = dict(n=len(sub), **{a: mb.aggregate({it['item_id']: mb.item_metrics(
                it, arms[a][it['item_id']], groups=groups[it['item_id']]) for it in sub})['auc']['recall']
                for a in ('recency', 'bm25', 'specialist_v2')})
    paired = {}
    per = {a: {it['item_id']: mb.item_metrics(it, arms[a][it['item_id']], groups=groups[it['item_id']]) for it in items}
           for a in ('recency', 'bm25', 'specialist_v2')}
    for a in ('recency', 'bm25'):
        paired[a] = {str(b): dict(v2_higher=sum(per['specialist_v2'][k][b]['recall'] > per[a][k][b]['recall'] + 1e-9
                                                for k in per[a]),
                                  v2_lower=sum(per['specialist_v2'][k][b]['recall'] < per[a][k][b]['recall'] - 1e-9
                                               for k in per[a])) for b in mb.BUDGETS}
    # bootstrap over items: v2 minus each baseline, recall AUC
    rng = random.Random(SEED)
    aucs = {a: {k: mb.auc([(0, 1.0)] + [(b, per[a][k][b]['recall']) for b in mb.BUDGETS]) for k in per[a]} for a in per}
    ids = sorted(aucs['specialist_v2'])
    boot = {}
    for a in ('recency', 'bm25'):
        diffs = [aucs['specialist_v2'][k] - aucs[a][k] for k in ids]
        bs = sorted(statistics.mean(rng.choice(diffs) for _ in diffs) for _ in range(1000))
        boot[a] = dict(mean=round(statistics.mean(diffs), 4), ci95=[round(bs[24], 4), round(bs[974], 4)])
    # dev-model subset: items that have saved specialist-v1 scores
    v1 = {p.stem: json.loads(p.read_text())['scores'] for p in (mb.PRIVATE / 'scores' / 'specialist').glob('*.json')
          if not p.stem.startswith('_')}
    dm_items = [it for it in items if it['item_id'] in v1 and it['item_id'] in set(mb.model_ids(items))]
    dm_arms = {a: {it['item_id']: arms[a][it['item_id']] for it in dm_items} for a in arms}
    dm_arms['specialist_v1'] = {it['item_id']: v1[it['item_id']] for it in dm_items}
    dm_curves = mb.evaluate(dm_items, dm_arms, groups)[0] if dm_items else {}
    # jev-overlap: Jev / v1 / Laya from saved runs; v2 never trained on these lineage groups
    j_items, j_saved, j_skip = mb.jev_overlap()
    jg = {it['item_id']: mb.evidence_groups(it) for it in j_items}
    jsc = {a: dict(v) for a, v in j_saved.items()}
    for it in j_items:
        pairs = list(mb.texts_for(it).items())
        for a, sc in mb.cheap_scores(it['goal'], pairs, it['item_id']).items():
            jsc.setdefault(a, {})[it['item_id']] = sc
    jsc['specialist_v2'] = judge_scores(judge, j_items)
    jsc['specialist_v2_gbdt'] = judge_scores(judge_gb, j_items)
    j_curves = mb.evaluate(j_items, jsc, jg)[0]
    jev_per = {it['item_id']: mb.item_metrics(it, jsc['jev'][it['item_id']], groups=jg[it['item_id']]) for it in j_items}
    v2_per = {it['item_id']: mb.item_metrics(it, jsc['specialist_v2'][it['item_id']], groups=jg[it['item_id']])
              for it in j_items}
    j_paired = {str(b): dict(v2_higher=sum(v2_per[k][b]['recall'] > jev_per[k][b]['recall'] + 1e-9 for k in v2_per),
                             v2_lower=sum(v2_per[k][b]['recall'] < jev_per[k][b]['recall'] - 1e-9 for k in v2_per))
                for b in mb.BUDGETS}
    # edge suite
    cases = es.load_cases()
    edge = mb.edge_results()
    for name, jj in (('specialist_v2', judge), ('specialist_v2_gbdt', judge_gb)):
        sc = {c['id']: dict(zip([b['id'] for b in c['blocks']], jj.score(c['goal'], edge_texts(c)))) for c in cases}
        sm = es.summary(cases, es.run(cases, sc))
        edge[name] = {str(b): dict(passed=v['passed'], n=v['n'], failed=v['failed']) for b, v in sm.items()}
    cost = dict(specialist_v2=bench(ART / 'model.json', items), specialist_v2_gbdt=bench(ART / 'model-gbdt.json', items))
    model, gb = json.loads((ART / 'model.json').read_text()), json.loads((ART / 'model-gbdt.json').read_text())
    tl = json.loads((ART / 'train-log.json').read_text())
    res = dict(schema='specialist-v2/dev', labels='next-action-v2 strict USED, dev split only (test not opened)',
               model=dict(kind=model['kind'], alpha=model['alpha'], features=len(FEATURES), pick=tl['pick']),
               alternative=dict(kind='gbdt', depth=gb['depth'], trees=gb['n_trees'], alpha=gb['alpha'], pick=tl['pick_gbdt']),
               train=json.loads((ART / 'features-meta.json').read_text()),
               train_best_per_arm=tl['best_per_arm'], train_rule=tl['rule'],
               dev=dict(items=len(items), excluded=dict(skip), curves=dev_curves, tie_random_auc=dev_ties,
                        by_source=by_src, by_category_recall_auc=by_cat, paired_recall=paired,
                        bootstrap_recall_auc_diff=boot),
               dev_model=dict(items=len(dm_items), curves=dm_curves),
               jev_overlap=dict(items=len(j_items), excluded=dict(j_skip), curves=j_curves, paired_recall_vs_jev=j_paired,
                                v2_trained_on_these_groups=False),
               edge_suite=edge, cost=cost)
    (ART / 'dev-results.json').write_text(json.dumps(res, indent=1))
    (OUT / 'dev-results.json').write_text(json.dumps(res, indent=1) + '\n')
    (OUT / 'DEV_RESULTS.md').write_text(render_md(res))
    return {k: res[k] for k in ('model', 'cost')}


def render_md(r):
    from research.matched_budget_v2 import curve_table
    arms = ('specialist_v2', 'specialist_v2_gbdt', 'specialist_v1', 'jev', 'recency', 'bm25', 'mechanical', 'laya', 'random')
    d, dm, jo, e, c = r['dev'], r['dev_model'], r['jev_overlap'], r['edge_suite'], r['cost']
    A = lambda cur, a: cur[a]['auc']['recall'] if a in cur else None  # noqa: E731
    K = lambda cur, a: cur[a]['auc']['all_kept'] if a in cur else None  # noqa: E731
    v2 = c['specialist_v2']
    L = ['# Specialist v2: dev results (next-action labels v2)', '',
         'Generated by `python -m research.specialist_v2 eval`; counts and metrics only, no session text. '
         'The test split was not opened; every number here is DEV (tuning) data, so it is optimistic for the '
         'chosen configuration.', '',
         '## Bottom line', '',
         '- `specialist_v2` = the shipped model (logistic regression, 50 features, 4 KB). `specialist_v2_gbdt` = the '
         'gradient-boosted alternative: about 1 pt higher on dev recall but it fits the label prior and fails the edge '
         'suite (see Model). Choosing LR over GBDT looked at the edge suite, so those two edge rows are not held-out.',
         f"- Dev, all {d['items']} eligible items: specialist v2 recall AUC {A(d['curves'], 'specialist_v2'):.3f} / "
         f"all-kept AUC {K(d['curves'], 'specialist_v2'):.3f}; recency {A(d['curves'], 'recency'):.3f} / "
         f"{K(d['curves'], 'recency'):.3f}, BM25 {A(d['curves'], 'bm25'):.3f} / {K(d['curves'], 'bm25'):.3f}, mechanical "
         f"{A(d['curves'], 'mechanical'):.3f} / {K(d['curves'], 'mechanical'):.3f}, random {A(d['curves'], 'random'):.3f}.",
         '- Paired bootstrap over dev items (v2 minus baseline, per-item recall AUC, 1000 resamples): ' + '; '.join(
             f"{a} {v['mean']:+.4f} [{v['ci95'][0]:+.4f}, {v['ci95'][1]:+.4f}]" for a, v in d['bootstrap_recall_auc_diff'].items()) + '.',
         (f"- Dev-model subset ({dm['items']} items with saved v1 scores): v2 {A(dm['curves'], 'specialist_v2'):.3f} vs "
          f"specialist v1 {A(dm['curves'], 'specialist_v1'):.3f}, recency {A(dm['curves'], 'recency'):.3f}."
          if dm['curves'] else '- Dev-model subset: no saved v1 scores.'),
         f"- jev-overlap ({jo['items']} items; v2 never trained on their lineage groups): v2 recall AUC "
         f"{A(jo['curves'], 'specialist_v2'):.3f} vs Jev {A(jo['curves'], 'jev'):.3f}; all-kept AUC "
         f"{K(jo['curves'], 'specialist_v2'):.3f} vs {K(jo['curves'], 'jev'):.3f}. n = {jo['items']} is small: read the paired "
         'counts, not only the AUC.',
         '- Gate from BASELINES.md (beat Jev on jev-overlap, beat recency and BM25 on dev, pass more edge cases than '
         'every other arm): jev-overlap ' + ('PASS' if A(jo['curves'], 'specialist_v2') > A(jo['curves'], 'jev') else 'FAIL')
         + '; dev ' + ('PASS' if A(d['curves'], 'specialist_v2') > max(A(d['curves'], 'recency'), A(d['curves'], 'bm25'))
                       else 'FAIL') + '; edge ' + ', '.join(
             f"{b}%: {e['specialist_v2'][b]['passed']} vs best other {best} ("
             + ('more' if e['specialist_v2'][b]['passed'] > best else 'tied' if e['specialist_v2'][b]['passed'] == best else 'fewer')
             + ')' for b in ('30', '50', '70')
             for best in [max(s[b]['passed'] for a, s in e.items() if a not in ('oracle', 'specialist_v2'))])
         + '.',
         '- Edge suite (35 cases, pass k/35 at 30/50/70%): ' + '; '.join(
             f"{a} {s['30']['passed']}/{s['50']['passed']}/{s['70']['passed']}" for a, s in e.items()) + '.',
         f"- Cost (fresh process: numpy + LCC's own mechanical pass, 1 thread): median {v2['ms_median']} ms per item (median "
         f"{v2['blocks_median']} blocks; {v2['ms_median_250_600_blocks']} ms on the {v2['n_250_600_blocks']} items with "
         f"250-600 blocks), p90 {v2['ms_p90']} ms, max {v2['ms_max']} ms; peak RSS {v2['peak_rss_mb']} MB; model file "
         f"{v2['model_file_kb']} KB; load {v2['load_ms']} ms. Machine load average {v2['load_avg_1m']} on 10 cores.", '',
         '## Model', '',
         f"- Shipped: weighted logistic regression over {r['model']['features']} per-block features (position and message "
         'recency, block kind and tool group, BM25 vs goal and vs the last 3 text turns, identifier/path overlap with '
         'goal and recent turns, later references, duplicates, re-reads, error/git/code markers, goal shape, and LCC\'s '
         f"own mechanical overlap + protection flags), size penalty alpha {r['model']['alpha']} (score = logit - alpha x "
         f"log chars). Target: USED or goal-shared (`lrg`). Dev pick: {json.dumps(r['model']['pick'])}.",
         f"- Alternative: GBDT depth {r['alternative']['depth']}, {r['alternative']['trees']} trees, alpha "
         f"{r['alternative']['alpha']}; dev pick {json.dumps(r['alternative']['pick'])}.",
         f"- Selection rule: {r.get('train_rule', '-')}. Dev at the chosen config per family (lr / lrg = LR on USED / "
         'USED-or-goal-shared; d4 / d4g / gbdt = GBDT depth 4): '
         + '; '.join(f"{k} recall {v['recall']:.4f} all-kept {v['all_kept']:.4f} (alpha {v['alpha']})"
                     for k, v in sorted(r['train_best_per_arm'].items())) + '. Depth 6 was tried in an earlier feature '
         'set and was no better than depth 4 and slower to train.',
         f"- Training rows / items: {json.dumps(r['train'])}. Train excludes items forked from dev (label-v2 "
         'quarantine) and the jev-overlap lineage groups and their forks; negatives subsampled at 25% and re-weighted; '
         'every item weighs the same.',
         '- No embedding feature (option b not taken): the only <= 30M-parameter model in the local HF cache is the '
         'MiniLM-L6 cross-encoder (22M, safetensors only, no ONNX export; onnxruntime is not in the LCC venv). Running it '
         'needs torch + transformers, whose import alone measured 235 MB peak RSS here before loading 87 MB of weights, '
         'so it cannot fit the 300 MB budget, and it would score ~400 goal-block pairs per item. No downloads allowed.', '',
         '## Dev, all eligible items', '',
         *curve_table(d['curves'], arms), '',
         'Random tie-break AUC: ' + '; '.join(f"{a} recall {t['recall']:.3f} / all-kept {t['all_kept']:.3f}"
                                              for a, t in d['tie_random_auc'].items()) + '.', '',
         'Recall AUC by source: ' + '; '.join(f"{a}: " + ', '.join(f"{s} {v['auc']['recall']:.3f} (n={v['n']})"
                                                                     for s, v in bs.items()) for a, bs in d['by_source'].items()) + '.', '',
         'Recall AUC by request category (>= 8 items): ' + '; '.join(
             f"{k} (n={v['n']}) v2 {v['specialist_v2']:.3f} / recency {v['recency']:.3f} / bm25 {v['bm25']:.3f}"
             for k, v in d['by_category_recall_auc'].items()) + '.', '',
         'Paired items (USED recall, v2 higher / lower): ' + '; '.join(
             f"vs {a}: " + ', '.join(f"{b}% +{v['v2_higher']}/-{v['v2_lower']}" for b, v in p.items())
             for a, p in d['paired_recall'].items()) + '.', '']
    if dm['curves']:
        L += [f"## Dev-model subset ({dm['items']} items)", '', *curve_table(dm['curves'], arms), '']
    L += [f"## jev-overlap ({jo['items']} items; excluded {jo['excluded']})", '', *curve_table(jo['curves'], arms), '',
          'Paired items vs Jev (USED recall, v2 higher / lower): ' + ', '.join(
              f"{b}% +{v['v2_higher']}/-{v['v2_lower']}" for b, v in jo['paired_recall_vs_jev'].items()) + '.', '',
          '## Edge suite (35 synthetic cases, size-balanced fixtures)', '',
          '| arm | 30% | 50% | 70% |', '|---|---|---|---|',
          *[f"| {a} | {s['30']['passed']} | {s['50']['passed']} | {s['70']['passed']} |" for a, s in e.items()], '',
          'v2 fails @50%: ' + (', '.join(e['specialist_v2']['50'].get('failed', [])) or '-') + '.', '',
          '## Cost', '', '| arm | ms median | p90 | max | blocks/s | peak RSS MB | model KB |', '|---|---|---|---|---|---|---|',
          *[f"| {a} | {x['ms_median']} | {x['ms_p90']} | {x['ms_max']} | {x['blocks_per_s']} | {x['peak_rss_mb']} | "
            f"{x['model_file_kb']} |" for a, x in c.items()], '',
          'Specialist v1 (exp02 ModernBERT head): see BASELINES.md cost table (~31 s median per item, 1.66 GB RSS).', '',
          '## Limits', '',
          '- Labels are rule-based next-action evidence (v2 relabel), not human judgement; they lean recent.',
          '- Dev was used for model selection (depth, trees, alpha): the dev numbers of the chosen model are optimistic. '
          'The frozen test split is the honest check and has not been run.',
          '- jev-overlap has few items; Jev scores are saved v0.1 runs (no new remote calls).',
          '- The edge suite is synthetic and single-author gold; v2 never trained on it.',
          '- Latency measured on a shared, heavily loaded machine; treat it as an upper bound.', '']
    return '\n'.join(L)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('phase', choices=('features', 'train', 'pick', 'refit', 'eval'))
    ap.add_argument('--arm', default='d6', help="train: 'lr' or 'd<depth>'")
    a = ap.parse_args(argv)
    if a.phase == 'features':
        out = features_phase()
    elif a.phase == 'train':
        out = train_phase(a.arm)
    elif a.phase == 'pick':
        out = pick_phase()
    elif a.phase == 'refit':
        out = refit_phase()
    else:
        out = eval_phase()
    print(json.dumps(out, indent=1)[:4000])


if __name__ == '__main__':
    sys.exit(main())
