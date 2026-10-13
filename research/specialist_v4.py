"""Specialist v4: v3 plus cheap supersession / contradiction / coreference / rule features and a small
auxiliary model distilled from Claude Opus 5.5 keep-judgements on TRAIN sessions.

Why: v3 fails the synthetic edge cases that need "old value later changed", "two sources disagree", "that
error" and "rule / exception / reversal" reasoning, where Opus passes 35/35/35 (LLM_ARMS_RESULTS.md). v3's
50 features carry none of those relations. v4 adds EXTRA (regex / key bookkeeping, CPU, no new deps) and
an LR "teacher" fitted on Opus soft labels for targeted train blocks; the selection rule is pre-declared in
specialist-v1/V4_SELECTION_RULE.md (committed before dev was scored).

Data rules: Opus labels only TRAIN items that v2 trained on (cache/train/<id>.npz exists: never dev, never
quarantined dev forks, never jev-overlap lineage groups); the spent test split and the post-2026-10-12
held-out set are never read. train_guard() enforces it for anything sent to the CLI.

Phases (private artifacts under ART; the repo gets code and counts only):
    extras  -> ART/extras-{train,dev}.npz (EXTRA columns for the v2 cached rows) + ART/patterns-train.json
    subset  -> ART/train-subset.json (frozen block lists per item for llm_judge_arm --set train)
    train   -> ART/model-lrg4.json (next-action LR on v2+EXTRA), ART/model-teacher.json (LR on Opus labels)
    select  -> ART/select-log.json, ART/model.json (pre-declared rule)
    eval    -> ART/dev-results.json, OUT/v4-dev-results.json

    PYTHONPATH=/Users/Master/.lcc/bench/real-context-v0/lcc-main/src:/Users/Master/Downloads/LCC-judge \\
    /Users/Master/LCC/.venv/bin/python -m research.specialist_v4 {extras|subset|train|select|eval}
"""
import argparse
import json
import math
import random
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

from research import specialist_v2 as s2
from research import specialist_v3 as s3

ART = Path('/Users/Master/.lcc/bench/specialist-v4')
OUT = s2.OUT
SEED = 20261013

RULE_RE = re.compile(r"\b(?:never|always|do not|don't|must|only|rule|policy|unless|except|nunca|sempre|n[aã]o "
                     r"(?:mand|envi|fa[cç]|us|commit|push|apag|mex)\w*|regra|s[oó] (?:quando|se|na|no|depois)|"
                     r"apenas|proibid\w*|exceto|a menos)\b", re.I)
REVERSAL_RE = re.compile(r"\b(?:actually|instead|revert\w*|undo|scratch that|never ?mind|changed my mind|no wait|"
                         r"not anymore|na verdade|em vez|ao inv[eé]s|desfaz\w*|esquece|mudei de ideia|volta (?:pro|para|a))\b",
                         re.I)
SUMMARY_RE = re.compile(r"\b(?:summary|resumo|decisions?|decis[aãoõ]\w*|pending|pendente\w*|next steps?|"
                        r"pr[oó]ximo passo|todo|roadmap|status)\b|\[(?:done|x| )\]", re.I)
REF_START_RE = re.compile(r"^\s*(?:this|that|it|these|those|isso|isto|esse|essa|este|esta|aquilo|disso|nisso)\b", re.I)
REF_ANY_RE = re.compile(r"\b(?:isso|disso|nisso|esse erro|essa? (?:mensagem|falha)|that (?:error|one|issue)|"
                        r"this (?:error|one|issue)|it again|de novo|o mesmo|the same)\b", re.I)
VALUE_RE = re.compile(r"(?:=|:|\bis\b|\bé\b|\bwas\b)\s*([-+]?\d[\d.,]*\s?(?:%|[A-Za-z/]{1,9})?)")
SUBJ_RE = re.compile(r"[A-Za-z][\w .\-/]*$")
EXTRA = ('rule_marker', 'user_rule', 'reversal_marker', 'reversal_near', 'summary_marker', 'value_facts',
         'value_conflict', 'value_changed_later', 'latest_value_holder', 'ref_start', 'ref_antecedent',
         'early_user_turn', 'reread_path', 'path_edited_later')
FEATURES = tuple(s2.FEATURES) + EXTRA
N2 = len(s2.FEATURES)


def values(body, cap=60):
    """{subject: value} for 'subject = / : / is <number>' facts (subject = last 3 words of its last sentence)."""
    out = {}
    for m in VALUE_RE.finditer(body[:20000]):  # anchored on the operator: no backtracking over every letter
        lo = max(0, m.start() - 41)
        sm = SUBJ_RE.search(body[lo:m.start()].rstrip())
        if sm is None:
            continue
        pre = sm.group(0)
        if lo and sm.start() == 0 and body[lo - 1].isalnum() and ' ' in pre:
            pre = pre.split(' ', 1)[1]  # window cut a word: drop the partial one
        subj = ' '.join(re.findall(r'\w+', re.split(r'[.;]\s', pre)[-1].lower())[-3:])
        if len(subj) >= 3 and not subj.isdigit():
            out.setdefault(subj, m.group(1).strip().rstrip('.,'))
        if len(out) >= cap:
            break
    return out


def extras(goal, texts, ctx=None):
    """EXTRA columns (n, len(EXTRA)) float32. ctx = s2.featurize's intermediates (meta, bodies, ks), or None to
    recompute them. Only trusted render headers (s2.block_meta) set role / kind / tool."""
    n = len(texts)
    if ctx is None:
        ctx = dict(meta=s2.block_meta(texts), bodies=[s2.HEADER_RE.sub('', t).strip() for t in texts])
        ctx['ks'] = [s2.keys(b) for b in ctx['bodies']]
    meta, bodies, ks = ctx['meta'], ctx['bodies'], ctx['ks']
    E = np.zeros((n, len(EXTRA)), np.float32)
    col = {f: j for j, f in enumerate(EXTRA)}
    is_text = [m[2] == 'text' and m[1] in ('user', 'assistant') for m in meta]
    grp = [s2.tool_group(m[3]) for m in meta]
    rev = np.zeros(n, bool)
    user_seen = 0
    vals = [values(b) for b in bodies]
    holders = defaultdict(list)  # subject -> [(block, value)]
    for i, v in enumerate(vals):
        for s, x in v.items():
            holders[s].append((i, x))
    first_rw, last_edit = {}, {}
    for i in range(n):
        if grp[i] in ('read', 'edit'):
            for x in ks[i]:
                if '/' in x or '.' in x:
                    first_rw.setdefault(x, i)
                    if grp[i] == 'edit' and meta[i][2] == 'tool_use':
                        last_edit[x] = i
    for i in range(n):
        b = bodies[i]
        r = len(RULE_RE.findall(b[:20000]))
        E[i, col['rule_marker']] = math.log1p(r)
        if is_text[i]:
            rev[i] = bool(REVERSAL_RE.search(b[:4000]))
            E[i, col['reversal_marker']] = rev[i]
            if meta[i][1] == 'user':
                E[i, col['user_rule']] = r > 0
                E[i, col['early_user_turn']] = user_seen < 3
                if meta[i][4]:
                    user_seen += 1
            E[i, col['ref_start']] = bool(REF_START_RE.match(b))
        E[i, col['summary_marker']] = math.log1p(len(SUMMARY_RE.findall(b[:20000])))
        E[i, col['value_facts']] = math.log1p(len(vals[i]))
        paths = [x for x in ks[i] if '/' in x or '.' in x]
        E[i, col['reread_path']] = any(first_rw.get(x, i) < i for x in paths) if grp[i] in ('read', 'edit') else 0
        E[i, col['path_edited_later']] = any(last_edit.get(x, -1) > i for x in paths)
    for hs in holders.values():  # each block holds a subject at most once; O(holders) per subject
        cnt = Counter(x for _, x in hs)
        if len(cnt) < 2:
            continue
        for i, x in hs:
            E[i, col['value_conflict']] = 1  # some other block holds a different value (len(cnt) >= 2)
        later = []  # up to 2 distinct values seen after position k
        for i, x in reversed(hs):
            if any(x2 != x for x2 in later):
                E[i, col['value_changed_later']] = 1
            if x not in later and len(later) < 2:
                later.append(x)
        i_last, x_last = hs[-1]
        E[i_last, col['latest_value_holder']] = any(x2 != x_last for _, x2 in hs[:-1])
    for i in range(n):
        lo, hi = max(0, i - 3), min(n, i + 4)
        E[i, col['reversal_near']] = rev[lo:hi].any() and not rev[i]
        # antecedent: a later text turn (within 3 blocks) that opens with a pronoun or says "that error" / "isso"
        for j in range(i + 1, min(n, i + 4)):
            if is_text[j] and (E[j, col['ref_start']] or (len(bodies[j]) < 300 and REF_ANY_RE.search(bodies[j]))):
                E[i, col['ref_antecedent']] = 1 / (j - i)
                break
    return E


def featurize(goal, texts):
    ctx = {}
    X = s2.featurize(goal, texts, ctx)
    return np.hstack([X, extras(goal, texts, ctx)])


# --- targeted train subset for the Opus teacher -----------------------------------------------------------
PATTERNS = ('supersession', 'value_change', 'coreference', 'reversal')


def patterns(X):
    """Pattern flags per row of a v4 feature matrix -> {pattern: bool array}."""
    c = {f: j for j, f in enumerate(FEATURES)}
    return dict(supersession=(X[:, c['superseded_path']] > 0) | (X[:, c['reread_path']] > 0) | (X[:, c['path_edited_later']] > 0),
                value_change=(X[:, c['value_conflict']] > 0),
                coreference=(X[:, c['ref_antecedent']] > 0) | (X[:, c['ref_start']] > 0),
                reversal=(X[:, c['reversal_marker']] > 0) | (X[:, c['reversal_near']] > 0))


def train_ids():
    """Items v2 trained on: cached train rows (excludes dev, quarantined dev forks, jev-overlap groups)."""
    return sorted(p.stem for p in (s2.ART / 'cache' / 'train').glob('*.npz') if not p.stem.endswith('.tmp'))


def train_guard(ids, splits=None, quarantine=None, jev=None):
    """Refuse anything that is not a plain train item. splits: {item_id: split}; quarantine: dev-fork ids;
    jev: {'items': [...], 'groups': [...]} plus each item's group via splits_groups (optional)."""
    if splits is None:
        sp = s2.split_of()
        splits, quarantine = sp['items'], set(sp['train_quarantined_dev_overlap'])
        jev = s2.jev_overlap_ids()
    bad = [i for i in ids if splits.get(i) != 'train' or i in quarantine or i in set(jev['items'])]
    if bad:
        raise SystemExit(f'train_guard: {len(bad)} non-train / quarantined / jev item(s) refused')
    return list(ids)


def extras_phase(splits=('train', 'dev')):
    """EXTRA columns for the cached v2 rows of every train / dev item (row order = features-<split>.npz order)
    and per-item pattern counts over candidate blocks (train only)."""
    ART.mkdir(parents=True, exist_ok=True, mode=0o700)
    out, pats = {}, {}
    for name in splits:
        D = np.load(s2.ART / f'features-{name}.npz')
        order = list(dict.fromkeys(D['item'].tolist()))
        rows = defaultdict(list)
        for r, iid in enumerate(D['item']):
            rows[iid].append(r)
        E = np.zeros((len(D['item']), len(EXTRA)), np.float32)
        t0 = time.time()
        for k, (it, texts) in enumerate(s2.load_items(order)):
            iid = it['item_id']
            Ei = extras(it['goal'], texts)
            E[rows[iid]] = Ei[D['block'][rows[iid]]]
            if name == 'train':
                cand = [j for j, b in enumerate(it['blocks']) if not b['protected']]
                P = patterns(np.hstack([np.zeros((len(texts), N2), np.float32), Ei])[cand])
                pats[iid] = dict(n=len(cand), **{p: int(v.sum()) for p, v in P.items()})
            if k % 200 == 0:
                print(name, k, len(order), round(time.time() - t0), flush=True)
        np.save(ART / f'extras-{name}.npy', E)
        out[name] = dict(rows=len(E), items=len(order), nonzero={f: int((E[:, j] != 0).sum()) for j, f in enumerate(EXTRA)})
    if pats:
        (ART / 'patterns-train.json').write_text(json.dumps(pats))
    (ART / 'extras-meta.json').write_text(json.dumps(out, indent=1))
    return out


def subset_phase(max_calls=1500, cap=32, fill=24):
    """Frozen targeted subset: train items with the rarer patterns first (value_change, coreference, reversal;
    supersession is common), up to `cap` candidate blocks per item (pattern blocks + 1 neighbour each side + the
    last 3 text turns, random fill to `fill`, seeded random sample down to `cap`), until the batch count reaches
    max_calls. Written once."""
    from research import llm_judge_arm as lj
    p = ART / 'train-subset.json'
    if p.exists():
        raise SystemExit(f'{p} exists (frozen); delete it by hand to rebuild')
    pats = json.loads((ART / 'patterns-train.json').read_text())
    rng = random.Random(SEED)
    rare = ('value_change', 'coreference', 'reversal')
    ids = train_guard(sorted(pats))
    rng.shuffle(ids)
    ids.sort(key=lambda i: -(sum(pats[i][r] > 0 for r in rare) + 0.5 * (pats[i]['supersession'] > 0)))
    prio = ids[:600]
    per = {}
    for it, texts in s2.load_items(prio):
        cand = [j for j, b in enumerate(it['blocks']) if not b['protected']]
        X = featurize(it['goal'], texts)[cand]
        P = patterns(X)
        meta = s2.block_meta(texts)
        irng = random.Random(f"{SEED}:{it['item_id']}")
        pick = set()
        for name in ('value_change', 'coreference', 'reversal', 'supersession'):
            hit = np.flatnonzero(P[name]).tolist()
            irng.shuffle(hit)
            for h in hit[:6 if name == 'supersession' else 8]:
                pick.update(k for k in (h - 1, h, h + 1) if 0 <= k < len(cand))
        txt = [k for k, j in enumerate(cand) if meta[j][2] == 'text']
        pick.update(txt[-3:])
        rest = [k for k in range(len(cand)) if k not in pick]
        irng.shuffle(rest)
        pick.update(rest[:max(0, fill - len(pick))])
        pick = sorted(irng.sample(sorted(pick), cap)) if len(pick) > cap else sorted(pick)
        bids = [it['blocks'][cand[k]]['id'] for k in pick]
        per[it['item_id']] = (bids, len(lj.batches([(b, texts[cand[k]]) for b, k in zip(bids, pick)])),
                              it.get('source', '?'))
    chosen, calls, srcs = {}, 0, Counter()
    for iid in prio:  # priority order
        if calls >= max_calls:
            break
        chosen[iid] = per[iid][0]
        calls += per[iid][1]
        srcs[per[iid][2]] += 1
    p.write_text(json.dumps(dict(seed=SEED, max_calls=max_calls, cap=cap, est_calls=calls, items=chosen)))
    p.chmod(0o600)
    return dict(items=len(chosen), est_calls=calls, by_source=dict(srcs))


def train_set():
    """[(item_id, goal, [(block_id, text)])] for llm_judge_arm --set train (frozen subset, guarded)."""
    sub = json.loads((ART / 'train-subset.json').read_text())['items']
    train_guard(list(sub))
    out = {}
    for it, texts in s2.load_items(list(sub)):
        idx = {b['id']: j for j, b in enumerate(it['blocks'])}
        out[it['item_id']] = (it['item_id'], it['goal'], [(b, texts[idx[b]]) for b in sub[it['item_id']]])
    return [out[i] for i in sub]  # subset (priority) order


# --- models ---------------------------------------------------------------------------------------------
def member_raw(model, X):
    """Logit of one member on a v4 matrix (v2 members use the first N2 columns)."""
    Xm = X[:, :len(model['features'])]
    if model['kind'] == 'lr':
        return s2.predict(model, Xm)
    s = np.full(len(X), model['base'])
    r = np.arange(len(X))
    for t in model['trees'][:model.get('n_trees', len(model['trees']))]:
        s += s2._walk(s2._flat(t), Xm, r)
    return s


class Judge:
    """model json: {kind: 'v4', members: [model, ...], teacher: model | None, beta, alpha, k_goal, k_err, bonus}.
    Judge.load(path).score(goal, texts) -> [float], higher = keep."""

    def __init__(self, model):
        self.model = model
        self.trees = {}
        for k, m in enumerate(model['members']):
            if m['kind'] != 'lr':
                self.trees[k] = [s2._flat(t) for t in m['trees'][:m.get('n_trees', len(m['trees']))]]

    @classmethod
    def load(cls, path=None):
        return cls(json.loads(Path(path or ART / 'model.json').read_text()))

    def raw(self, X):
        out = np.zeros(len(X))
        r = np.arange(len(X))
        for k, m in enumerate(self.model['members']):
            if m['kind'] == 'lr':
                out += s2.predict(m, X[:, :len(m['features'])])
            else:
                s = np.full(len(X), m['base'])
                for flat in self.trees[k]:
                    s += s2._walk(flat, X, r)
                out += s
        out /= len(self.model['members'])
        if self.model.get('teacher') and self.model['beta']:
            out += self.model['beta'] * s2.predict(self.model['teacher'], X)
        return out

    def score_x(self, X):
        m = self.model
        return (self.raw(X) - m['alpha'] * X[:, s3.LC] + m['bonus'] * s3.floor_mask(X, m['k_goal'], m['k_err'])).tolist()

    def score(self, goal, texts):
        if not texts:
            return []
        return self.score_x(featurize(goal, texts))


def train_matrices():
    T = np.load(s2.ART / 'features-train.npz')
    return T, np.hstack([T['X'], np.load(ART / 'extras-train.npy')])


def teacher_rows():
    """Opus-labelled train blocks -> (X, soft y, w); features from the full item (live featurize)."""
    from research import llm_judge_arm as lj
    sc = lj.scores('opus', 'train')
    train_guard(list(sc))
    Xs, ys, ws, n_items = [], [], [], 0
    for it, texts in s2.load_items(sorted(sc)):
        idx = {b['id']: j for j, b in enumerate(it['blocks'])}
        lab = [(idx[b], v) for b, v in sc[it['item_id']].items() if v is not None]
        if not lab:
            continue
        X = featurize(it['goal'], texts)
        rows = [j for j, _ in lab]
        Xs.append(X[rows])
        ys.append(np.array([v for _, v in lab], np.float32))
        ws.append(np.full(len(rows), 1 / len(rows)))
        n_items += 1
    return np.vstack(Xs), np.concatenate(ys), np.concatenate(ws), n_items


def train_phase(part='all'):
    """lrg4: v2's lrg recipe on 64 features (train rows). teacher: LR on Opus soft labels (train subset)."""
    meta = json.loads((ART / 'train-meta.json').read_text()) if (ART / 'train-meta.json').exists() else {}
    if part in ('all', 'lrg4'):
        T, X = train_matrices()
        y = np.maximum(T['y'], T['goal_shared'])
        lrg4 = dict(s2.fit_lr(X, y, T['w']), features=list(FEATURES), alpha=0.5)
        (ART / 'model-lrg4.json').write_text(json.dumps(lrg4))
        meta.update(lrg4_rows=len(y), lrg4_extra_coef=dict(zip(EXTRA, np.round(lrg4['beta'][N2:], 3).tolist())))
    if part in ('all', 'teacher'):
        Xt, yt, wt, n_items = teacher_rows()
        teacher = dict(s2.fit_lr(Xt, yt, wt), features=list(FEATURES))
        (ART / 'model-teacher.json').write_text(json.dumps(teacher))
        pt = 1 / (1 + np.exp(-s2.predict(teacher, Xt)))
        meta.update(teacher_rows=len(yt), teacher_items=n_items, opus_mean=round(float(yt.mean()), 3),
                    opus_ge_05=round(float((yt >= 0.5).mean()), 3),
                    teacher_fit_corr=round(float(np.corrcoef(pt, yt)[0, 1]), 3),
                    teacher_top_coef=sorted(zip(FEATURES, np.round(teacher['beta'], 3).tolist()),
                                            key=lambda t: -abs(t[1]))[:12])
    (ART / 'train-meta.json').write_text(json.dumps(meta, indent=1))
    return meta


BASES = ('v3', 'v3n')
BETAS = (0.0, 0.25, 0.5, 1.0, 2.0)


def build(base, beta):
    v2lr = json.loads((s2.ART / 'model.json').read_text())
    v2gb = json.loads((s2.ART / 'model-gbdt.json').read_text())
    members = [v2lr, v2gb] if base == 'v3' else [json.loads((ART / 'model-lrg4.json').read_text()), v2gb]
    teacher = json.loads((ART / 'model-teacher.json').read_text()) if beta else None
    return dict(kind='v4', base=base, members=members, teacher=teacher, beta=beta, alpha=0.5, k_goal=1, k_err=2,
                bonus=3.0)


def edge_counts(cases, judge):
    from research import edge_suite as es
    sc = {c['id']: dict(zip([b['id'] for b in c['blocks']], judge.score(c['goal'], s2.edge_texts(c)))) for c in cases}
    return es.summary(cases, es.run(cases, sc))


def select_phase():
    """V4_SELECTION_RULE.md, verbatim."""
    from itertools import product

    from research import edge_suite as es
    from research import matched_budget_v2 as mb
    D = np.load(s2.ART / 'features-dev.npz')
    X = np.hstack([D['X'], np.load(ART / 'extras-dev.npy')])
    items, _ = mb.eligible_dev()
    groups = {it['item_id']: mb.evidence_groups(it) for it in items}
    spans = defaultdict(list)
    for r, iid in enumerate(D['item']):
        spans[iid].append(r)
    cases = es.load_cases()

    def dev_auc(j):
        sc = np.zeros(len(X))
        for rs in spans.values():
            sc[rs] = j.score_x(X[rs])
        return s2.curve(items, s2.item_scores(items, D, sc), groups)['auc']

    log = []
    for base, beta in product(BASES, BETAS):
        j = Judge(build(base, beta))
        e = edge_counts(cases, j)
        r = dict(base=base, beta=beta, **dev_auc(j), edge={str(b): e[b]['passed'] for b in es.BUDGETS})
        log.append(r)
        print(r, flush=True)
    v3 = next(r for r in log if r['base'] == 'v3' and r['beta'] == 0)
    for r in log:
        r['eligible'] = (r['recall'] >= v3['recall'] and r['all_kept'] >= v3['all_kept']
                         and all(r['edge'][b] >= v3['edge'][b] for b in r['edge']))
        r['edge_total'] = sum(r['edge'].values())
    ok = [r for r in log if r['eligible']]
    pick = max(ok, key=lambda r: (r['edge_total'], s2.pick_key(r)))
    adopt = pick['edge_total'] > v3['edge_total']
    out = dict(rule='V4_SELECTION_RULE.md', v3=v3, pick=pick, adopt=adopt, n_eligible=len(ok), log=log)
    (ART / 'select-log.json').write_text(json.dumps(out, indent=1))
    (ART / 'model.json').write_text(json.dumps(build(pick['base'], pick['beta'])))
    return {k: v for k, v in out.items() if k != 'log'}


# --- eval ---------------------------------------------------------------------------------------------
V4_BENCH = s2.BENCH.replace('from research.specialist_v2 import Judge', 'from research.specialist_v4 import Judge')


def bench(model_path, items):
    orig = s2.BENCH
    s2.BENCH = V4_BENCH
    try:
        return s2.bench(model_path, items, n=len(items))
    finally:
        s2.BENCH = orig


def grid_ci():
    """Every grid config vs v3 on dev (select's row-based scores): per-item AUC paired group bootstrap; edge per
    category. Diagnostic only: the pick is already fixed by select_phase."""
    from research import edge_suite as es
    from research import matched_budget_v2 as mb
    D = np.load(s2.ART / 'features-dev.npz')
    X = np.hstack([D['X'], np.load(ART / 'extras-dev.npy')])
    items, _ = mb.eligible_dev()
    groups = {it['item_id']: mb.evidence_groups(it) for it in items}
    spans = defaultdict(list)
    for r, iid in enumerate(D['item']):
        spans[iid].append(r)
    cases = es.load_cases()
    per, out = {}, {}
    for base in BASES:
        for beta in BETAS:
            j = Judge(build(base, beta))
            sc = np.zeros(len(X))
            for rs in spans.values():
                sc[rs] = j.score_x(X[rs])
            isc = s2.item_scores(items, D, sc)
            pm = {it['item_id']: mb.item_metrics(it, isc[it['item_id']], groups=groups[it['item_id']]) for it in items}
            name = f'{base}_b{beta}'
            per[name] = {m: {k: mb.auc([(0, 1.0)] + [(b, float(pm[k][b][m])) for b in mb.BUDGETS]) for k in pm}
                         for m in ('recall', 'all_kept')}
            e = edge_counts(cases, j)
            out[name] = dict(edge={str(b): e[b]['passed'] for b in es.BUDGETS},
                             edge_by_category={str(b): e[b]['by_category'] for b in es.BUDGETS})
    for name in out:
        out[name].update({f'{m}_vs_v3': s3.group_bootstrap(items, per[name][m], per['v3_b0.0'][m])
                          for m in ('recall', 'all_kept')})
    return out


EVAL_MODEL = ART / 'model-cand.json'


def eval_phase():
    """Diagnostic candidate (EVAL_MODEL) vs v3 and v3n / beta 0 (the no-Opus control) on dev, jev-overlap, edge
    (per cut and category), cost; plus grid_ci(). The adopted model is whatever select_phase wrote."""
    import os

    from research import edge_suite as es
    from research import matched_budget_v2 as mb
    os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1')
    sel = json.loads((ART / 'select-log.json').read_text())
    judges = dict(specialist_v4=Judge.load(EVAL_MODEL), specialist_v3=s3.Judge.load(s3.ART / 'model.json'),
                  v4_no_opus=Judge(build('v3n', 0.0)))
    items, skip = mb.eligible_dev()
    groups = {it['item_id']: mb.evidence_groups(it) for it in items}
    arms = defaultdict(dict)
    for it in items:
        for a, sc in mb.cheap_scores(it['goal'], list(mb.texts_for(it).items()), it['item_id']).items():
            arms[a][it['item_id']] = sc
    for name, j in judges.items():
        arms[name] = s2.judge_scores(j, items)
    curves, _ = mb.evaluate(items, arms, groups)
    cmp = ('specialist_v3', 'v4_no_opus', 'recency', 'bm25', 'mechanical')
    per = {a: {it['item_id']: mb.item_metrics(it, arms[a][it['item_id']], groups=groups[it['item_id']]) for it in items}
           for a in ('specialist_v4',) + cmp}
    auc = {a: {m: {k: mb.auc([(0, 1.0)] + [(b, float(per[a][k][b][m])) for b in mb.BUDGETS]) for k in per[a]}
               for m in ('recall', 'all_kept')} for a in per}
    boot = {f'v4-{a}': {m: s3.group_bootstrap(items, auc['specialist_v4'][m], auc[a][m]) for m in ('recall', 'all_kept')}
            for a in cmp}
    by_src = {a: mb.by_source(items, arms[a], groups) for a in ('specialist_v4', 'specialist_v3')}
    j_items, j_saved, j_skip = mb.jev_overlap()
    jg = {it['item_id']: mb.evidence_groups(it) for it in j_items}
    jsc = {a: dict(v) for a, v in j_saved.items()}
    for it in j_items:
        for a, sc in mb.cheap_scores(it['goal'], list(mb.texts_for(it).items()), it['item_id']).items():
            jsc.setdefault(a, {})[it['item_id']] = sc
    for name in ('specialist_v4', 'specialist_v3'):
        jsc[name] = s2.judge_scores(judges[name], j_items)
    j_curves = mb.evaluate(j_items, jsc, jg)[0]
    cases = es.load_cases()
    from research import llm_judge_arm as lj
    edge_sc = {name: {c['id']: dict(zip([b['id'] for b in c['blocks']], j.score(c['goal'], s2.edge_texts(c))))
                      for c in cases} for name, j in judges.items()}
    edge_sc['opus'] = lj.scores('opus', 'edge')
    edge_sc['mechanical'] = {c['id']: mb.mechanical_scores(c['goal'], p) for c, p in mb.edge_pairs()}
    edge_sc['bm25'] = es.arm_scores(cases, es.bm25)
    edge = {a: {str(b): dict(passed=v['passed'], n=v['n'], failed=v['failed'], by_category=v['by_category'])
                for b, v in es.summary(cases, es.run(cases, sc)).items()} for a, sc in edge_sc.items()}
    cost = dict(dev_v4=bench(EVAL_MODEL, items), dev_v3=s3.bench(s3.ART / 'model.json', items))
    for p in sorted(s3.ART.glob('stress*.jsonl')):
        cost[f'{p.stem}_v4'] = s3.bench_file(EVAL_MODEL, p, V4_BENCH)
    m = judges['specialist_v4'].model
    res = dict(schema='specialist-v4/dev', labels='next-action-v2 strict USED, dev split only (test not opened)',
               model=dict(base=m['base'], beta=m['beta'], alpha=m['alpha'], k_goal=m['k_goal'], k_err=m['k_err'],
                          bonus=m['bonus'], features=len(FEATURES)),
               select={k: v for k, v in sel.items()}, train=json.loads((ART / 'train-meta.json').read_text()),
               extras=json.loads((ART / 'extras-meta.json').read_text()),
               dev=dict(items=len(items), excluded=dict(skip), curves=curves, bootstrap_groups=boot, by_source=by_src),
               jev_overlap=dict(items=len(j_items), excluded=dict(j_skip), curves=j_curves), edge_suite=edge, cost=cost,
               grid=grid_ci())
    (ART / 'dev-results.json').write_text(json.dumps(res, indent=1))
    (OUT / 'v4-dev-results.json').write_text(json.dumps(res, indent=1) + '\n')
    return dict(model=res['model'], boot=boot, edge={a: [v[b]['passed'] for b in ('30', '50', '70')] for a, v in edge.items()},
                cost={k: {x: v.get(x) for x in ('ms_median', 'peak_rss_mb', 'model_file_kb')} for k, v in cost.items()})


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('phase', choices=('extras', 'subset', 'train', 'select', 'eval'))
    ap.add_argument('--max-calls', type=int, default=1500)
    ap.add_argument('--part', default='all', choices=('all', 'lrg4', 'teacher'))
    a = ap.parse_args(argv)
    out = dict(extras=extras_phase, subset=lambda: subset_phase(a.max_calls), train=lambda: train_phase(a.part), select=select_phase,
               eval=eval_phase)[a.phase]()
    print(json.dumps(out, indent=1, default=str)[:8000])


if __name__ == '__main__':
    sys.exit(main())
