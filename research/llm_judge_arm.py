"""LLM-judge arm: a generalist model asked the same keep/drop question the Jev arm got, via the owner's
subscription CLIs. NOT run by tests or by any other module: every call spends subscription quota.

Same question and IO shape as the Jev block arm (real_context_bench JEV_BLOCK_KW through LCC's compactor):
blocks are clipped with lcc.relevance.compactor._clip_for_scoring, batched with _batch_blocks (8 blocks, 12000
state chars), and each batch is one request whose state is {"objective", "blocks": [{"id", "text"}]} and whose
questions are {"keep_<id>": compactor.keep_question(id)} (LCC's KEEP_INSTRUCTIONS / KEEP_CRITERIA, verbatim).
Answers are validated with lcc.relevance.jev.parse_noul_answer; a missing or invalid answer leaves the block
unscored (None), as LCC does.

Safety: no --dangerously-skip-permissions (asserted), tools disabled (claude: --tools ""; agy: --mode plan
--sandbox), cwd = an empty private scratch dir, prompt on stdin, no session persistence where the CLI has it.
A usage/rate-limit error stops the run at once (no retry loop); other failures are not cached, so a rerun
retries them once; 3 consecutive failures stop the run. Per-batch results are cached under
~/.lcc/bench/llm-arms/<arm>/<set>/ so reruns resume.

    PYTHONPATH=/Users/Master/.lcc/bench/real-context-v0/lcc-main/src:/Users/Master/Downloads/LCC-judge \\
    /Users/Master/LCC/.venv/bin/python -m research.llm_judge_arm run --arm opus --set edge --limit 2 --max-calls 4
    ... report --arm opus --set jev-overlap      # curves vs the saved Jev scores (offline)
"""
import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path('/Users/Master/.lcc/bench/llm-arms')
SCHEMA = {'type': 'object', 'required': ['answers'], 'properties': {'answers': {
    'type': 'object', 'additionalProperties': {
        'type': 'object', 'required': ['noul', 'confidence'],
        'properties': {'noul': {'type': 'number', 'minimum': 0, 'maximum': 1},
                       'confidence': {'type': 'number', 'minimum': 0, 'maximum': 1}}}}}}
SYSTEM = ('You are a relevance judge for a context compactor. You receive a JSON state (an objective and some '
          'context blocks) and JSON questions, one per block. Answer every question. Reply with JSON only, no '
          'prose and no code fence: {"answers": {"<question id>": {"noul": <probability 0-1 that the answer is '
          'true>, "confidence": <0-1>}}}. Do not use tools.')
TIMEOUT_S = 300
ARMS = {
    'opus': ['claude', '-p', '--model', 'opus', '--tools', '', '--output-format', 'json',
             '--json-schema', json.dumps(SCHEMA), '--no-session-persistence', '--disable-slash-commands',
             '--strict-mcp-config', '--permission-prompts', 'none',
             # no user/project settings or CLAUDE.md: ~840 vs ~13.7K overhead tokens per call (2026-10-13)
             '--setting-sources', '', '--exclude-dynamic-system-prompt-sections', '--system-prompt', SYSTEM],
    # agy has no stdin prompt: the prompt goes in as --print=<text> (see call()).
    'gemini-flash': ['agy', '--model', 'Gemini 3.8 Flash (High)', '--mode', 'plan', '--sandbox',
                     '--print-timeout', f'{TIMEOUT_S}s', '--output-format', 'json', '--json-schema',
                     json.dumps(SCHEMA), '--disable-slash-commands'],
}
LIMIT_RE = re.compile(r'usage limit|rate.?limit|quota|resource.?exhausted|too many requests|\b429\b|limit reached|'
                      r'hit your limit|credit balance|out of (?:extra )?usage', re.I)


class LimitHit(RuntimeError):
    """Usage / rate limit: the run stops here (no retries)."""


def argv_for(arm):
    a = list(ARMS[arm])
    assert not any('dangerously' in x for x in a), 'never skip permissions'
    return a


# --- prompt (mirrors the Jev block arm) ------------------------------------------------------------------
def batches(pairs):
    """[(block_id, text)] -> [[(block_id, clipped text)]] with LCC's own clip + batching (Jev block settings)."""
    from lcc.relevance.blocks import TextBlock
    from lcc.relevance.compactor import _batch_blocks, _clip_for_scoring
    tb = [TextBlock(id=i, index=n, text=t, character_start=0, character_end=0, line_start=0, line_end=0)
          for n, (i, t) in enumerate(pairs)]
    return [[(b.id, _clip_for_scoring(b.text)) for b in batch] for batch in _batch_blocks(tb, 8, 12000)]


def prompt(goal, batch):
    from lcc.relevance.compactor import keep_question
    state = {'objective': goal, 'blocks': [{'id': i, 'text': t} for i, t in batch]}
    questions = {f'keep_{i}': keep_question(i) for i, _ in batch}
    return ('STATE:\n' + json.dumps(state, ensure_ascii=False) + '\n\nQUESTIONS:\n'
            + json.dumps(questions, ensure_ascii=False) + '\n\n' + SYSTEM)


# --- output parsing ----------------------------------------------------------------------------------------
def _json_in(text):
    """First JSON object in a string (bare, fenced, or embedded in prose) that holds 'answers'."""
    if not isinstance(text, str):
        return None
    t = re.sub(r'^```(?:json)?\s*|\s*```$', '', text.strip())
    for cand in (t, *re.findall(r'\{.*\}', t, re.S)):
        try:
            d = json.loads(cand)
        except ValueError:
            continue
        found = _find_answers(d)
        if found is not None:
            return found
    return None


def _find_answers(d, depth=0):
    """Walk a CLI's JSON envelope for {'answers': {...}} (structured_output, result text, nested fields)."""
    if depth > 6:
        return None
    if isinstance(d, dict):
        if isinstance(d.get('answers'), dict):
            return d['answers']
        for k in ('structured_output', 'result', 'response', 'output', 'text', 'content', 'message'):
            if k in d:
                r = _find_answers(d[k], depth + 1) if not isinstance(d[k], str) else _json_in(d[k])
                if r is not None:
                    return r
        for v in d.values():
            r = _find_answers(v, depth + 1) if not isinstance(v, str) else None
            if r is not None:
                return r
    if isinstance(d, list):
        for v in d:
            r = _find_answers(v, depth + 1) if not isinstance(v, str) else _json_in(v)
            if r is not None:
                return r
    return None


def parse_output(stdout, stderr, returncode, block_ids):
    """-> {block_id: score | None}. Raises LimitHit on a usage/rate-limit error, RuntimeError on other failures."""
    from lcc.relevance.jev import parse_noul_answer
    env = None
    try:
        env = json.loads(stdout)
    except ValueError:
        pass
    is_error = returncode != 0 or (isinstance(env, dict) and env.get('is_error') is True)
    answers = None if is_error else (_find_answers(env) if env is not None else _json_in(stdout))
    if answers is None:
        msg = f'{stdout[-2000:]}\n{stderr[-2000:]}'
        if LIMIT_RE.search(msg):
            raise LimitHit(LIMIT_RE.search(msg).group(0))
        raise RuntimeError(f'no answers (exit {returncode})')
    out = {}
    for i in block_ids:
        score, _, _ = parse_noul_answer(answers.get(f'keep_{i}'))
        out[i] = score
    return out


# --- run ---------------------------------------------------------------------------------------------------
def call_cli(arm, text, cwd):
    if any(Path(cwd).iterdir()):
        raise SystemExit(f'{cwd} must stay empty')
    argv, stdin = argv_for(arm), text
    if arm == 'gemini-flash':
        argv, stdin = argv + [f'--print={text}'], None
    r = subprocess.run(argv, input=stdin, capture_output=True, text=True, cwd=cwd, timeout=TIMEOUT_S + 30,
                       env={k: v for k, v in os.environ.items() if not k.startswith(('PYTHON', 'ANTHROPIC_'))})
    # ^ subscription login only: an API key in the env would bill per token.
    return r.stdout, r.stderr, r.returncode


def load_set(name):
    """-> [(item_id, goal, [(block_id, text)])]. edge = synthetic fixtures (raw block text, as the saved Jev / Laya edge runs);
    jev-overlap = the 43 dev items with saved Jev scores; dev = every eligible dev item; train = the frozen
    targeted train subset of specialist_v4 (train_guard: train items only). Never test."""
    if name == 'train':
        from research.specialist_v4 import train_set
        return train_set()
    if name == 'edge':
        from research.edge_suite import load_cases
        return [(c['id'], c['goal'], [(b['id'], b['text']) for b in c['blocks']]) for c in load_cases()]
    from research import matched_budget_v2 as mb
    items = mb.jev_overlap()[0] if name == 'jev-overlap' else mb.eligible_dev()[0]
    sp = json.loads((mb.PRIVATE_LABELS / 'splits.json').read_text())['items']
    assert all(sp.get(it['item_id']) in ('train', 'dev') for it in items), 'test items are never sent'
    return [(it['item_id'], it['goal'], list(mb.texts_for(it).items())) for it in items]


def run(arm, set_name, limit=None, max_calls=None, root=ROOT, caller=call_cli, items=None, shard=(0, 1)):
    out = Path(root) / arm / set_name
    cwd = Path(root) / '_empty_cwd'
    out.mkdir(parents=True, exist_ok=True, mode=0o700)
    cwd.mkdir(parents=True, exist_ok=True, mode=0o700)
    calls = fails = done = 0
    # shard k/n: items k, k+n, ... so n processes can run side by side on disjoint item dirs
    for iid, goal, pairs in (items if items is not None else load_set(set_name))[:limit][shard[0]::shard[1]]:
        d = out / iid
        d.mkdir(exist_ok=True, mode=0o700)
        bs = batches(pairs)
        for k, batch in enumerate(bs):
            p = d / f'batch-{k:04d}.json'
            if p.exists():
                continue
            if max_calls is not None and calls >= max_calls:
                return dict(calls=calls, items_done=done, stopped='max_calls')
            calls += 1
            try:
                so, se, rc = caller(arm, prompt(goal, batch), cwd)
                sc = parse_output(so, se, rc, [i for i, _ in batch])
            except LimitHit as e:
                return dict(calls=calls, items_done=done, stopped=f'limit: {e}')
            except (RuntimeError, subprocess.TimeoutExpired) as e:
                fails += 1
                print(arm, iid, k, 'failed:', str(e)[:200], flush=True)
                if fails >= 3:
                    return dict(calls=calls, items_done=done, stopped='3 consecutive failures')
                continue
            fails = 0
            p.write_text(json.dumps(dict(scores=sc, n=len(batch))))
        if all((d / f'batch-{k:04d}.json').exists() for k in range(len(bs))):
            (d / 'done.json').write_text(json.dumps(dict(batches=len(bs), blocks=len(pairs))))
            done += 1
    return dict(calls=calls, items_done=done, stopped=None)


def scores(arm, set_name, root=ROOT):
    """{item_id: {block_id: score | None}} for items whose every batch is cached."""
    res = {}
    for d in sorted((Path(root) / arm / set_name).iterdir()) if (Path(root) / arm / set_name).exists() else ():
        if (d / 'done.json').exists():
            sc = {}
            for p in sorted(d.glob('batch-*.json')):
                sc.update(json.loads(p.read_text())['scores'])
            res[d.name] = sc
    return res


def report(arm, set_name):
    """Offline: curves of the cached LLM arm vs the other arms on the same items (counts only)."""
    sc = scores(arm, set_name)
    if set_name == 'train':  # teacher labels only: no curves on train
        return dict(items=len(sc), blocks=sum(len(v) for v in sc.values()),
                    unscored=sum(x is None for v in sc.values() for x in v.values()))
    if set_name == 'edge':
        from research import edge_suite as es
        cases = [c for c in es.load_cases() if c['id'] in sc]
        sm = es.summary(cases, es.run(cases, sc))
        return {b: dict(passed=v['passed'], n=v['n']) for b, v in sm.items()}
    from research import matched_budget_v2 as mb
    items = [it for it in (mb.jev_overlap()[0] if set_name == 'jev-overlap' else mb.eligible_dev()[0])
             if it['item_id'] in sc and len(sc[it['item_id']]) == len(mb.cand_blocks(it))]
    groups = {it['item_id']: mb.evidence_groups(it) for it in items}
    arms = {arm: {it['item_id']: sc[it['item_id']] for it in items}}
    if set_name == 'jev-overlap':
        saved = mb.jev_overlap()[1]
        arms['jev'] = {it['item_id']: saved['jev'][it['item_id']] for it in items}
    for it in items:
        for a, s in mb.cheap_scores(it['goal'], list(mb.texts_for(it).items()), it['item_id']).items():
            arms.setdefault(a, {})[it['item_id']] = s
    curves = mb.evaluate(items, arms, groups)[0]
    return dict(items=len(items), auc={a: c['auc'] for a, c in curves.items()})


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('phase', choices=('run', 'report'))
    ap.add_argument('--arm', choices=tuple(ARMS), required=True)
    ap.add_argument('--set', default='jev-overlap', choices=('edge', 'jev-overlap', 'dev', 'train'))
    ap.add_argument('--limit', type=int, help='max items')
    ap.add_argument('--max-calls', type=int, help='max CLI calls (batches) this run')
    ap.add_argument('--shard', default='0/1', help='k/n: this process takes items k, k+n, ...')
    a = ap.parse_args(argv)
    k, n = map(int, a.shard.split('/'))
    assert 0 <= k < n
    out = run(a.arm, a.set, a.limit, a.max_calls, shard=(k, n)) if a.phase == 'run' else report(a.arm, a.set)
    print(json.dumps(out, indent=1))


if __name__ == '__main__':
    sys.exit(main())
