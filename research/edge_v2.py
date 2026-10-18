"""Edge suite v2 (v5 cycle, step A): ~130 synthetic edge cases written by Claude Opus 5.5 (subscription CLI,
research.opus_cli), validated mechanically, split per edge type into dev-edge (visible) and sealed.

    gen     -> ROOT/raw/<n>.json      one Opus call per planned case (PLAN, seeded); cached, resumable
    build   -> validate every raw case, seeded split per edge type (~60% dev / ~40% sealed):
               dev    -> tests/fixtures/edge_cases_v2/<id>.json  (synthetic, repo)
               sealed -> SEALED/<id>.json                         (private; never opened before the final step)
               receipt -> specialist-v1/edge-v2-receipt.json      (counts per type, sha256 per sealed case, dir hash)
    review  -> specialist-v1/edge-v2-review.csv (seeded sample of 20 dev-edge cases, plain pt-BR, for the owner)

Case schema = tests/fixtures/edge_cases (research.edge_suite scores both), plus `edge_type`, `lang`, `harness`.
Filler blocks ("filler": build_log | pip_log | test_log | code | chatter | web_boiler | git_log) are expanded
with research.edge_cases_build's deterministic generators and chunked with its balance(), so block size carries
no signal, exactly as in v1.

    PYTHONPATH=...lcc-main/src:$PWD .venv python -m research.edge_v2 {gen|build|review} [--shards 4]
"""
import argparse
import csv
import hashlib
import io
import json
import random
import re
import sys
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from research import edge_cases_build as eb
from research import opus_cli

ROOT = Path('/Users/Master/.lcc/bench/edge-v2')
SEALED = Path('/Users/Master/.lcc/bench/edge-v2-sealed')
FIX2 = eb.ROOT / 'tests' / 'fixtures' / 'edge_cases_v2'
OUT = eb.OUT
SEED = 20261018
DEV_SHARE = 0.6
SEEN = {0}  # raw case 0 was read during the generator smoke test (2026-10-18), so it can only be dev

# edge type -> (how many to plan, what the case must exercise)
TYPES = {
    'contradiction': (11, 'Two sources state DIFFERENT values for the same fact and nothing in the session says which '
                          'is right; both must be kept so the agent can report the conflict.'),
    'structured_config': (11, 'A structured config/data block (YAML, JSON, .env, TOML, SQL schema, table) where only '
                              'one key matters for the goal; other config blocks have the same key name with a '
                              'different value (other service / env) or lots of unrelated keys.'),
    'source_authority': (11, 'The same fact appears from sources of different authority: an explicit user statement '
                             'or an authoritative tool output (official doc, the actual file, command output) vs an '
                             'assistant guess / memory / hedge ("acho que", "I think", "probably"). Keep the '
                             'authoritative one(s); the guess is droppable.'),
    'qualifier_exception': (12, 'A general rule plus a separate, later or distant qualifier / exception ("exceto", '
                                '"menos", "a menos que", "só se", "but not", "unless", "except", "only if") that '
                                'changes the answer; both the rule and the exception (and any fact that triggers '
                                'the exception) must be kept.'),
    'pt_en_mixed': (11, 'The user writes in Portuguese while the code / logs / docs that matter are in English (or '
                        'the reverse), so the must-keep block shares almost no words with the goal; a distractor '
                        'shares many goal words in the goal language.'),
    'git_wide_view': (11, 'Either git state (git status / log / diff / branch, AGENTS.md commit conventions, which '
                          'files this session touched) needed to commit or ship correctly, or a wide-view question '
                          '(project overview, strengths / weaknesses, what is left) that needs early roadmap / status '
                          '/ README reads rather than the recent narrow work.'),
    'prompt_injection': (11, 'A tool output (web page, file, issue, email, log) contains text that tries to instruct '
                             'the agent. The tool output that carries the data the goal needs must be KEPT (it is '
                             'evidence), and the user\'s real rule must be kept; the injected instruction is never '
                             'a rule. Vary whether the injection sits inside the must-keep block or in a separate '
                             'may-drop block.'),
    'supersession': (11, 'A value, decision, file content or plan is replaced later (re-read after edit, correction '
                         'message, "mudei de ideia", newer version of a file). The CURRENT version must be kept; '
                         'the stale version is longer or lexically closer to the goal and is droppable.'),
    'coreference': (11, 'The goal or a later short turn refers back with a pronoun or vague reference ("isso", '
                        '"esse erro", "aquele arquivo", "that one", "the same thing", "o segundo") to a specific '
                        'earlier block that shares few words with the goal; that antecedent must be kept.'),
    'general': (30, 'Any of: pasted error then fix, plan / todo state, handoff prompt, approval of numbered options '
                    '("1 e 3"), secrets redacted in .env, subagent report, prior compaction summary, multi-file '
                    'refactor, partial reads of a long file, error in the middle of a huge log, duplicated tool '
                    'output (use one:<group> gold), stale vs fresh error, file named only in the goal, number-only '
                    'reply, unrecoverable read, retry of a failed command. Pick one; vary across calls.'),
}
CATEGORIES = ('approve_or_pick', 'correct_approach_or_rule', 'environment_and_infra', 'external_accounts_and_comms',
              'failure_report', 'general_question', 'git_ship', 'handoff_prompt', 'project_audit_or_direction',
              'revise_recent_output', 'specified_task', 'supply_fact_or_step_done', 'task_status_or_control')
LANGS = ('pt-BR', 'en', 'mixed pt-BR goal / English artifacts')
HARNESS = {
    'claude-code': 'Claude Code (tools: Read, Bash, Edit, Write, Grep, Glob, WebFetch, Agent, TodoWrite; mcp__* tools)',
    'codex': 'OpenAI Codex CLI (tools: exec_command, apply_patch, shell, web_search; outputs like "Exit code: 1\\nOutput:")',
    'hermes': 'Hermes agent (tools: terminal, read_file, write_file, patch, web_extract, execute_code, delegate_task)',
}
FILLERS = ('build_log', 'pip_log', 'test_log', 'code', 'chatter', 'web_boiler', 'git_log')

BLOCK = {'type': 'object', 'required': ['gold', 'role', 'kind', 'text'], 'properties': {
    'gold': {'type': 'string'}, 'role': {'enum': ['user', 'assistant', 'tool']},
    'kind': {'enum': ['text', 'tool_result', 'tool_call']}, 'tool': {'type': ['string', 'null']},
    'is_error': {'type': 'boolean'}, 'text': {'type': 'string'},
    'filler': {'enum': list(FILLERS)}, 'n': {'type': 'integer', 'minimum': 5, 'maximum': 60}}}
SCHEMA = {'type': 'object', 'required': ['id', 'category', 'use_case', 'goal', 'situation', 'must_keep', 'may_drop',
                                        'why_judges_fail', 'blocks'],
          'properties': {'id': {'type': 'string'}, 'category': {'enum': list(CATEGORIES)},
                         'use_case': {'type': 'string'}, 'goal': {'type': 'string'}, 'situation': {'type': 'string'},
                         'must_keep': {'type': 'string'}, 'may_drop': {'type': 'string'},
                         'why_judges_fail': {'type': 'string'}, 'blocks': {'type': 'array', 'items': BLOCK}}}
SYSTEM = ('You write synthetic test cases for a context compactor used by coding agents. Reply with JSON only that '
          'matches the schema. Do not use tools.')
PROMPT = """Write ONE test case for a context compactor. The compactor sees the agent's goal (the user's latest
message) and the earlier session blocks, and must drop {{30,50,70}}% of the tokens. The case checks that the
blocks marked "must" survive.

Edge type: {etype}
What it must exercise: {desc}
Language: {lang}
Agent harness and tool names: {harness}
Variation seed: {seed} (use it to pick a fresh domain: e.g. clinic SaaS, e-commerce, CLI tool, data pipeline,
mobile app, game, infra, outreach automation, billing, ML training; vary file names, numbers and wording).

Rules:
- blocks: 10 to 22 authored blocks in session order (oldest first) plus 2 to 5 filler blocks. A filler block is
  {{"gold": "may", "role": "tool", "kind": "tool_result", "tool": <tool>, "text": "", "filler": one of
  {fillers}, "n": 5..40}} (chatter is an assistant text block: role "assistant", kind "text", and its "text" is
  the topic it rambles about).
- role/kind: user text, assistant text, assistant tool_call (the call, e.g. an Edit diff), tool tool_result.
  "tool" names the tool for tool_call / tool_result, null otherwise.
- gold: "must" for the 1 to 3 blocks without which the agent would answer or act WRONGLY; "may" for the rest. For
  two identical copies of the same evidence use "one:a" on both (at least one must survive) instead of "must".
- The must blocks must be SHORT (under 400 characters each) and must NOT be the last block, and not all of them
  may sit in the last 3 blocks. Put realistic noise after them.
- Include at least two hard distractors (may blocks): one that shares more words with the goal than the must
  block does, and one that looks like the must block but is stale, hedged, about another service / env, or
  otherwise wrong for this goal.
- Tool outputs must look like real {harness_short} output (paths, commands, exit codes, stack traces, diffs).
- Everything fictional: no real people, emails, keys or tokens (use placeholders like [REDACTED]).
- The goal is a short, natural user message (in the stated language), often vague; it must not quote the must
  block's key words verbatim unless the edge type needs it.
- id: short snake_case describing the case. category: the closest of the given enum.
- situation / must_keep / may_drop / why_judges_fail: one or two plain English sentences each."""


def plan():
    """[(n, etype, lang, harness, seed)]: fixed, seeded."""
    rng = random.Random(SEED)
    out, n = [], 0
    for et, (k, _) in TYPES.items():
        for j in range(k):
            out.append((n, et, LANGS[(n + j) % 3], list(HARNESS)[(n // 3 + j) % 3], rng.randrange(10 ** 6)))
            n += 1
    return out


def prompt_for(etype, lang, harness, seed):
    return PROMPT.format(etype=etype, desc=TYPES[etype][1], lang=lang, harness=HARNESS[harness],
                         harness_short=harness, seed=seed, fillers=', '.join(FILLERS))


def gen_one(p):
    n, et, lang, h, seed = p
    out = ROOT / 'raw' / f'{n:03d}.json'
    if out.exists():
        return n, 'cached'
    try:
        obj = opus_cli.call(SYSTEM, SCHEMA, prompt_for(et, lang, h, seed), 'gen')
    except Exception as e:  # LimitHit included: the shard stops
        return n, f'{type(e).__name__}: {str(e)[:160]}'
    out.write_text(json.dumps(dict(plan=dict(n=n, edge_type=et, lang=lang, harness=h, seed=seed), case=obj),
                              ensure_ascii=False))
    return n, 'ok'


def gen(shards=4, limit=None):
    (ROOT / 'raw').mkdir(parents=True, exist_ok=True, mode=0o700)
    todo = [p for p in plan() if not (ROOT / 'raw' / f'{p[0]:03d}.json').exists()][:limit]
    res, stop = Counter(), []
    with ThreadPoolExecutor(shards) as ex:
        for n, st in ex.map(gen_one, todo):
            res[st.split(':')[0]] += 1
            if st not in ('ok', 'cached'):
                print(n, st, flush=True)
                stop.append(st)
    return dict(result=dict(res), raw=len(list((ROOT / 'raw').glob('*.json'))), calls_used=opus_cli.calls_used())


# --- build ---------------------------------------------------------------------------------------------------
def git_log(n):
    return '\n'.join(f'commit {hashlib.sha1(str(i).encode()).hexdigest()[:7]} chore: bump deps batch {i}' for i in range(n))


def expand(b):
    f, n = b.get('filler'), int(b.get('n') or 20)
    if not f:
        return b['text']
    return dict(build_log=lambda: eb.build_log(n), pip_log=lambda: eb.pip_log(n), test_log=lambda: eb.test_log(n),
                code=lambda: eb.code('helper', n), chatter=lambda: eb.chatter(b['text'] or 'the codebase', n),
                web_boiler=lambda: eb.web_boiler(n), git_log=lambda: git_log(n))[f]()


GOLD_RE = re.compile(r'^(?:must|may|one:[a-z0-9_]{1,12})$')


def to_fixture(raw, used_ids):
    """raw generator output -> fixture dict, or raises ValueError(reason)."""
    c, p = raw['case'], raw['plan']
    blocks, last_tool = [], None
    for b in c['blocks']:
        g = b['gold'].strip()
        if not GOLD_RE.match(g):
            raise ValueError(f'bad gold {g!r}')
        if b.get('filler') and g != 'may':
            raise ValueError('filler marked as kept')
        role, kind = b['role'], b['kind']
        if (role == 'tool') != (kind == 'tool_result') or (kind == 'tool_call' and role != 'assistant'):
            raise ValueError(f'role/kind mismatch {role}/{kind}')
        tool = b.get('tool') or None
        if kind == 'tool_call' and not tool:  # Opus often writes the call as 'Read(file_path=...)'
            m = re.match(r'\s*\$?\s*([A-Za-z_][\w.]*)\(', b['text'])
            tool = m.group(1) if m else None
        if kind == 'tool_result' and not tool:
            tool = last_tool  # the result of the preceding call
        if kind != 'text' and not tool:
            raise ValueError('tool block without tool name')
        if kind == 'tool_call':
            last_tool = tool
        text = expand(b)
        if not text.strip():
            raise ValueError('empty block')
        blocks.append(eb.B(g, role, kind, text, tool if kind != 'text' else None, bool(b.get('is_error'))))
    kept = [k for k, b in enumerate(blocks) if b['gold'] != 'may']
    if not kept or len(kept) == len(blocks):
        raise ValueError('no kept or no droppable block')
    groups = Counter(b['gold'] for b in blocks if b['gold'].startswith('one:'))
    if any(v < 2 for v in groups.values()):
        raise ValueError('one: group with a single member')
    n = len(blocks)
    if n < 8:
        raise ValueError('fewer than 8 blocks')
    if all(k >= n - 3 for k in kept) or n - 1 in kept:
        raise ValueError('kept evidence trivially most recent')
    if max(range(n), key=lambda k: len(blocks[k]['text'])) in kept:
        raise ValueError('kept evidence trivially largest')
    if any(len(blocks[k]['text']) > 1200 for k in kept):
        raise ValueError('kept block over 1200 chars')
    secretish = re.compile(r'(?:sk-[A-Za-z0-9]{16,}|AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{20,}|xox[bp]-[A-Za-z0-9-]{10,})')
    if any(secretish.search(b['text']) for b in blocks):
        raise ValueError('secret-shaped string')
    base = re.sub(r'[^a-z0-9_]+', '_', c['id'].lower()).strip('_')[:48] or 'case'
    cid = f"v2_{p['n']:03d}_{base}"
    assert cid not in used_ids
    case = dict(id=cid, category=c['category'], use_case=c['use_case'], situation=c['situation'],
                must_keep=c['must_keep'], may_drop=c['may_drop'], why_judges_fail=c['why_judges_fail'],
                source='synthetic-opus', source_ref=f"edge_v2 plan {p['n']} seed {p['seed']}", goal=c['goal'].strip(),
                blocks=blocks)
    if not case['goal']:
        raise ValueError('empty goal')
    fx = eb.fixture(case, p['n'])
    eb.validate(fx)  # must share <= 30%, gold values, droppable present
    return dict(fx, edge_type=p['edge_type'], lang=p['lang'], harness=p['harness'], plan_n=p['n'])


def dump(fx):
    return json.dumps(fx, ensure_ascii=False, indent=1) + '\n'


def build():
    raws = sorted((ROOT / 'raw').glob('*.json'))
    good, bad, used = [], Counter(), set()
    for rp in raws:
        try:
            fx = to_fixture(json.loads(rp.read_text()), used)
        except (ValueError, AssertionError, KeyError, TypeError) as e:
            bad[str(e).split(':')[0][:60] if str(e) else type(e).__name__] += 1
            continue
        used.add(fx['id'])
        good.append(fx)
    by = defaultdict(list)
    for fx in good:
        by[fx['edge_type']].append(fx)
    rng = random.Random(SEED)
    dev, sealed = [], []
    for et in sorted(by):
        xs = sorted(by[et], key=lambda f: f['id'])
        rng.shuffle(xs)
        k = round(DEV_SHARE * len(xs))
        seen = [f for f in xs[k:] if f['plan_n'] in SEEN]  # viewed before the split: never sealed
        xs = [f for f in xs if f not in seen]
        dev += xs[:k - len(seen)] + seen
        sealed += xs[k - len(seen):]
    if SEALED.exists() and any(SEALED.iterdir()):
        raise SystemExit(f'{SEALED} already populated (sealed set is written once)')
    SEALED.mkdir(parents=True, exist_ok=True, mode=0o700)
    FIX2.mkdir(parents=True, exist_ok=True)
    for p in FIX2.glob('*.json'):
        p.unlink()
    for fx in dev:
        (FIX2 / f"{fx['id']}.json").write_text(dump(fx))
    shas = {}
    for fx in sealed:
        t = dump(fx)
        (SEALED / f"{fx['id']}.json").write_text(t)
        (SEALED / f"{fx['id']}.json").chmod(0o600)
        shas[fx['id']] = hashlib.sha256(t.encode()).hexdigest()
    dir_hash = hashlib.sha256(''.join(f'{k} {v}\n' for k, v in sorted(shas.items())).encode()).hexdigest()
    cnt = lambda xs: dict(sorted(Counter(f['edge_type'] for f in xs).items()))  # noqa: E731
    receipt = dict(schema='edge-v2/receipt', seed=SEED, dev_share=DEV_SHARE, raw=len(raws), valid=len(good),
                   dropped_invalid=dict(bad), dev=cnt(dev), sealed=cnt(sealed), n_dev=len(dev), n_sealed=len(sealed),
                   sealed_dir='~/.lcc/bench/edge-v2-sealed', sealed_sha256=dict(sorted(shas.items())),
                   sealed_dir_sha256=dir_hash,
                   dir_hash_rule='sha256 of "<id> <sha256>\\n" lines sorted by id; each sha256 = file bytes',
                   generator=dict(code_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                                  model='claude opus (subscription CLI)', calls_used=opus_cli.calls_used()))
    (OUT / 'edge-v2-receipt.json').write_text(json.dumps(receipt, indent=1) + '\n')
    return {k: v for k, v in receipt.items() if k != 'sealed_sha256'}


def load_dev():
    return [json.loads(p.read_text()) for p in sorted(FIX2.glob('*.json'))]


def check_sealed():
    """Hash check only (does not parse or print any sealed content)."""
    rc = json.loads((OUT / 'edge-v2-receipt.json').read_text())
    got = {p.stem: hashlib.sha256(p.read_bytes()).hexdigest() for p in SEALED.glob('*.json')}
    return got == rc['sealed_sha256']


def load_sealed(i_mean_it=False):
    """Final measurement only (V5_SELECTION_RULE.md step 4)."""
    assert i_mean_it, 'sealed edge v2 is opened once, in the final step'
    assert check_sealed(), 'sealed set changed since the receipt'
    return [json.loads(p.read_text()) for p in sorted(SEALED.glob('*.json'))]


# --- owner review ----------------------------------------------------------------------------------------------
TYPE_PT = dict(contradiction='duas fontes discordam', structured_config='config estruturada (mesma chave, valor '
               'diferente)', source_authority='qual fonte vale mais', qualifier_exception='regra com exceção',
               pt_en_mixed='pedido em português, código em inglês', git_wide_view='git / visão geral do projeto',
               prompt_injection='texto tentando dar ordem dentro de saída de ferramenta', supersession='versão nova '
               'substitui a antiga', coreference='"isso" / "aquele" apontando pra trás', general='caso geral')


def review_pt(cases):
    """One Opus call: plain pt-BR 'situacao' / 'por_que' per case for the owner (cached)."""
    schema = {'type': 'object', 'required': ['rows'], 'properties': {'rows': {'type': 'object', 'additionalProperties': {
        'type': 'object', 'required': ['situacao', 'por_que'],
        'properties': {'situacao': {'type': 'string'}, 'por_que': {'type': 'string'}}}}}}
    src = [dict(id=f['id'], situation=f['situation'], must_keep=f['must_keep']) for f in cases]
    prompt = ('Para cada caso abaixo, escreva em portugues do Brasil simples, sem jargao, para um dono de produto '
              'que nao e programador: "situacao" (1 frase: o que aconteceu na sessao) e "por_que" (1 frase: qual '
              'bloco precisa ficar e por que). Sem travessao. JSON: {"rows": {"<id>": {"situacao", "por_que"}}}.\n\n'
              + json.dumps(src, ensure_ascii=False, indent=1))
    try:
        return opus_cli.call(SYSTEM, schema, prompt, 'review')['rows']
    except Exception as e:  # the English fields stay as a fallback
        print('review_pt failed:', str(e)[:200])
        return {}


def review(n=20):
    """Seeded sample of dev-edge cases -> CSV for the owner (pt-BR, plain words)."""
    dev = load_dev()
    rng = random.Random(SEED + 1)
    pick = sorted(rng.sample(dev, min(n, len(dev))), key=lambda f: f['id'])
    pt = review_pt(pick)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(['caso', 'tipo', 'situacao', 'pedido do usuario', 'blocos que precisam ficar (resumo)', 'por que',
                'ok', 'errado', 'comentario'])
    for f in pick:
        must = [b for b in f['blocks'] if b['gold'] != 'may']
        quem = {'user': 'usuario', 'assistant': 'agente', 'tool': 'ferramenta'}
        kept = ' | '.join(f"[{quem[b['role']]}{' ' + b['tool'] if b.get('tool') else ''}] "
                          + re.sub(r'\s+', ' ', b['text'])[:160] for b in must)
        r = pt.get(f['id']) or {}
        w.writerow([f['id'], TYPE_PT[f['edge_type']], r.get('situacao', f['situation']), f['goal'], kept,
                    r.get('por_que', f['must_keep']), '', '', ''])
    p = OUT / 'edge-v2-review.csv'
    p.write_text(buf.getvalue())
    return dict(path=str(p), rows=len(pick))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('phase', choices=('gen', 'build', 'review', 'check'))
    ap.add_argument('--shards', type=int, default=4)
    ap.add_argument('--limit', type=int)
    a = ap.parse_args(argv)
    out = dict(gen=lambda: gen(a.shards, a.limit), build=build, review=review,
               check=lambda: dict(sealed_ok=check_sealed()))[a.phase]()
    print(json.dumps(out, indent=1, ensure_ascii=False))


if __name__ == '__main__':
    sys.exit(main())
