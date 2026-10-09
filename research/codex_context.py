"""Codex adapter for the real-context bench: rebuild the context a Codex prompt was sent into.

Read-only on ~/.codex/sessions/**/rollout-*.jsonl. For one human prompt (same extraction rules as
research.import_agent_requests.codex), the context is every response item before the prompt's
first record in its rollout, restarting at the latest `compacted` record (whose
replacement_history is what the model saw next). Mapped to:

  (a) the harness dossier blocks of research.real_context_bench (m, role, kind, tool_name,
      tool_use_id, is_error, content), so the v0 probes, render and audit helpers apply unchanged;
  (b) the compact_transcript payload {role, text, toolUses, toolResults(is_error)} via
      research.real_context_bench_v02.rules_payload over those blocks.

Choices (stated in the v0.4 protocol): one block-group m per response item (Claude Code also
writes one record per content block); developer messages, reasoning and encrypted compaction
items are dropped (system prompt / thinking analogues); tool names stay native (exec_command,
apply_patch, mcp namespace + name), so Claude-named probes/rules (Bash git, Edit/Write, Read) do
not fire on Codex calls; is_error is set only from an exit code Codex recorded (nonzero).
Not imported from import_agent_requests: that module puts ~/LCC/src first on sys.path, which
would shadow the pinned lcc.
"""
import hashlib
import json
import re
from pathlib import Path

ROOT = Path.home() / '.codex'
HUMAN_SOURCES = ('vscode', 'cli')  # importer: vscode = Desktop, cli = TUI; exec/dict sources are automation
REQ = '## My request for Codex:'
SKIP = ('<', '# AGENTS.md instructions', '# Files mentioned by the user', '# Files pasted by the user',
        '# In app browser', 'Automation:', 'PLEASE IMPLEMENT THIS PLAN')
_SLASH = re.compile(r'/[\w:.-]+')
_EXIT_LINE = re.compile(r'^(?:Process exited with code|Exit code:) (-?\d+)\s*$', re.M)


def read_rollout(path):
    out = []
    with open(path, encoding='utf-8', errors='replace') as fh:
        for line in fh:
            try:
                d = json.loads(line)
            except ValueError:
                continue
            if isinstance(d, dict):
                out.append(d)
    return out


def _payload(r):
    return r.get('payload') if isinstance(r.get('payload'), dict) else {}


def prompt_records(records):
    """(index, sid, human, raw text) for every user-text record, as the importer sees them."""
    sid, human = None, False
    for i, r in enumerate(records):
        p = _payload(r)
        if r.get('type') == 'session_meta':
            sid = p.get('id') or p.get('session_id') or sid
            human = not p.get('parent_thread_id') and p.get('source') in HUMAN_SOURCES
            continue
        if r.get('type') == 'event_msg' and p.get('type') == 'user_message':
            found = [p.get('message') or '']
        elif r.get('type') == 'response_item' and p.get('type') == 'message' and p.get('role') == 'user':
            found = [c.get('text', '') for c in p.get('content') or []
                     if isinstance(c, dict) and c.get('type') == 'input_text']
        else:
            continue
        for t in found:
            yield i, sid, human, t


def goal_of(raw):
    """The prompt text the importer keeps, or None when it drops the text as injected."""
    t = raw.strip()
    if REQ in t:
        return t.split(REQ, 1)[1].strip()
    return None if t.startswith(SKIP) else t


def index_prompts(paths, redact, max_chars=1000):
    """{id: dict(path, index, sid, goal)} for each imported Codex id, at its first record.

    Same order and dedup as research.import_agent_requests (sorted rollouts; (sid, text) seen
    once; id = sha256('codex\\0' + redact(text)[:max_chars])[:16]; first id wins). Only human
    sessions are indexed; history.jsonl lines have no rollout position and are not indexed.
    """
    seen, out = set(), {}
    for path in sorted(paths):
        sid0 = Path(path).stem[-36:]
        for i, sid, human, raw in prompt_records(read_rollout(path)):
            sid = sid or sid0
            t = goal_of(raw)
            if not human or t is None or (sid, t) in seen:
                continue
            seen.add((sid, t))
            if not t or _SLASH.fullmatch(t) or len(t) > max_chars:
                continue
            out.setdefault(prompt_id(t, redact, max_chars), dict(path=str(path), index=i, sid=sid, goal=t))
    return out


def context_items(records, upto):
    """Response items the model had before record `upto` (excluded), oldest first."""
    items = []
    for r in records[:upto]:
        p = _payload(r)
        if r.get('type') == 'compacted':
            rh = p.get('replacement_history')
            items = [x for x in rh if isinstance(x, dict)] if isinstance(rh, list) else (
                [dict(type='message', role='user', content=[dict(type='input_text', text=p['message'])])]
                if p.get('message') else [])
        elif r.get('type') == 'response_item':
            items.append(p)
    return items


def _output_text(o):
    if isinstance(o, str):
        return o
    if isinstance(o, list):
        return '\n'.join('[image omitted]' if isinstance(c, dict) and c.get('type') == 'input_image'
                         else (c.get('text') or '') if isinstance(c, dict) else str(c) for c in o)
    return json.dumps(o, ensure_ascii=False, sort_keys=True)


def exit_codes(o):
    """Exit codes Codex recorded in a tool output: the header line of exec_command/write_stdin
    ('Process exited with code N') or apply_patch ('Exit code: N'), read before the first
    'Output:' line only, or an exit_code field of a JSON part (apply_patch metadata, code-mode exec)."""
    parts = o if isinstance(o, list) else [o]
    codes = []
    for c in parts:
        s = c.get('text') if isinstance(c, dict) else c
        if not isinstance(s, str):
            continue
        codes += [int(x) for x in _EXIT_LINE.findall(s.split('\nOutput:', 1)[0])]
        try:
            d = json.loads(s)
        except ValueError:
            continue
        if isinstance(d, dict):
            for v in (d.get('exit_code'), (d.get('metadata') or {}).get('exit_code')
                      if isinstance(d.get('metadata'), dict) else None):
                if isinstance(v, int) and not isinstance(v, bool):
                    codes.append(v)
    return codes


def tool_name(p):
    ns, name = p.get('namespace'), p.get('name') or p.get('type')
    return f"{ns.rstrip('_')}__{name.lstrip('_')}" if ns else name


def render_blocks(items):
    """Response items -> harness dossier blocks (one m per item)."""
    blocks, names = [], {}

    def add(m, role, kind, content, tool=None, tid=None, is_error=False):
        blocks.append(dict(m=m, role=role, kind=kind, tool_name=tool, tool_use_id=tid, is_error=is_error,
                           content=content))

    for m, p in enumerate(items):
        t = p.get('type')
        if t == 'message' and p.get('role') in ('user', 'assistant'):
            for c in p.get('content') or ():
                if not isinstance(c, dict):
                    continue
                if c.get('type') in ('input_text', 'output_text'):
                    add(m, p['role'], 'text', c.get('text') or '')
                elif c.get('type') == 'input_image':
                    add(m, p['role'], 'image', '[image omitted]')
        elif t == 'agent_message':  # message from another agent: input to this one
            add(m, 'user', 'text', _output_text(p.get('content')))
        elif t in ('function_call', 'custom_tool_call', 'tool_search_call'):
            raw = p.get('arguments') if t != 'custom_tool_call' else None
            if t == 'custom_tool_call':
                inp = dict(input=p.get('input'))
            else:
                try:
                    inp = json.loads(raw) if isinstance(raw, str) else raw
                except ValueError:
                    inp = dict(arguments=raw)
                inp = inp if isinstance(inp, dict) else dict(arguments=inp)
            name = 'tool_search' if t == 'tool_search_call' else tool_name(p)
            names[p.get('call_id')] = name
            add(m, 'assistant', 'tool_use', json.dumps(inp, ensure_ascii=False, sort_keys=True), name,
                p.get('call_id') or f'codex-item-{m}')
        elif t in ('function_call_output', 'custom_tool_call_output', 'tool_search_output'):
            o = p.get('tools') if t == 'tool_search_output' else p.get('output')
            add(m, 'user', 'tool_result', _output_text(o), names.get(p.get('call_id')),
                p.get('call_id') or f'codex-item-{m}', any(c != 0 for c in exit_codes(o)))
        elif t == 'web_search_call':
            add(m, 'assistant', 'tool_use', json.dumps(p.get('action'), ensure_ascii=False, sort_keys=True),
                'web_search', p.get('id') or f'codex-item-{m}')
        elif t == 'image_generation_call':
            add(m, 'assistant', 'tool_use', json.dumps(dict(revised_prompt=p.get('revised_prompt')), ensure_ascii=False),
                'image_generation', p.get('id') or f'codex-item-{m}')
        # developer/system messages, reasoning, compaction: dropped
    return blocks


def assistant_turns(items):
    return sum(p.get('type') == 'message' and p.get('role') == 'assistant' for p in items)


def prompt_id(goal, redact, max_chars=1000):
    return hashlib.sha256(f'codex\0{redact(goal)[:max_chars]}'.encode()).hexdigest()[:16]


def build_dossier(item, redact, render):
    """item: sample row (id, category, label_source, confidence, session_hash, path, index).
    The goal is re-read from the rollout record at `index`; id_ok checks it hashes to the id.
    render: research.real_context_bench.render (passed in so this module stays stdlib-only)."""
    records = read_rollout(item['path'])
    goals = [g for i, _, _, raw in prompt_records(records) if i == item['index'] and (g := goal_of(raw))]
    goal = next((g for g in goals if prompt_id(g, redact) == item['id']), goals[0] if goals else '')
    blocks = render_blocks(context_items(records, item['index']))
    return dict(id=item['id'], id_ok=prompt_id(goal, redact) == item['id'], category=item['category'],
                label_source=item['label_source'], confidence=item['confidence'],
                session_hash=item['session_hash'], goal=goal, blocks=blocks, text=render(blocks))
