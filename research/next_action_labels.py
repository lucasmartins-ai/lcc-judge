"""Next-action evidence labels v1: which prior-context blocks did the agent actually rely on?

The frozen v0 probes reward recent blocks (recency AUC .97 in matched-budget v1), so they cannot
tell a good ranker from "keep the newest". This module builds a label source from what the agent
DID after each real human prompt (Claude Code, Codex, Hermes), read-only on the transcript stores.

Item = one human prompt (importer rules: research.import_agent_requests) with prior context that
holds >= 1 assistant block. Per item:

  context  the prior context rebuilt by the bench adapters (real_context_bench.context walk for
           Claude, codex_context.context_items, hermes_context.context_rows), rendered with
           real_context_bench.render and split exactly as LCC block mode splits it
           (lcc.relevance.blocks.split_blocks, min_block_chars=40, max_block_chars=6000 =
           real_context_bench.MECH_KW). Blocks shorter than 40 chars are LCC-protected (always
           kept): labelled, but not candidates. Tokens = LCC heuristic counter (gpt-4.1).
  window   what the agent did after the prompt, in order, until the next human prompt, a user
           slash command, an interrupt, a context compaction, or the end of the transcript:
           tool calls (name + input), assistant text, and the tool results / injected user text
           it received (results are not evidence; they only mark what was re-fetched).

Evidence features (same extractor on blocks and on the window; all thresholds are minimums):
  path    file paths / URLs (>= 8 chars, with '/'; needs a leading '/', '~/', './', >= 3
          components or a file extension). File paths (with an extension) are also matched by
          last-two-components suffix and by basename, each only when >= 12 chars; directories get
          no suffix key. Bare file names (known extensions) count as basename keys under the same
          12-char minimum, and never as identifiers (index.tsx is neither).
  ident   code identifiers >= 6 chars that look like code: contain '_' or '.', a lower->upper
          camel step, or letters + digits; not a file name, not right after a backslash (JSON
          u-escapes such as \\u00e3). Plain words never match. A small stop list drops tool argument keys
          (tool_use_id, file_path, old_string, ...).
  num     decimals with >= 4 digits (0.973) and a non-zero fraction (not 100.0), integers with
          >= 5 digits that are not multiples of 1000.
  hex     hex strings of 7..64 chars with both a letter and a digit (commit SHAs, ids), not
          fragments of a dashed id; whole UUIDs are one hex feature.
  line    whole lines >= 24 chars after whitespace collapse with >= 3 words of >= 2 chars;
          read-out line-number prefixes ('  12→', '12|', '12\\t') and a leading 'cd <path> &&'
          are stripped. JSON-escaped
          tool_use text is also read unescaped, so old Edit inputs match too.
  quoted  `backticked` spans of >= 8 chars in assistant text, not a single plain word, matched as a substring of the
          whitespace-collapsed block (or its unescaped view).

Window evidence rules (a block feature hit through any of these is a match reason):
  edit_anchor  lines of the old text of an edit (old_string / old_text / old_str, apply_patch
               '-' and context lines): the agent edited content it had seen.
  path_op      paths the agent operated on: path-valued call arguments, apply_patch file
               headers, paths in shell commands.
  call_value   any other feature in a tool-call input (commands, patterns, code, new content).
  text_ref     features and quoted spans in the agent's own text (identifiers, error strings,
               numbers, file names it cited).

Anti-trivial filters (applied per item before labelling):
  goal     features also present in the goal are dropped: the agent did not need context for
           them (counted per block as goal_shared, never as evidence).
  common   a feature that hits more than max(3, ceil(5% of labelled blocks)) blocks is
           dropped as non-discriminative (counted as common_dropped).
  ancestor a directory path (no extension) that is a parent of another path in the window, a
           home/project root (/Users/x/Downloads/proj: <= 4 components under /Users or /home;
           ~/Downloads/x: <= 3; also the head of a path cut at a space), a system path (/dev/null) or any path under a temp dir
           (/tmp, /private/tmp, /var/folders: harness task outputs and scratch files carrying
           the session id) is dropped (ancestor_dir_dropped).
  generic  (split phase, before the freeze) a feature kept in the evidence of
           >= max(5, 2% of) TRAIN session groups is flagged generic=true and ignored by the
           labels in every split: language builtins (console.log), /dev/null, brand names.
  refetch  a feature the window had already received in a tool result or injected text before
           the agent used it is recorded with refetched=true: the agent may have read it anew.

Labels per block: used = >= 1 reason with refetched=false (strict, the training label);
used_loose = >= 1 reason at all; n_evidence = strict reasons (a strength to threshold on). Per item, evidence_sets lists every kept feature with ALL the
blocks holding it: a feature is covered when any one of them survives, which is the natural
retention metric when the same identifier sits in several blocks. Items whose window has no agent action are kept, flagged
evidence='none' (every block unused), so consumers can drop them.

Phases (PRIVATE text stays under PRIVATE; the repo gets counts and hashes only):
    build    -> PRIVATE/items/<item_id>.json (+ PRIVATE/texts/<store>.json block id -> text and
                PRIVATE/windows/<store>.json item id -> window events, per transcript),
                PRIVATE/index-<sources>.json, lineage-<sources>.json (one process per source is fine)
    split    session-lineage groups (seed 20261012, per source 70/15/15) -> PRIVATE/splits.json,
                split field written into every item, test items chmod 444, repo receipt
                specialist-v1/labels-receipt.json (counts + sha256 only)
    report   counts per source/category, used rates (train+dev only), sanity checks
                -> PRIVATE/report.json and specialist-v1/labels-report.json (counts only)
    relabel  v2: the current extractor re-run on the stored train+dev items, texts and windows (the
                frozen v1 split and receipt are untouched; test is not opened) -> PRIVATE_V2/items,
                generic features from train groups, content_links() fork detection (train items
                sharing >= 20% of long candidate blocks with a dev item are quarantined from
                training) -> specialist-v1/labels-v2-receipt.json (counts only)

    PYTHONPATH=/Users/Master/.lcc/bench/real-context-v0/lcc-main/src:/Users/Master/Downloads/LCC-judge \\
    /Users/Master/LCC/.venv/bin/python -m research.next_action_labels {build|split|report|relabel}
"""
import argparse
import bisect
import glob
import hashlib
import json
import math
import os
import random
import re
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

from research import codex_context as cc
from research import hermes_context as hc
from research import real_context_bench as rcb

PRIVATE = Path('/Users/Master/.lcc/bench/next-action-v1')
PRIVATE_V2 = Path('/Users/Master/.lcc/bench/next-action-v2')  # relabel phase output (train + dev only)
OUT = rcb.REPO / 'research' / 'goal-engine-2026-10-04' / 'specialist-v1'
RECEIPT = OUT / 'labels-receipt.json'
SEED = 20261012
SPLITS = (('train', 0.70), ('dev', 0.15), ('test', 0.15))
RULESET_PREFIX = '4e99ffac1f9f'
MIN_BLOCK = rcb.MECH_KW['min_block_chars']
MAX_BLOCK = rcb.MECH_KW['max_block_chars']
CLAUDE_ROOT = Path.home() / '.claude' / 'projects'

MIN_PATH, MIN_KEY, MIN_IDENT, MIN_LINE, MIN_QUOTED = 8, 12, 6, 24, 8
COMMON_SHARE, COMMON_MIN = 0.05, 3
GENERIC_SHARE, GENERIC_MIN = 0.02, 5
EXTS = ('py|pyi|ts|tsx|js|jsx|mjs|cjs|md|mdx|json|jsonl|toml|ya?ml|sql|css|scss|html|sh|zsh|go|rs|java|kt|swift'
        '|rb|php|c|h|cc|cpp|hpp|gd|tscn|tres|txt|csv|ini|cfg|env|lock|xml|svg|png|jpe?g|pdf|ipynb|vue|svelte|prisma')
PATH_RE = re.compile(r'https?://[^\s\'"`<>()\[\]{}|\\]+|(?:~|\.{1,2})?/?(?:[\w@+.-]+/)+[\w@+.-]+')
FILE_RE = re.compile(rf'(?<![\w/.-])[\w-][\w.-]*\.(?:{EXTS})(?![\w-])')
EXT_RE = re.compile(rf'\.(?:{EXTS})$')
IDENT_RE = re.compile(r'(?<![\w.\\])[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*')
CAMEL_RE = re.compile(r'[a-z][A-Z]')
NUM_RE = re.compile(r'(?<![\w.])(?:\d+\.\d+|\d{5,})(?![\w.])')
HEX_RE = re.compile(r'(?<![\w-])(?=[0-9a-f]*[a-f])(?=[0-9a-f]*\d)[0-9a-f]{7,64}(?![\w-])')
UUID_RE = re.compile(r'(?<![\w-])[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}(?![\w-])')
QUOTED_RE = re.compile(r'`([^`\n]{%d,300})`' % MIN_QUOTED)
WORD_RE = re.compile(r'\w{2,}')
LINENO_RE = re.compile(r'^\s*\d{1,6}(?:→|\||\t|:\s)')
CD_RE = re.compile(r'^cd\s+\S+\s*(?:&&|;|$)\s*')
HEADER_RE = re.compile(r'^\[m\d{4} (?:user|assistant) [a-z_]+(?: [^\]\n]*)?\]$', re.M)
STOP = frozenset({
    'tool_use', 'tool_result', 'tool_use_id', 'tool_call_id', 'tool_calls', 'tool_name', 'file_path', 'old_string',
    'new_string', 'old_text', 'new_text', 'replace_all', 'is_error', 'exit_code', 'call_id', 'notebook_path',
    'output_mode', 'file_glob', 'timeout_ms', 'run_in_background', 'max_output_tokens', 'yield_time_ms',
    'workdir', 'session_id', 'with_escalated_permissions', 'sandbox_permissions', 'stdout', 'stderr',
})
EDIT_OLD = frozenset({'old_string', 'old_text', 'old_str'})
PATH_KEYS = frozenset({'file_path', 'path', 'notebook_path', 'filePath', 'target_file', 'filename', 'file', 'paths'})
PATCH_KEYS = frozenset({'patch', 'input', 'diff'})
SKIP_KEYS = frozenset({'workdir', 'cwd', 'description', 'timeout', 'timeout_ms', 'limit', 'offset'})


# --- feature extraction (stdlib only; same extractor for blocks and window) ------------------------
def collapse(s):
    return ' '.join(s.split())


def _path_keys(raw):
    p = raw.rstrip('.,:;!?)\'"')
    if p.startswith('./'):
        p = p[2:]
    if len(p) < MIN_PATH or '/' not in p:
        return ()
    if p.startswith(('http://', 'https://')):
        return (p,) if len(p) >= MIN_KEY else ()
    parts = [x for x in p.split('/') if x]
    if not (p.startswith(('/', '~/')) or len(parts) >= 3 or EXT_RE.search(p)):
        return ()  # "and/or", "pt/en", "10/12": not paths
    keys = [p]
    if len(parts) >= 2 and EXT_RE.search(p) and len(s2 := '/'.join(parts[-2:])) >= MIN_KEY:  # files only
        keys.append(s2)
    if len(parts[-1]) >= MIN_KEY and EXT_RE.search(parts[-1]):
        keys.append(parts[-1])
    return keys


def features(text):
    """{(kind, value)} for one text (see module docstring for every rule)."""
    out = set()
    for m in PATH_RE.finditer(text):
        out.update(('path', k) for k in _path_keys(m.group(0)))
    for m in FILE_RE.finditer(text):
        if len(m.group(0)) >= MIN_KEY:
            out.add(('path', m.group(0)))
    for m in IDENT_RE.finditer(text):
        t = m.group(0).rstrip('.')
        if len(t) >= MIN_IDENT and t not in STOP and not EXT_RE.search(t) and (  # file names: FILE_RE, >= 12
                '_' in t or '.' in t or CAMEL_RE.search(t) or (any(c.isdigit() for c in t) and any(c.isalpha() for c in t))):
            out.add(('ident', t))
    for m in NUM_RE.finditer(text):
        t = m.group(0)
        if '.' in t and (sum(c.isdigit() for c in t) < 4 or not t.split('.')[1].strip('0')):
            continue  # short or round decimals (100.0)
        if '.' in t or int(t) % 1000:  # round integers (25000) carry no identity
            out.add(('num', t))
    out.update(('hex', m.group(0)) for m in HEX_RE.finditer(text))
    out.update(('hex', m.group(0)) for m in UUID_RE.finditer(text))
    for line in text.splitlines():
        line = CD_RE.sub('', collapse(LINENO_RE.sub('', line, count=1)))  # 'cd <root> &&' prefix
        if len(line) >= MIN_LINE and len(WORD_RE.findall(line)) >= 3:
            out.add(('line', line))
    return out


def unescape(text):
    """JSON-escaped view of tool_use text (tool inputs are rendered with json.dumps)."""
    if '\\' not in text:
        return None
    return text.replace('\\n', '\n').replace('\\t', '\t').replace('\\"', '"').replace('\\\\', '\\')


def block_view(text):
    """(features, collapsed views) of one LCC block: render headers stripped; a tool_use JSON line
    is read by its string values (exact), any other escaped text through unescape()."""
    body = HEADER_RE.sub('', text)
    feats = features(body)
    views = [collapse(body)]
    for line in body.splitlines():
        if line.startswith('{'):
            try:
                d = json.loads(line)
            except ValueError:
                continue
            for _, v in _strings(d):
                feats |= features(v)
                views.append(collapse(v))
    if (u := unescape(body)) is not None:
        feats |= features(u)
        views.append(collapse(u))
    return feats, views


# --- window evidence -------------------------------------------------------------------------------
def _strings(x, key=None):
    """(key, string) for every string value in a tool input, depth-first."""
    if isinstance(x, str):
        yield key, x
    elif isinstance(x, dict):
        for k, v in x.items():
            yield from _strings(v, k)
    elif isinstance(x, list):
        for v in x:
            yield from _strings(v, key)


def _patch(s):
    """(anchor text, added text, file paths) of an apply_patch / unified diff, or None."""
    if '*** Begin Patch' not in s and not re.search(r'^(?:---|\+\+\+) \S', s, re.M):
        return None
    anchors, added, paths = [], [], []
    for line in s.splitlines():
        m = re.match(r'^\*\*\* (?:Update|Add|Delete) File: (.+)$|^\*\*\* Move to: (.+)$|^(?:---|\+\+\+) (?:[ab]/)?(\S+)', line)
        if m:
            paths.append(next(g for g in m.groups() if g))
        elif line.startswith('*** ') or line.startswith('@@'):
            continue
        elif line.startswith('-'):
            anchors.append(line[1:])
        elif line.startswith('+'):
            added.append(line[1:])
        elif line.startswith(' '):
            anchors.append(line[1:])
    return '\n'.join(anchors), '\n'.join(added), paths


def call_evidence(inp):
    """[(rule, feature)] of one tool-call input."""
    out = []
    for key, s in _strings(inp if isinstance(inp, (dict, list)) else dict(input=inp)):
        if key in SKIP_KEYS:
            continue
        if key in EDIT_OLD:
            out += [('edit_anchor', f) for f in features(s) if f[0] == 'line']
            out += [('call_value', f) for f in features(s) if f[0] != 'line']
            continue
        if key in PATCH_KEYS and (p := _patch(s)) is not None:
            anchors, added, paths = p
            out += [('edit_anchor', f) for f in features(anchors) if f[0] == 'line']
            out += [('call_value', f) for f in features(anchors) | features(added) if f[0] != 'line' or f in features(added)]
            out += [('path_op', ('path', k)) for x in paths for k in _path_keys(x.strip())]
            out += [('path_op', ('path', x.strip())) for x in paths if '/' not in x and len(x.strip()) >= MIN_KEY]
            continue
        fs = features(s)
        if key in PATH_KEYS:
            keys = list(_path_keys(s.strip())) or ([s.strip()] if len(s.strip()) >= MIN_KEY and EXT_RE.search(s.strip()) else [])
            out += [('path_op', ('path', k)) for k in keys]
        out += [('path_op' if f[0] == 'path' else 'call_value', f) for f in fs]
    return out


def text_evidence(text):
    out = [('text_ref', f) for f in features(text)]
    out += [('text_ref', ('quoted', collapse(m.group(1)))) for m in QUOTED_RE.finditer(text)
            if len(collapse(m.group(1))) >= MIN_QUOTED and not m.group(1).strip().isalpha()]  # plain words
    return out


def window_evidence(events):
    """Ordered window events -> {feature: dict(rules, refetched)}.

    events: ('call', name, input) | ('text', text) | ('result', text) | ('user', text).
    A feature is refetched when every agent use of it came after the window had received it in a
    result or injected user text (its first agent use decides)."""
    got, got_text, ev = set(), [], {}
    for e in events:
        if e[0] in ('result', 'user'):
            got |= features(e[-1] or '')
            got_text.append(collapse(e[-1] or ''))
            continue
        pairs = call_evidence(e[2]) if e[0] == 'call' else text_evidence(e[1] or '')
        for rule, f in pairs:
            if f[0] == 'quoted':
                re_f = any(f[1] in t for t in got_text)
            else:
                re_f = f in got
            d = ev.setdefault(f, dict(rules=set(), refetched=re_f))
            d['rules'].add(rule)
    return ev


# --- labelling -------------------------------------------------------------------------------------
def offsets(blocks):
    """Start offset of every dossier block inside rcb.render(blocks)."""
    starts, pos = [], 0
    for b in blocks:
        starts.append(pos)
        pos += len(rcb.header(b)) + 1 + len(b['content']) + 2
    return starts


TEMP_DIRS = ('/tmp/', '/private/tmp/', '/var/folders/', '/private/var/folders/')
SYS_PATHS = frozenset({'/dev/null', '/dev/stdout', '/dev/stderr', '/usr/bin/env', '/bin/bash', '/bin/sh', '/bin/zsh'})


def root_dir(p):
    """Home/user roots and system paths: '/Users/x', '/Users/x/proj', '~/Downloads/x' (also the
    head of a path with spaces cut at the space), '/dev/null'."""
    if p in SYS_PATHS or p.startswith(TEMP_DIRS):
        return True
    parts = [x for x in p.split('/') if x and x != '~']
    if EXT_RE.search(p):
        return False
    if p.startswith(('/Users/', '/home/')):  # home + 2 levels: /Users/x/Downloads/proj (project roots)
        return len(parts) <= 4
    return len(parts) <= 3 and p.startswith(('~', '/tmp', '/private/'))


def match(ev, goal, views):
    """Window evidence x block views -> ([reasons per block], [goal_shared per block], stats, sets).
    views: [(features, collapsed views)] in block order. sets: one row per kept evidence feature
    with every block index holding it (a feature is covered when ANY of its blocks is kept)."""
    hits = defaultdict(set)
    quoted = [f for f in ev if f[0] == 'quoted']
    for i, (f, v) in enumerate(views):
        for x in f & ev.keys():
            hits[x].add(i)
        for q in quoted:
            if any(q[1] in t for t in v):
                hits[q].add(i)
    goal_f, goal_c = features(goal), collapse(goal)
    paths = [f[1] for f in ev if f[0] == 'path']
    anc = {p for p in paths if root_dir(p) or not EXT_RE.search(p) and any(
        q != p and (q.startswith(p + '/') or f'/{p}/' in q) for q in paths)}
    cap = max(COMMON_MIN, math.ceil(COMMON_SHARE * len(views)))
    reasons, shared, st, sets = [[] for _ in views], [0] * len(views), Counter(), []
    for f, idx in hits.items():
        if f in goal_f or (f[0] == 'quoted' and f[1] in goal_c):
            st['goal_dropped'] += 1
            for i in idx:
                shared[i] += 1
        elif len(idx) > cap:
            st['common_dropped'] += 1
        elif f[0] == 'path' and f[1] in anc:
            st['ancestor_dir_dropped'] += 1
        else:
            sets.append(dict(kind=f[0], value=f[1][:120], rules=sorted(ev[f]['rules']), refetched=ev[f]['refetched'],
                             blocks=sorted(idx)))
            for i in idx:
                reasons[i].append(dict(rules=sorted(ev[f]['rules']), kind=f[0], value=f[1][:120],
                                       refetched=ev[f]['refetched']))
    for r in reasons:
        r.sort(key=lambda x: (x['refetched'], x['kind'], x['value']))
    sets.sort(key=lambda x: (x['refetched'], x['kind'], x['value']))
    return reasons, shared, st, sets


def label_item(goal, dossier_blocks, events, split, count, cache, texts=None):
    """-> (block rows, item stats). split(text) -> [(id, text, start, end)]; count(text) -> tokens;
    cache: {block id: (features, views, tokens)} shared by the items of one transcript (ids are
    content-addressed with their index); texts, when given, collects block id -> text."""
    starts = offsets(dossier_blocks)
    rows, views = [], []
    for i, (bid, btext, s, e) in enumerate(split(rcb.render(dossier_blocks))):
        if bid not in cache:
            f, v = block_view(btext)
            cache[bid] = (f, v, count(btext))
        if texts is not None:
            texts[bid] = btext
        f, v, tok = cache[bid]
        lo = bisect.bisect_right(starts, s) - 1
        hi = bisect.bisect_right(starts, max(s, e - 1)) - 1
        src = dossier_blocks[lo]
        rows.append(dict(id=bid, i=i, tokens=tok, chars=len(btext), protected=len(btext) < MIN_BLOCK,
                         m=src['m'], role=src['role'], kind=src['kind'], tool=src['tool_name'],
                         is_error=any(dossier_blocks[j]['is_error'] for j in range(lo, hi + 1)),
                         src=[lo, hi]))
        views.append((f, v))
    ev = window_evidence(events)
    reasons, shared, st, sets = match(ev, goal, views)
    for r, rs, g in zip(rows, reasons, shared):
        r.update(used=any(not x['refetched'] for x in rs), used_loose=bool(rs), goal_shared=g, reasons=rs)
    st['evidence_features'] = len(ev)
    st['evidence_by_rule'] = dict(Counter(rule for d in ev.values() for rule in d['rules']))
    st['evidence_sets'] = sets
    return rows, dict(st)


def lcc_split(text, max_block_chars=MAX_BLOCK):
    """lcc.relevance.blocks.split_blocks spans and ids, built from LCC's own helpers, without its
    per-block line numbering (text.count from 0 per block: quadratic on multi-MB contexts).
    Equality with split_blocks is asserted in tests and on real items in the report phase."""
    from lcc.relevance import blocks as lb
    spans = []
    for start, end in lb._atomic_spans(text):
        spans.extend([(start, end)] if end - start <= max_block_chars
                     else lb._split_oversized(text, start, end, max_block_chars))
    return [(lb.block_id(i, text[s:e]), text[s:e], s, e) for i, (s, e) in enumerate(spans, start=1)]


# --- sources: prompts, prior context, window -------------------------------------------------------
def _iar(rl=None):
    """research.import_agent_requests with lcc.request_log bound to the pinned ruleset module."""
    if rl is not None:
        import lcc
        sys.modules.setdefault('lcc.request_log', rl)
        if not hasattr(lcc, 'request_log'):
            lcc.request_log = rl
    return hc._importer()


def claude_human(d, iar):
    """Importer rules (import_agent_requests.claude) for one record -> prompt text or None."""
    if d.get('type') != 'user' or (d.get('isMeta') or d.get('isSidechain') or d.get('isCompactSummary') or d.get('agentId')
                                   or d.get('toolUseResult') is not None or d.get('sourceToolUseID')
                                   or d.get('sourceToolAssistantUUID') or d.get('entrypoint') in ('sdk-py', 'sdk-ts', 'sdk-cli')):
        return None
    t = iar._claude_text((d.get('message') or {}).get('content'))
    if t is None:
        return None
    s = t.strip()
    return None if s.startswith('<') or s.startswith(iar._CLAUDE_AUTO) else s


def claude_context(recs, uuid):
    """rcb.context_records over an already-parsed {uuid: record} map."""
    out, seen = [], set()
    cur = recs[uuid].get('parentUuid')
    while cur and cur in recs and cur not in seen:
        seen.add(cur)
        r = recs[cur]
        if r.get('type') == 'system' and r.get('subtype') == 'compact_boundary':
            break
        if r.get('type') in ('user', 'assistant'):
            out.append(r)
        cur = r.get('parentUuid')
    return out[::-1]


def claude_window(records, pos, iar):
    """Events after records[pos] (the prompt), file order, main chain only -> (events, ended_by)."""
    ev = []
    for r in records[pos + 1:]:
        if r.get('isSidechain'):
            continue
        if r.get('type') == 'system' and r.get('subtype') == 'compact_boundary':
            return ev, 'compaction'
        msg = r.get('message') if isinstance(r.get('message'), dict) else {}
        content = msg.get('content')
        if r.get('type') == 'user':
            if claude_human(r, iar) is not None:
                return ev, 'next_prompt'
            t = iar._claude_text(content)
            if t is not None:
                s = t.strip()
                if s.startswith('[Request interrupted'):
                    return ev, 'interrupt'
                if s.startswith(('<command-name>', '<command-message>')) and not r.get('isMeta'):
                    return ev, 'next_prompt'
                ev.append(('user', t))
                continue
            for b in content if isinstance(content, list) else ():
                if isinstance(b, dict) and b.get('type') == 'tool_result':
                    ev.append(('result', rcb._result_text(b.get('content'))))
        elif r.get('type') == 'assistant':
            for b in content if isinstance(content, list) else [dict(type='text', text=content or '')]:
                if not isinstance(b, dict):
                    continue
                if b.get('type') == 'text':
                    ev.append(('text', b.get('text') or ''))
                elif b.get('type') == 'tool_use':
                    ev.append(('call', b.get('name'), b.get('input')))
    return ev, 'eof'


def codex_window(records, index, goal):
    """Events after the prompt record at `index` -> (events, ended_by). The duplicate copy of the
    prompt (event_msg + response_item) before any agent item is skipped, not a new prompt."""
    ev, started = [], False
    for r in records[index + 1:]:
        p = cc._payload(r)
        if r.get('type') == 'compacted':
            return ev, 'compaction'
        if r.get('type') == 'event_msg' and p.get('type') == 'turn_aborted':
            return ev, 'interrupt'
        texts = None
        if r.get('type') == 'event_msg' and p.get('type') == 'user_message':
            texts = [p.get('message') or '']
        elif r.get('type') == 'response_item' and p.get('type') == 'message' and p.get('role') == 'user':
            texts = [c.get('text', '') for c in p.get('content') or [] if isinstance(c, dict) and c.get('type') == 'input_text']
        if texts is not None:
            for raw in texts:
                g = cc.goal_of(raw)
                if g is not None or raw.strip().startswith(('PLEASE IMPLEMENT THIS PLAN', 'Automation:')):
                    if not started and g == goal:
                        continue
                    return ev, 'next_prompt'
                ev.append(('user', raw))
            continue
        if r.get('type') != 'response_item':
            continue
        t = p.get('type')
        if t == 'message' and p.get('role') == 'assistant':
            started = True
            for c in p.get('content') or ():
                if isinstance(c, dict) and c.get('type') == 'output_text':
                    ev.append(('text', c.get('text') or ''))
        elif t in ('function_call', 'custom_tool_call', 'tool_search_call'):
            started = True
            if t == 'custom_tool_call':
                inp = dict(input=p.get('input'))
            else:
                raw = p.get('arguments')
                try:
                    inp = json.loads(raw) if isinstance(raw, str) else raw
                except ValueError:
                    inp = dict(arguments=raw)
            ev.append(('call', cc.tool_name(p), inp))
        elif t in ('function_call_output', 'custom_tool_call_output', 'tool_search_output'):
            ev.append(('result', cc._output_text(p.get('tools') if t == 'tool_search_output' else p.get('output'))))
        elif t == 'web_search_call':
            started = True
            ev.append(('call', 'web_search', p.get('action')))
    return ev, 'eof'


def hermes_window(rows, prompt_pos, is_human):
    """Events after rows[prompt_pos] -> (events, ended_by). is_human(row) marks the next prompt."""
    ev = []
    for r in rows[prompt_pos + 1:]:
        if r['_compressed_summary']:
            return ev, 'compaction'
        if r['role'] == 'user':
            if is_human(r):
                return ev, 'next_prompt'
            ev.append(('user', r['content'] or ''))
        elif r['role'] == 'assistant':
            if (r['content'] or '').strip():
                ev.append(('text', r['content']))
            try:
                calls = json.loads(r['tool_calls']) if r['tool_calls'] else []
            except ValueError:
                calls = []
            for c in calls if isinstance(calls, list) else ():
                fn = c.get('function') if isinstance(c, dict) and isinstance(c.get('function'), dict) else {}
                raw = fn.get('arguments')
                try:
                    inp = json.loads(raw) if isinstance(raw, str) else raw
                except ValueError:
                    inp = dict(arguments=raw)
                ev.append(('call', fn.get('name'), inp))
        elif r['role'] == 'tool':
            ev.append(('result', r['content'] or ''))
    return ev, 'eof'


def json_wrapped(t):
    """Hermes stores multimodal user content as '\\x00json:[{type, text}, ...]': its text parts,
    or t itself when not wrapped (the importer keeps the wrapper, so e.g. an injected 'Resume
    prior conversation' notice slips through as a prompt)."""
    if not t.startswith('\x00json:'):
        return t
    try:
        parts = json.loads(t[6:])
    except ValueError:
        return t
    return '\n'.join(x.get('text') or '' for x in parts if isinstance(x, dict) and x.get('type') == 'text').strip() \
        if isinstance(parts, list) else t


def window_stats(events, ended_by):
    calls = [e for e in events if e[0] == 'call']
    return dict(ended_by=ended_by, calls=len(calls), texts=sum(e[0] == 'text' for e in events),
                results=sum(e[0] == 'result' for e in events), tools=dict(Counter(str(e[1]) for e in calls)))


# --- lineage (session groups for the split) ---------------------------------------------------------
class Union:
    def __init__(self):
        self.p = {}

    def find(self, x):
        self.p.setdefault(x, x)
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def join(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[max(ra, rb)] = min(ra, rb)


def h16(s):
    return hashlib.sha256(s.encode()).hexdigest()[:16]


# --- category labels --------------------------------------------------------------------------------
def category_labels():
    """{prompt id: (label, confidence, source)}: owner > taxonomy v2 LLM pass > bench LLM / pool labels."""
    tax = Path.home() / '.lcc' / 'request-log' / 'taxonomy-v1'
    out = {}

    def jl(p):
        return [json.loads(x) for x in Path(p).read_text().splitlines() if x.strip()] if Path(p).exists() else []

    for p in sorted(glob.glob(str(Path.home() / '.lcc' / 'bench' / '*' / 'labels-llm-v2.jsonl'))):
        for d in jl(p):
            out.setdefault(d['id'], (d['label'], d.get('confidence'), d.get('label_source') or 'llm_bench_v2'))
    v0 = Path.home() / '.lcc' / 'bench' / 'real-context-v0'
    for d in jl(v0 / 'labels-claude-extra.jsonl'):
        out[d['id']] = (d['label'], d.get('confidence'), 'llm_v0_claude_extra')
    if (v0 / 'pool.json').exists():
        for rid, v in json.loads((v0 / 'pool.json').read_text()).items():
            if 'owner_v1' in v:
                out[rid] = (v['owner_v1'], 'high', 'owner_v1')
            elif 'label' in v:
                out[rid] = (v['label'], v.get('confidence'), 'llm_v0_pool')
    for p in sorted(glob.glob(str(tax / 'labels-v2-*.jsonl'))):
        for d in jl(p):
            if out.get(d['id'], ('', '', ''))[2] != 'owner_v1':
                out[d['id']] = (d['label'], d.get('confidence'), 'llm_v2_pass')
    if (tax / 'owner-judgments.json').exists():
        for d in json.loads((tax / 'owner-judgments.json').read_text()):
            if d['id'] in out and d['proposed'] == out[d['id']][0]:
                out[d['id']] = (d['owner_label'], 'high', 'owner_confirmed_v2' if d['owner_verdict'] == 'right' else 'owner_corrected_v2')
    return out


# --- build ------------------------------------------------------------------------------------------
class Builder:
    def __init__(self, root=PRIVATE, limit=None):
        self.rl = rcb.load_request_log(RULESET_PREFIX)
        self.iar = _iar(self.rl)
        self.cats = category_labels()
        self.root = Path(root)
        (self.root / 'items').mkdir(parents=True, exist_ok=True)
        (self.root / 'texts').mkdir(exist_ok=True)
        (self.root / 'windows').mkdir(exist_ok=True)
        self.split = self.checked_split
        self.count = lambda s: rcb.lcc_count(s)[0]
        self.limit = limit
        self.index, self.skips, self.lineage = [], Counter(), Union()

    def checked_split(self, text):
        """lcc_split, compared against the real split_blocks on every 25th item under 3 MB."""
        out = lcc_split(text)
        if len(self.index) % 25 == 0 and len(text) < 3_000_000:
            from lcc.relevance.blocks import split_blocks
            if out != [(b.id, b.text, b.character_start, b.character_end)
                       for b in split_blocks(text, min_block_chars=MIN_BLOCK, max_block_chars=MAX_BLOCK)]:
                raise SystemExit('lcc_split differs from split_blocks')
            self.skips['split_checked_equal'] += 1
        return out

    def pid(self, source, goal):
        return hashlib.sha256(f'{source}\0{self.rl.redact(goal)[:self.rl.MAX_GOAL_CHARS]}'.encode()).hexdigest()[:16]

    def emit(self, source, key, session, goal, dossier_blocks, events, ended_by, store, cache, texts, windows):
        if not any(b['role'] == 'assistant' for b in dossier_blocks):
            self.skips[f'{source}:no_prior_assistant'] += 1
            return
        if not goal or cc._SLASH.fullmatch(goal):
            self.skips[f'{source}:empty_or_slash_goal'] += 1
            return
        rows, st = label_item(goal, dossier_blocks, events, self.split, self.count, cache, texts)
        sets = st.pop('evidence_sets')
        cand = [r for r in rows if not r['protected']]
        if not cand:
            self.skips[f'{source}:no_candidates'] += 1
            return
        iid = h16(f'{source}\0{key}')
        pid = self.pid(source, goal)
        cat = self.cats.get(pid)
        ws = window_stats(events, ended_by)
        windows[iid] = events
        item = dict(item_id=iid, source=source, prompt_id=pid, session=h16(f'{source}:{session}'), text_store=store,
                    goal=goal, category=cat[0] if cat else None, category_confidence=cat[1] if cat else None,
                    category_source=cat[2] if cat else None, window=ws,
                    evidence='actions' if ws['calls'] or ws['texts'] else 'none', stats=st,
                    n_blocks=len(rows), n_candidates=len(cand), tokens_candidates=sum(r['tokens'] for r in cand),
                    used_candidates=sum(r['used'] for r in cand), evidence_sets=sets, blocks=rows)
        (self.root / 'items' / f'{iid}.json').write_text(json.dumps(item, ensure_ascii=False))
        self.index.append(dict(item_id=iid, source=source, session=item['session'], category=item['category'],
                               n_candidates=len(cand), used=item['used_candidates'], evidence=item['evidence']))
        if self.limit and len(self.index) >= self.limit:
            raise StopIteration

    def run_store(self, source, store, prompts):
        """prompts: iterable of (key, session, goal, dossier_blocks, events, ended_by). Block texts and
        windows of one transcript go to texts/<store>.json and windows/<store>.json."""
        cache, texts, windows = {}, {}, {}
        try:
            for key, session, goal, db, ev, ended in prompts:
                self.emit(source, key, session, goal, db, ev, ended, store, cache, texts, windows)
        finally:
            if windows:
                (self.root / 'texts' / f'{store}.json').write_text(json.dumps(texts, ensure_ascii=False))
                (self.root / 'windows' / f'{store}.json').write_text(json.dumps(windows, ensure_ascii=False, default=str))

    # Claude --------------------------------------------------------------------------------------
    def claude(self, root=CLAUDE_ROOT):
        seen = set()
        for f in sorted(Path(root).rglob('*.jsonl')):
            if 'subagents' in f.relative_to(root).parts or self.iar.is_denied(f):
                continue
            records = [d for d in self.iar._lines(f, Counter())]
            recs = {d['uuid']: d for d in records if d.get('uuid')}
            store = 'claude-' + h16(str(f))

            def gen():
                for pos, d in enumerate(records):
                    goal = claude_human(d, self.iar)
                    if goal is None or not d.get('uuid'):
                        continue
                    sid = d.get('sessionId') or f.stem
                    self.lineage.join(f'claude:{sid}', f'claude:file:{f}')
                    self.lineage.join(f'claude:{sid}', f'claude:uuid:{d["uuid"]}')
                    if d['uuid'] in seen:
                        self.skips['claude:duplicate_uuid'] += 1
                        continue
                    seen.add(d['uuid'])
                    ctx = rcb.render_blocks(claude_context(recs, d['uuid']))
                    ev, ended = claude_window(records, pos, self.iar)
                    yield d['uuid'], sid, goal, ctx, ev, ended

            self.run_store('claude', store, gen())

    # Codex ---------------------------------------------------------------------------------------
    def codex(self, root=cc.ROOT):
        seen = set()
        for path in sorted(glob.glob(str(Path(root) / 'sessions' / '**' / 'rollout-*.jsonl'), recursive=True)):
            records = cc.read_rollout(path)
            store = 'codex-' + h16(path)

            def gen():
                sid0 = Path(path).stem[-36:]
                for i, sid, human, raw in cc.prompt_records(records):
                    sid = sid or sid0
                    g = cc.goal_of(raw)
                    if not human or g is None:
                        continue
                    ts = records[i].get('timestamp')
                    self.lineage.join(f'codex:{sid}', f'codex:prompt:{ts}\0{g}')
                    if (sid, g) in seen or (ts, g) in seen:  # resumed / forked rollouts replay turns
                        self.skips['codex:replay_or_copy'] += 1
                        continue
                    seen.update({(sid, g), (ts, g)})
                    ctx = cc.render_blocks(cc.context_items(records, i))
                    ev, ended = codex_window(records, i, g)
                    yield f'{sid}\0{i}\0{ts}\0{g}', sid, g, ctx, ev, ended  # one record can hold 2 prompts

            self.run_store('codex', store, gen())

    # Hermes --------------------------------------------------------------------------------------
    def hermes(self, root=hc.ROOT):
        con = hc.connect(root)
        clean = self.iar._hermes_clean
        by_sid = defaultdict(list)
        for t, sid, iso in self.iar.hermes(root, Counter()):
            t = (t or '').strip()
            if t and iso is not None:
                by_sid[sid].append((datetime.fromisoformat(iso).timestamp(), t))
        for sid, parent in con.execute('select id, parent_session_id from sessions'):
            if parent:
                self.lineage.join(f'hermes:{sid}', f'hermes:{parent}')
        for sid in sorted(by_sid):
            rows = hc.session_rows(con, sid)
            kinds = dict(con.execute('select id, display_kind from messages where session_id=?', (sid,)).fetchall())

            def is_human(r):
                if r['role'] != 'user' or kinds.get(r['id']) not in (None, 'steer'):
                    return False
                t = json_wrapped(clean(r['content'] or ''))
                return bool(t) and not t.startswith(self.iar._HERMES_DROP) and not (
                    t.startswith('Read the file ') and 'answer' in t[:200])

            def gen():
                for ts, goal in by_sid[sid]:
                    pos = next((k for k, r in enumerate(rows) if r['role'] == 'user' and abs(r['timestamp'] - ts) < 1e-3
                                and clean(r['content'] or '') == goal), None)
                    if pos is None:
                        self.skips['hermes:prompt_row_missing'] += 1
                        continue
                    text = json_wrapped(goal)
                    if text != goal and (not text or text.startswith(self.iar._HERMES_DROP)):
                        self.skips['hermes:injected_json_wrapped'] += 1
                        continue
                    ctx = hc.render_blocks(hc.context_rows(rows, rows[pos]['timestamp']))
                    ev, ended = hermes_window(rows, pos, is_human)
                    yield f'{sid}\0{ts}', sid, text, ctx, ev, ended

            self.lineage.find(f'hermes:{sid}')
            self.run_store('hermes', 'hermes-' + h16(sid), gen())
        con.close()


def build_phase(root=PRIVATE, sources=('claude', 'codex', 'hermes'), limit=None):
    rcb.check_lcc(rcb.load_protocol())
    b = Builder(root, limit)
    try:
        for s in sources:
            getattr(b, s)()
    except StopIteration:
        pass
    lineage = {k: b.lineage.find(k) for k in list(b.lineage.p)}
    tag = '+'.join(sources)  # one process per source can run in parallel; split merges them
    (Path(root) / f'index-{tag}.json').write_text(json.dumps(dict(items=b.index, skips=dict(b.skips)), indent=0))
    (Path(root) / f'lineage-{tag}.json').write_text(json.dumps(lineage))
    return dict(items=len(b.index), per_source=dict(Counter(r['source'] for r in b.index)), skips=dict(b.skips))


def apply_generic(item, generic):
    """Flag reasons/evidence sets whose feature is generic (matched in the evidence of many train
    session groups: language builtins, home/repo roots, the owner's brand names) and recompute the
    block labels without them."""
    for e in item['evidence_sets']:
        e['generic'] = (e['kind'], e['value']) in generic
    for b in item['blocks']:
        for x in b['reasons']:
            x['generic'] = (x['kind'], x['value']) in generic
        b['used'] = any(not x['refetched'] and not x['generic'] for x in b['reasons'])
        b['used_loose'] = any(not x['generic'] for x in b['reasons'])
        b['n_evidence'] = sum(not x['refetched'] and not x['generic'] for x in b['reasons'])
    item['used_candidates'] = sum(b['used'] for b in item['blocks'] if not b['protected'])
    return item


def generic_features(items_by_group, n_groups):
    """{(kind, value)} kept in the evidence of >= max(GENERIC_MIN, GENERIC_SHARE * n_groups) groups."""
    df = Counter()
    for group, sets in items_by_group.items():
        df.update(sets)
    need = max(GENERIC_MIN, GENERIC_SHARE * n_groups)
    return {f for f, n in df.items() if n >= need}


# --- split ------------------------------------------------------------------------------------------
def assign_splits(groups_by_source, seed=SEED):
    """{source: [group keys]} -> {group: split}. Per source: sort, one Random(seed) shuffle per
    source in sorted source order, then the first 70% train, next 15% dev, rest test."""
    rng = random.Random(seed)
    out = {}
    for src in sorted(groups_by_source):
        g = sorted(set(groups_by_source[src]))
        rng.shuffle(g)
        n = len(g)
        a, b = round(SPLITS[0][1] * n), round((SPLITS[0][1] + SPLITS[1][1]) * n)
        for k, x in enumerate(g):
            out[x] = 'train' if k < a else 'dev' if k < b else 'test'
    return out


def split_phase(root=PRIVATE, out=OUT):
    root, out = Path(root), Path(out)
    receipt = out / RECEIPT.name
    if receipt.exists():
        raise SystemExit(f'{receipt} exists: the test split is frozen; refusing to re-split')
    lineage, index, skips = {}, [], Counter()
    for p in sorted(root.glob('lineage-*.json')):
        lineage.update(json.loads(p.read_text()))  # sources never share lineage keys
    for p in sorted(root.glob('index-*.json')):
        d = json.loads(p.read_text())
        index += d['items']
        skips.update(d['skips'])
    if len({it['item_id'] for it in index}) != len(index):
        raise SystemExit('duplicate item ids across index files')
    session_group = {}
    for k, g in lineage.items():
        src = k.split(':', 1)[0]
        if not k.startswith(f'{src}:file:') and not k.startswith(f'{src}:uuid:') and not k.startswith(f'{src}:prompt:'):
            session_group[h16(k)] = h16(g)
    by_src = defaultdict(set)
    for it in index:
        it['group'] = session_group.get(it['session'], it['session'])
        by_src[it['source']].add(it['group'])
    split = assign_splits(by_src)
    train = defaultdict(set)  # generic features: from TRAIN groups only
    for it in index:
        if split[it['group']] == 'train':
            d = json.loads((root / 'items' / f"{it['item_id']}.json").read_text())
            train[it['group']].update((e['kind'], e['value']) for e in d['evidence_sets'])
    generic = generic_features(train, len(train))
    (root / 'generic-features.json').write_text(json.dumps(sorted(generic), ensure_ascii=False))
    manifest = defaultdict(list)
    for it in index:
        p = root / 'items' / f"{it['item_id']}.json"
        d = apply_generic(json.loads(p.read_text()), generic)
        d['group'], d['split'] = it['group'], split[it['group']]
        it['used'] = d['used_candidates']
        data = json.dumps(d, ensure_ascii=False)
        p.write_text(data)
        it['split'] = d['split']
        manifest[d['split']].append((it['item_id'], hashlib.sha256(data.encode()).hexdigest(), d['text_store']))
    stores = defaultdict(set)
    for s, rows in manifest.items():
        for _, _, st in rows:
            stores[s].add(st)
    rec = dict(seed=SEED, splits=dict(SPLITS), unit='session lineage group, per source', created='2026-10-12',
               generic_features=dict(n=len(generic), from_train_groups=len(train),
                                     rule=f'>= max({GENERIC_MIN}, {GENERIC_SHARE} x train groups)'),
               skips=dict(sorted(skips.items())), counts={}, sha256={})
    for s in ('train', 'dev', 'test'):
        rows = sorted(manifest[s])
        lines = ''.join(f'{i} {h}\n' for i, h, _ in rows)
        (root / f'manifest-{s}.txt').write_text(lines)
        st_lines = ''.join(f'{x} {rcb.sha256_file(root / "texts" / (x + ".json"))}\n' for x in sorted(stores[s])
                           if (root / 'texts' / f'{x}.json').exists())
        (root / f'manifest-{s}-texts.txt').write_text(st_lines)
        its = [it for it in index if it.get('split') == s]
        rec['counts'][s] = dict(items=len(its), groups=len({it['group'] for it in its}),
                                per_source=dict(sorted(Counter(it['source'] for it in its).items())),
                                per_category=dict(sorted(Counter(it['category'] or 'unlabelled' for it in its).items())),
                                no_action_items=sum(it['evidence'] == 'none' for it in its),
                                candidate_blocks=sum(it['n_candidates'] for it in its))
        rec['sha256'][s] = dict(items_manifest=hashlib.sha256(lines.encode()).hexdigest(),
                                texts_manifest=hashlib.sha256(st_lines.encode()).hexdigest())
    rec['sha256']['group_assignment'] = hashlib.sha256(''.join(f'{g} {split[g]}\n' for g in sorted(split)).encode()).hexdigest()
    shared = stores['test'] & (stores['train'] | stores['dev'])
    per_group = defaultdict(set)
    for it in index:
        per_group[it['group']].add(it['split'])
    rec['leak_check'] = dict(groups_in_more_than_one_split=sum(len(v) > 1 for v in per_group.values()),
                             text_stores_shared_with_test=len(shared))
    (root / 'splits.json').write_text(json.dumps(dict(groups=split, items={it['item_id']: it['split'] for it in index})))
    for i, _, _ in manifest['test']:
        os.chmod(root / 'items' / f'{i}.json', 0o444)
    out.mkdir(parents=True, exist_ok=True)
    receipt.write_text(json.dumps(rec, indent=1) + '\n')
    return rec


# --- report -----------------------------------------------------------------------------------------
def _rate(k, n):
    return dict(k=k, n=n, rate=round(k / n, 4) if n else None)


def _views(it, texts):
    return [block_view(texts.get(b['id']) or '') for b in it['blocks']]


def placebo(items, texts_of, window_of, rng, generic=frozenset(), n=200):
    """Item A's window evidence matched against item B's blocks, A and B from different session
    groups: the strict used rate of chance matches, next to B's real used rate (same B items)."""
    pool = [it for it in items if it['evidence'] == 'actions']
    fake = real = tot = pairs = 0
    for _ in range(n if len(pool) > 1 else 0):
        a, b = rng.sample(pool, 2)
        if a['group'] == b['group']:
            continue
        reasons, _, _, _ = match(window_evidence(window_of(a)), b['goal'], _views(b, texts_of(b)))
        for blk, rs in zip(b['blocks'], reasons):
            if not blk['protected']:
                fake += any(not x['refetched'] and (x['kind'], x['value']) not in generic for x in rs)
                real += blk['used']
                tot += 1
        pairs += 1
    return dict(pairs=pairs, placebo=_rate(fake, tot), real=_rate(real, tot))


def window_raw(events):
    """(tool-input text, agent text) of a window, collapsed, with JSON-escaped views unescaped."""
    calls = [collapse(unescape(j) or j) for e in events if e[0] == 'call'
             for j in [json.dumps(e[2], ensure_ascii=False)]]
    texts = [collapse(e[1] or '') for e in events if e[0] == 'text']
    return '\n'.join(calls), '\n'.join(texts)


def report_phase(root=PRIVATE, out=OUT, sample=20):
    root, out = Path(root), Path(out)
    splits = json.loads((root / 'splits.json').read_text())['items']
    tstore = {}

    def texts_of(it):
        s = it['text_store']
        if s not in tstore:
            if len(tstore) > 64:
                tstore.clear()
            tstore[s] = json.loads((root / 'texts' / f'{s}.json').read_text())
        return tstore[s]

    wstore = {}

    def window_of(it):
        s = it['text_store']
        if s not in wstore:
            if len(wstore) > 64:
                wstore.clear()
            wstore[s] = json.loads((root / 'windows' / f'{s}.json').read_text())
        return wstore[s][it['item_id']]

    counts = defaultdict(Counter)
    open_items = []
    for iid, s in splits.items():
        counts[s]['items'] += 1
        if s == 'test':
            continue  # frozen: counts only, never opened for statistics
        open_items.append(json.loads((root / 'items' / f'{iid}.json').read_text()))
    rep = dict(note='used rates over train+dev only; test is frozen (counts in labels-receipt.json)')
    by = lambda key: defaultdict(lambda: Counter())  # noqa: E731
    per_src, per_cat, kind, dec, ended = by(0), by(0), by(0), by(0), Counter()
    tok_used = tok_all = 0
    zero_used = all_used = none_ev = 0
    used_per_item = []
    rule_hits = Counter()
    for it in open_items:
        cand = [b for b in it['blocks'] if not b['protected']]
        u = sum(b['used'] for b in cand)
        ul = sum(b['used_loose'] for b in cand)
        for key, tab in ((it['source'], per_src), (it['category'] or 'unlabelled', per_cat)):
            tab[key].update(items=1, blocks=len(cand), used=u, used_loose=ul,
                            items_with_used=int(u > 0))
        ended[it['window']['ended_by']] += 1
        none_ev += it['evidence'] == 'none'
        zero_used += u == 0
        all_used += u == len(cand)
        used_per_item.append(u)
        n = len(cand)
        for j, b in enumerate(cand):
            kind[f"{b['role']}:{b['kind']}"].update(blocks=1, used=int(b['used']))
            dec[min(9, j * 10 // n)].update(blocks=1, used=int(b['used']))
            tok_all += b['tokens']
            tok_used += b['tokens'] * b['used']
            for x in b['reasons']:
                if not x['refetched']:
                    rule_hits.update(x['rules'])
    tab = lambda t: {k: dict(v, used_rate=round(v['used'] / v['blocks'], 4) if v['blocks'] else None,  # noqa: E731
                             item_used_rate=round(v['items_with_used'] / v['items'], 4) if v.get('items') else None)
                     for k, v in sorted(t.items(), key=lambda kv: str(kv[0]))}
    rep.update(items=dict(counts={s: dict(c) for s, c in counts.items()}),
               per_source=tab(per_src), per_category=tab(per_cat),
               used_block_rate=_rate(sum(v['used'] for v in per_src.values()), sum(v['blocks'] for v in per_src.values())),
               used_loose_block_rate=_rate(sum(v['used_loose'] for v in per_src.values()), sum(v['blocks'] for v in per_src.values())),
               used_token_share=round(tok_used / tok_all, 4) if tok_all else None,
               used_per_item=dict(median=statistics.median(used_per_item) if used_per_item else None,
                                  zero_used_items=zero_used, all_used_items=all_used, no_action_items=none_ev),
               window_ended_by=dict(ended), reason_rules_strict=dict(rule_hits),
               by_block_kind={k: dict(v, used_rate=round(v['used'] / v['blocks'], 4)) for k, v in sorted(kind.items())},
               by_position_decile={str(k): dict(v, used_rate=round(v['used'] / v['blocks'], 4)) for k, v in sorted(dec.items())})
    # sanity 1: 20 random items, every strict reason of every used block re-checked by raw substring
    # search, independent of the feature sets: in the block text, and in the window's tool inputs/text
    rng = random.Random(SEED)
    picked = rng.sample(open_items, min(sample, len(open_items)))
    in_block = in_inputs = in_any = tool_rule = used_n = 0
    private_rows = []
    for it in picked:
        texts = texts_of(it)
        calls, said = window_raw(window_of(it))
        for b in it['blocks']:
            if not b['used']:
                continue
            used_n += 1
            body = texts.get(b['id']) or ''
            raw = '\n'.join(block_view(body)[1])  # collapsed text, JSON-decoded values, unescaped view
            strict = [x for x in b['reasons'] if not x['refetched']]
            in_block += all(x['value'] in raw for x in strict)
            in_inputs += any(x['value'] in calls for x in strict)
            in_any += any(x['value'] in calls or x['value'] in said for x in strict)
            tool_rule += any(set(x['rules']) & {'edit_anchor', 'path_op', 'call_value'} for x in strict)
        private_rows.append(dict(item_id=it['item_id'], source=it['source'], category=it['category'],
                                 goal=it['goal'][:300], candidates=it['n_candidates'], used=it['used_candidates'],
                                 window=it['window'],
                                 used_blocks=[dict(i=b['i'], kind=b['kind'], tool=b['tool'], reasons=b['reasons'][:4],
                                                   head=(texts.get(b['id']) or '')[:200]) for b in it['blocks'] if b['used']][:8]))
    rep['sanity'] = dict(
        sample_items=len(picked), sample_used_blocks=used_n,
        reasons_found_in_block_text=_rate(in_block, used_n),
        used_referenced_by_later_tool_inputs=_rate(in_inputs, used_n),
        used_referenced_by_later_inputs_or_text=_rate(in_any, used_n),
        used_with_a_tool_input_rule=_rate(tool_rule, used_n),
        placebo_cross_session=placebo(open_items, texts_of, window_of, random.Random(SEED + 1),
                                      {tuple(x) for x in json.loads((root / 'generic-features.json').read_text())}))
    (root / 'report-sample.json').write_text(json.dumps(private_rows, ensure_ascii=False, indent=1))
    (root / 'report.json').write_text(json.dumps(rep, indent=1))
    (out / 'labels-report.json').write_text(json.dumps(rep, indent=1) + '\n')
    return rep


# --- relabel (v2 extractor on the frozen v1 split; train + dev only) ---------------------------------
def relabel_item(item, texts, events):
    """Re-run match() with the current extractor on one stored item (block texts + window events).
    Returns the item with labels, stats and evidence_sets replaced; generic flags are applied later."""
    views = [block_view(texts.get(b['id']) or '') for b in item['blocks']]
    ev = window_evidence(events)
    reasons, shared, st, sets = match(ev, item['goal'], views)
    for b, rs, g in zip(item['blocks'], reasons, shared):
        b.update(used=any(not x['refetched'] for x in rs), used_loose=bool(rs), goal_shared=g, reasons=rs)
    st['evidence_features'] = len(ev)
    st['evidence_by_rule'] = dict(Counter(rule for d in ev.values() for rule in d['rules']))
    item['stats'], item['evidence_sets'] = dict(st), sets
    return item


def content_links(items, min_chars=200, share=0.2, min_shared=3):
    """{(a, b)} item-id pairs (a < b) from different lineage groups whose candidate blocks of >= min_chars
    share >= `share` of either item's such blocks (and >= min_shared of them: one common preamble block does
    not link two short items) by LCC block id (content + index: a copied/forked prefix).
    Catches forks the (sid, goal) / (ts, goal) lineage joins miss (label review 2026-10-12)."""
    holders, n = defaultdict(list), {}
    for it in items:
        ids = {b['id'] for b in it['blocks'] if not b['protected'] and b['chars'] >= min_chars}
        n[it['item_id']] = len(ids)
        for b in ids:
            holders[b].append(it)
    pair = Counter()
    for hs in holders.values():
        for x in range(len(hs)):
            for y in range(x + 1, len(hs)):
                a, b = hs[x], hs[y]
                if a['group'] != b['group']:
                    pair[tuple(sorted((a['item_id'], b['item_id'])))] += 1
    return {p for p, k in pair.items() if k >= max(min_shared, share * min(n[p[0]], n[p[1]]))}


def relabel_phase(src=PRIVATE, dst=PRIVATE_V2, out=OUT, splits=('train', 'dev')):
    """v1 items + stored texts/windows -> dst/items with the current extractor. TEST is never read:
    only ids whose split is in `splits` are opened, and text/window stores are per transcript and never
    shared with test (labels-receipt leak_check). Generic features are recomputed from TRAIN groups."""
    if 'test' in splits:
        raise SystemExit('relabel never opens the frozen test split')
    src, dst = Path(src), Path(dst)
    sp = json.loads((src / 'splits.json').read_text())['items']
    want = sorted(i for i, s in sp.items() if s in splits)
    (dst / 'items').mkdir(parents=True, exist_ok=True)
    by_store = defaultdict(list)
    for iid in want:  # pass 1: store of each item (slim; items are large)
        it = json.loads((src / 'items' / f'{iid}.json').read_text())
        by_store[it['text_store']].append(iid)
    train, slim, split_of = defaultdict(set), [], {}
    for k, (store, iids) in enumerate(sorted(by_store.items())):
        texts = json.loads((src / 'texts' / f'{store}.json').read_text())
        windows = json.loads((src / 'windows' / f'{store}.json').read_text())
        for iid in iids:
            it = relabel_item(json.loads((src / 'items' / f'{iid}.json').read_text()), texts, windows[iid])
            (dst / 'items' / f'{iid}.json').write_text(json.dumps(it, ensure_ascii=False))
            split_of[iid] = it['split']
            if it['split'] == 'train':
                train[it['group']].update((e['kind'], e['value']) for e in it['evidence_sets'])
            slim.append(dict(item_id=iid, group=it['group'], blocks=[
                dict(id=b['id'], chars=b['chars'], protected=b['protected']) for b in it['blocks']
                if not b['protected'] and b['chars'] >= 200]))
        if k % 50 == 0:
            print('relabel', k, len(by_store), flush=True)
    generic = generic_features(train, len(train))
    links = content_links(slim)
    del slim
    linked = defaultdict(set)
    for a, b in links:
        linked[a].add(b)
        linked[b].add(a)
    quarantine = sorted(i for i in split_of if split_of[i] == 'train' and any(split_of[j] == 'dev' for j in linked[i]))
    used = Counter()
    for iid in split_of:  # pass 2: generic flags
        p = dst / 'items' / f'{iid}.json'
        it = apply_generic(json.loads(p.read_text()), generic)
        it['content_linked'] = sorted(linked[iid])
        p.write_text(json.dumps(it, ensure_ascii=False))
        cand = [b for b in it['blocks'] if not b['protected']]
        used[it['split'] + ':blocks'] += len(cand)
        used[it['split'] + ':used'] += sum(b['used'] for b in cand)
        used[it['split'] + ':items_with_used'] += any(b['used'] for b in cand)
    (dst / 'generic-features.json').write_text(json.dumps(sorted(generic), ensure_ascii=False))
    (dst / 'splits.json').write_text(json.dumps(dict(items=dict(sorted(split_of.items())),
                                                     train_quarantined_dev_overlap=quarantine)))
    rec = dict(labels='next-action-v2 (relabel of the frozen v1 split, train+dev only; test untouched, v1 extractor '
                      'stays on test until the final run relabels it with this same code)',
               items={s: sum(v == s for v in split_of.values()) for s in splits},
               generic_features=len(generic), content_links=len(links),
               content_links_train_dev=sum(split_of[a] != split_of[b] for a, b in links),
               train_quarantined_dev_overlap=len(quarantine), counts=dict(sorted(used.items())))
    out.mkdir(parents=True, exist_ok=True)
    (out / 'labels-v2-receipt.json').write_text(json.dumps(rec, indent=1) + '\n')
    return rec


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('phase', choices=('build', 'split', 'report', 'relabel'))
    ap.add_argument('--sources', default='claude,codex,hermes')
    ap.add_argument('--limit', type=int)
    ap.add_argument('--root', default=str(PRIVATE))
    ap.add_argument('--out', default=str(OUT), help='repo folder for the receipt/report (counts only)')
    a = ap.parse_args(argv)
    if a.phase == 'build':
        out = build_phase(Path(a.root), tuple(a.sources.split(',')), a.limit)
    elif a.phase == 'split':
        out = split_phase(Path(a.root), Path(a.out))
    elif a.phase == 'report':
        out = report_phase(Path(a.root), Path(a.out))
    else:
        out = relabel_phase(Path(a.root), PRIVATE_V2, Path(a.out))
    print(json.dumps(out, indent=1)[:6000])


if __name__ == '__main__':
    main()
