"""Post-cutoff held-out set: sessions that STARTED after 2026-10-12, session-disjoint from every
train/dev/test lineage group of next-action v1/v2 (the frozen test split is spent).

A session qualifies when its earliest human prompt (importer rules: research.import_agent_requests) is at or
after CUTOFF (UTC), its lineage keys (session id, Claude transcript file, Hermes parent session) are absent
from the next-action-v1 lineage files, and it has >= 2 human prompts (an item needs prior assistant context,
so a session's first prompt never yields one). Only lineage KEYS of the old splits are read: no test item,
text or window is opened.

    count  -> qualifying sessions / prompts per source today (counts only; nothing private is written to the repo)
    build  -> PRIVATE/items|texts|windows via next_action_labels.Builder restricted to the qualifying sessions,
              v2 labels (current extractor + v2 generic features), lineage re-check after the build (any group
              that touches an old lineage key is dropped), content-link check against train/dev items only,
              PRIVATE/manifest-heldout.txt + repo receipt specialist-v1/heldout-v3-receipt.json (counts + sha256).
              Run it only when count shows enough sessions; it refuses to overwrite an existing receipt.

    PYTHONPATH=/Users/Master/.lcc/bench/real-context-v0/lcc-main/src:/Users/Master/Downloads/LCC-judge \\
    /Users/Master/LCC/.venv/bin/python -m research.heldout_v3 {count|build} [--cutoff ...] [--limit N]
"""
import argparse
import hashlib
import json
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from research import codex_context as cc
from research import hermes_context as hc

CUTOFF = '2026-10-13T00:00:00.000Z'  # "after 2026-10-12": sessions starting on 2026-10-13 UTC or later
PRIVATE = Path('/Users/Master/.lcc/bench/heldout-v3')
V1 = Path('/Users/Master/.lcc/bench/next-action-v1')
V2 = Path('/Users/Master/.lcc/bench/next-action-v2')
CLAUDE_ROOT = Path.home() / '.claude' / 'projects'
OUT = Path(__file__).resolve().parent / 'goal-engine-2026-10-04' / 'specialist-v1'


def importer():
    from research import next_action_labels as nal
    from research import real_context_bench as rcb
    return nal._iar(rcb.load_request_log(nal.RULESET_PREFIX))


def old_lineage(root=V1):
    """{lineage key: group} of every next-action-v1 item (train, dev and test); keys only."""
    out = {}
    for p in sorted(Path(root).glob('lineage-*.json')):
        out.update(json.loads(p.read_text()))
    return out


def _keep(text, iar):
    t = (text or '').strip()
    return bool(t) and not iar._SLASH.fullmatch(t)


def claude_sessions(iar, cutoff, root=CLAUDE_ROOT):
    """{sid: dict(first, n, files)} for transcripts modified after the cutoff (older files cannot hold a
    session that starts after it)."""
    cut = datetime.fromisoformat(cutoff.replace('Z', '+00:00')).timestamp()
    out = defaultdict(lambda: dict(first=None, n=0, files=set()))
    for f in sorted(Path(root).rglob('*.jsonl')):
        if 'subagents' in f.relative_to(root).parts or iar.is_denied(f) or f.stat().st_mtime < cut:
            continue
        for d in iar._lines(f, Counter()):
            ts, sid = iar._utc(d.get('timestamp')), d.get('sessionId') or f.stem
            if ts:
                s = out[sid]
                s['first'] = min(s['first'] or ts, ts)  # any record: a resumed old session starts early
                s['files'].add(str(f))
    for sid, n in _claude_prompts(iar, out).items():
        out[sid]['n'] = n
    return dict(out)


def _claude_prompts(iar, sessions):
    from research.next_action_labels import claude_human
    n = Counter()
    for f in sorted({f for s in sessions.values() for f in s['files']}):
        for d in iar._lines(Path(f), Counter()):
            g = claude_human(d, iar)
            if g is not None and _keep(g, iar):
                n[d.get('sessionId') or Path(f).stem] += 1
    return n


def codex_sessions(iar, cutoff, root=cc.ROOT):
    """{sid: dict(first, n, files)} from rollouts in day folders on or after the cutoff day - 1 (local dates)."""
    day = cutoff[:10]
    out = defaultdict(lambda: dict(first=None, n=0, files=set()))
    for f in sorted(Path(root, 'sessions').rglob('rollout-*.jsonl')):
        parts = f.relative_to(Path(root, 'sessions')).parts[:3]
        if len(parts) == 3 and '-'.join(parts) < _day_before(day):
            continue
        recs = cc.read_rollout(f)
        first = min((t for t in (iar._utc(r.get('timestamp')) for r in recs) if t), default=None)
        for _, sid, human, raw in cc.prompt_records(recs):
            sid = sid or f.stem[-36:]
            s = out[sid]
            s['files'].add(str(f))
            s['first'] = min(x for x in (s['first'], first) if x) if first or s['first'] else None
            if human and cc.goal_of(raw) is not None and _keep(cc.goal_of(raw), iar):
                s['n'] += 1
    return dict(out)


def _day_before(day):
    from datetime import timedelta
    return (datetime.fromisoformat(day) - timedelta(days=1)).date().isoformat()


def hermes_sessions(iar, cutoff, root=hc.ROOT):
    """{sid: dict(first, n, parent)}: human prompts per Hermes session (importer rules)."""
    out = defaultdict(lambda: dict(first=None, n=0, parent=None))
    for t, sid, iso in iar.hermes(root, Counter()):
        ts = iar._utc(iso)
        if ts and _keep(t, iar):
            s = out[sid]
            s['first'] = min(s['first'] or ts, ts)
            s['n'] += 1
    if out:
        con = hc.connect(root)
        try:
            for sid, parent in con.execute('select id, parent_session_id from sessions'):
                if sid in out:
                    out[sid]['parent'] = parent
        finally:
            con.close()
    return dict(out)


def qualifying(source, sessions, old, cutoff):
    """-> ({sid}, Counter of exclusion reasons)."""
    ok, why = set(), Counter()
    for sid, s in sessions.items():
        if not s['first'] or s['first'] < cutoff:
            why['started_before_cutoff'] += 1
        elif f'{source}:{sid}' in old or any(f'{source}:file:{f}' in old for f in s.get('files', ())):
            why['in_old_lineage'] += 1
        elif s.get('parent') and f'{source}:{s["parent"]}' in old:
            why['parent_in_old_lineage'] += 1
        elif s['n'] < 2:
            why['fewer_than_2_prompts'] += 1
        else:
            ok.add(sid)
    return ok, why


SCANNERS = dict(claude=claude_sessions, codex=codex_sessions, hermes=hermes_sessions)


def scan(cutoff=CUTOFF, sources=tuple(SCANNERS)):
    iar, old = importer(), old_lineage()
    out = {}
    for src in sources:
        sess = SCANNERS[src](iar, cutoff)
        ok, why = qualifying(src, sess, old, cutoff)
        out[src] = dict(sessions=sess, ok=ok, why=why)
    return out


def count_phase(cutoff=CUTOFF):
    res = scan(cutoff)
    return dict(cutoff_utc=cutoff, measured_at_utc=datetime.now(timezone.utc).isoformat(timespec='seconds'),
                per_source={s: dict(qualifying_sessions=len(r['ok']),
                                    candidate_items=sum(r['sessions'][i]['n'] - 1 for i in r['ok']),
                                    excluded=dict(r['why'])) for s, r in res.items()})


# --- build (run later) ----------------------------------------------------------------------------------
def farm(root, files, rel_to):
    """Symlink farm of the qualifying transcripts, so the Builder walks only those."""
    for f in files:
        dst = Path(root) / Path(f).relative_to(rel_to)
        dst.parent.mkdir(parents=True, exist_ok=True)
        if not dst.exists():
            dst.symlink_to(f)


def build_phase(cutoff=CUTOFF, limit=None, root=PRIVATE, out=OUT):
    from research import next_action_labels as nal
    receipt = Path(out) / 'heldout-v3-receipt.json'
    if receipt.exists():
        raise SystemExit(f'{receipt} exists: the held-out set is frozen')
    res = scan(cutoff)
    ok = {(s, sid) for s, r in res.items() for sid in r['ok']}

    class Restricted(nal.Builder):
        def emit(self, source, key, session, goal, *rest):
            if (source, session) not in ok:
                self.skips[f'{source}:not_qualifying_session'] += 1
                return
            return super().emit(source, key, session, goal, *rest)

    class HermesOnly:
        def __init__(self, iar):
            self._iar = iar

        def __getattr__(self, k):
            return getattr(self._iar, k)

        def hermes(self, r, drops):
            return ((t, sid, iso) for t, sid, iso in self._iar.hermes(r, drops) if ('hermes', sid) in ok)

    b = Restricted(root, limit)
    b.iar = HermesOnly(b.iar)
    fr = Path(root) / 'farm'
    farm(fr / 'claude', {f for i in res['claude']['ok'] for f in res['claude']['sessions'][i]['files']}, CLAUDE_ROOT)
    farm(fr / 'codex', {f for i in res['codex']['ok'] for f in res['codex']['sessions'][i]['files']}, cc.ROOT)
    try:
        b.claude(fr / 'claude')
        b.codex(fr / 'codex')
        b.hermes()
    except StopIteration:
        pass
    old = old_lineage()
    groups = {k: b.lineage.find(k) for k in list(b.lineage.p)}
    tainted = {g for k, g in groups.items() if k in old}  # a new group that shares any key with an old one
    group_of = {nal.h16(k): g for k, g in groups.items() if k.count(':') == 1}  # session keys, as split_phase
    generic = {tuple(x) for x in json.loads((V2 / 'generic-features.json').read_text())}
    manifest, slim, drop = [], [], Counter()
    for row in b.index:
        p = Path(root) / 'items' / f"{row['item_id']}.json"
        it = json.loads(p.read_text())
        src, g = it['source'], group_of.get(it['session'])
        it['group'] = nal.h16(g) if g else it['session']
        if g in tainted:
            drop['lineage_touches_old_split'] += 1
            p.unlink()
            continue
        it = nal.apply_generic(it, generic)
        it['split'] = 'heldout'
        data = json.dumps(it, ensure_ascii=False)
        p.write_text(data)
        manifest.append((it['item_id'], hashlib.sha256(data.encode()).hexdigest(), src, it['evidence']))
        slim.append(dict(item_id=it['item_id'], group=it['group'], blocks=[
            dict(id=b_['id'], chars=b_['chars'], protected=b_['protected']) for b_ in it['blocks']
            if not b_['protected'] and b_['chars'] >= 200]))
    sp = json.loads((V2 / 'splits.json').read_text())['items']
    for iid, s in sp.items():  # train/dev only: test items are never opened
        if s in ('train', 'dev'):
            it = json.loads((V2 / 'items' / f'{iid}.json').read_text())
            slim.append(dict(item_id=iid, group=it['group'], blocks=[
                dict(id=b_['id'], chars=b_['chars'], protected=b_['protected']) for b_ in it['blocks']
                if not b_['protected'] and b_['chars'] >= 200]))
    mine = {m[0] for m in manifest}
    linked = {a if a in mine else b_ for a, b_ in nal.content_links(slim) if (a in mine) != (b_ in mine)}
    lines = ''.join(f'{i} {h}\n' for i, h, _, _ in sorted(manifest))
    (Path(root) / 'manifest-heldout.txt').write_text(lines)
    (Path(root) / 'content-linked-train-dev.json').write_text(json.dumps(sorted(linked)))
    rec = dict(cutoff_utc=cutoff, created_utc=datetime.now(timezone.utc).isoformat(timespec='seconds'),
               labels='next-action v2 extractor + v2 generic features (train groups)',
               items=len(manifest), per_source=dict(Counter(m[2] for m in manifest)),
               with_agent_action=sum(m[3] == 'actions' for m in manifest), groups=len({s['group'] for s in slim
                                                                                         if s['item_id'] in mine}),
               content_linked_to_train_dev=len(linked), dropped=dict(drop), builder_skips=dict(b.skips),
               sha256=dict(items_manifest=hashlib.sha256(lines.encode()).hexdigest()))
    for i, *_ in manifest:
        os.chmod(Path(root) / 'items' / f'{i}.json', 0o444)
    Path(out).mkdir(parents=True, exist_ok=True)
    receipt.write_text(json.dumps(rec, indent=1) + '\n')
    return rec


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('phase', choices=('count', 'build'))
    ap.add_argument('--cutoff', default=CUTOFF)
    ap.add_argument('--limit', type=int)
    a = ap.parse_args(argv)
    out = count_phase(a.cutoff) if a.phase == 'count' else build_phase(a.cutoff, a.limit)
    print(json.dumps(out, indent=1, default=sorted))


if __name__ == '__main__':
    sys.exit(main())
