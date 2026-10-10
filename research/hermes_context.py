"""Hermes adapter for the real-context bench: rebuild the context a Hermes prompt was sent into.

Read-only on ~/.hermes/state.db (opened mode=ro). Prompts come from the importer's own Hermes
extractor (research.import_agent_requests.hermes: human sources only, same cleaning, drops and
dedup), so ids match ~/.lcc/request-log/imported/hermes.jsonl. For one prompt, the context is
every message row of the same session written before the prompt row, mapped to:

  (a) the harness dossier blocks of research.real_context_bench (m, role, kind, tool_name,
      tool_use_id, is_error, content), so probes, render and audit helpers apply unchanged;
  (b) the compact_transcript payload via research.real_context_bench_v02.rules_payload.

Choices (stated in the v0.6 receipt):
- Hermes re-writes a session's rows on each flush, and later copies can be pruned (fewer
  tool_calls). Rows are grouped by (role, timestamp, tool_call_id) and the first-written row
  (lowest id) of each group is kept: the record as it was when it happened.
- A Hermes compression summary row (_compressed_summary=1) restarts the context, like a Codex
  `compacted` record. Context never crosses into a parent session.
- One m per message row; an assistant row's text and its tool_calls share that m. Reasoning
  fields, session_meta rows and the system prompt are dropped. User rows (incl. injected notices)
  are kept as user text. Tool results keep the raw content string the model received.
- is_error: the tool content parses as a JSON object with a nonzero int exit_code, success false,
  or a non-empty error field.
"""
import hashlib
import json
import re
import sqlite3
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path.home() / '.hermes'
_SLASH = re.compile(r'/[\w:.-]+')
_COLS = ('id', 'role', 'content', 'tool_calls', 'tool_call_id', 'tool_name', 'timestamp', '_compressed_summary')


def _importer():
    """research.import_agent_requests without its sys.path edit leaking (it prepends ~/LCC/src)."""
    saved = list(sys.path)
    try:
        from research import import_agent_requests as iar
    finally:
        sys.path[:] = saved
    return iar


def connect(root=ROOT):
    return sqlite3.connect(f"file:{Path(root) / 'state.db'}?mode=ro", uri=True)


def prompt_id(goal, redact, max_chars=1000):
    return hashlib.sha256(f'hermes\0{redact(goal)[:max_chars]}'.encode()).hexdigest()[:16]


def index_prompts(root, redact, max_chars=1000):
    """{id: dict(sid, ts, goal)}: importer order, filters and first-id-wins; ts is epoch seconds."""
    out = {}
    for t, sid, iso in _importer().hermes(root, Counter()):
        t = (t or '').strip()
        if not t or _SLASH.fullmatch(t) or len(t) > max_chars or iso is None:
            continue
        out.setdefault(prompt_id(t, redact, max_chars),
                       dict(sid=sid, ts=datetime.fromisoformat(iso).timestamp(), goal=t))
    return out


def session_rows(con, sid):
    """Deduplicated message rows of one session, oldest first (first-written copy per group)."""
    rows = [dict(zip(_COLS, r)) for r in con.execute(
        f"select {','.join(_COLS)} from messages where session_id=? order by timestamp, id", (sid,))]
    first = {}
    for r in rows:
        first.setdefault((r['role'], r['timestamp'], r['tool_call_id'] or ''), r)
    return sorted((r for r in first.values()), key=lambda r: (r['timestamp'], r['id']))


def prompt_row(rows, ts, goal, clean):
    """The user row a prompt came from: within 1 ms of ts and cleaning to the goal text."""
    return next((r for r in rows if r['role'] == 'user' and abs(r['timestamp'] - ts) < 1e-3
                 and clean(r['content'] or '') == goal), None)


def context_rows(rows, upto_ts):
    """Rows written before upto_ts, restarting at the latest compression summary."""
    out = []
    for r in rows:
        if r['timestamp'] >= upto_ts:
            break
        if r['_compressed_summary']:
            out = []
        out.append(r)
    return out


def is_error(content):
    try:
        d = json.loads(content)
    except (TypeError, ValueError):
        return False
    if not isinstance(d, dict):
        return False
    code = d.get('exit_code')
    return (isinstance(code, int) and not isinstance(code, bool) and code != 0) or d.get('success') is False \
        or bool(d.get('error'))


def render_blocks(rows):
    """Context rows -> harness dossier blocks (one m per row)."""
    blocks, names = [], {}

    def add(m, role, kind, content, tool=None, tid=None, err=False):
        blocks.append(dict(m=m, role=role, kind=kind, tool_name=tool, tool_use_id=tid, is_error=err,
                           content=content))

    for m, r in enumerate(rows):
        role, content = r['role'], r['content'] or ''
        if role == 'user':
            add(m, 'user', 'text', content)
        elif role == 'assistant':
            if content.strip():
                add(m, 'assistant', 'text', content)
            try:
                calls = json.loads(r['tool_calls']) if r['tool_calls'] else []
            except ValueError:
                calls = []
            for i, c in enumerate(c for c in (calls if isinstance(calls, list) else []) if isinstance(c, dict)):
                fn = c.get('function') if isinstance(c.get('function'), dict) else {}
                raw = fn.get('arguments')
                try:
                    inp = json.loads(raw) if isinstance(raw, str) else raw
                except ValueError:
                    inp = dict(arguments=raw)
                inp = inp if isinstance(inp, dict) else dict(arguments=inp)
                tid = c.get('id') or c.get('call_id') or f'hermes-row-{r["id"]}-{i}'
                names[tid] = fn.get('name')
                add(m, 'assistant', 'tool_use', json.dumps(inp, ensure_ascii=False, sort_keys=True), fn.get('name'), tid)
        elif role == 'tool':
            tid = r['tool_call_id'] or f'hermes-row-{r["id"]}'
            add(m, 'user', 'tool_result', content, r['tool_name'] or names.get(tid), tid, is_error(content))
        # session_meta and any other role: dropped
    return blocks


def counts(blocks):
    """(assistant turns, tool results) in a block list."""
    return (len({b['m'] for b in blocks if b['role'] == 'assistant'}),
            sum(b['kind'] == 'tool_result' for b in blocks))


def build_dossier(item, con, redact, render, clean):
    """item: sample row (id, category, label_source, confidence, session_hash, sid, ts).
    The goal is re-read from the prompt row; id_ok checks it hashes to the id.
    render: research.real_context_bench.render; clean: import_agent_requests._hermes_clean."""
    rows = session_rows(con, item['sid'])
    pr = next((r for r in rows if r['role'] == 'user' and abs(r['timestamp'] - item['ts']) < 1e-3
               and prompt_id(clean(r['content'] or ''), redact) == item['id']), None)
    goal = clean(pr['content'] or '') if pr else ''
    blocks = render_blocks(context_rows(rows, pr['timestamp'])) if pr else []
    return dict(id=item['id'], id_ok=bool(pr), category=item['category'], label_source=item['label_source'],
                confidence=item['confidence'], session_hash=item['session_hash'], goal=goal, blocks=blocks,
                text=render(blocks))
