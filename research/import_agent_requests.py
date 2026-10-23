"""Import the owner's genuine agent prompts (Claude, Codex, Hermes, Antigravity, Grok, Cursor,
OpenCode) as redacted LCC requests.

Read-only on every transcript store. Writes only ~/.lcc/request-log/imported/<source>.jsonl,
outside the repo. Raw prompt text is never written or printed: each record holds the goal after
lcc.request_log.redact, plus counts. Redaction, language detection, session hashing and the salt
all come from lcc.request_log, so imported entries match what the live logger would write.

    python3 -m research.import_agent_requests run      # import (idempotent)
    python3 -m research.import_agent_requests summary  # counts per source/language/session
"""
import argparse
import hashlib
import json
import re
import sqlite3
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, '/Users/Master/LCC/src')
from lcc import request_log as rl  # noqa: E402

HOME = Path.home()
BASE = HOME / '.lcc' / 'request-log'  # same dir and .salt the live logger uses
PROVENANCE = 'genuine_agent_prompt'

# Never open credential/auth material, whatever a store's layout turns out to be.
DENY = re.compile(r'oauth|token|creds|credential|auth|secret|api[_-]?key|\.key$|\.pem$|cookie|keychain'
                  r'|\.env(?:\.|$)|browser-profile|login data|installation_id|google_accounts', re.I)


def is_denied(path):
    return bool(DENY.search(str(path)))


def safe_open(path):
    if is_denied(path):
        raise PermissionError(f'denied path: {Path(path).name}')
    return open(path, encoding='utf-8', errors='replace')


def connect_ro(path):
    if is_denied(path):
        raise PermissionError(f'denied path: {Path(path).name}')
    return sqlite3.connect(f'file:{path}?mode=ro', uri=True)


def _lines(path, drops):
    """JSON objects from a JSONL file; malformed lines and denied files are counted, not raised."""
    try:
        fh = safe_open(path)
    except PermissionError:
        drops['denied_path'] += 1
        return
    except OSError:
        return
    with fh:
        for line in fh:
            try:
                d = json.loads(line)
            except ValueError:
                drops['malformed_line'] += 1
                continue
            if isinstance(d, dict):
                yield d
            else:
                drops['malformed_line'] += 1


def _epoch(ts, scale=1):
    return datetime.fromtimestamp(ts / scale, timezone.utc).isoformat() if isinstance(ts, (int, float)) else None


# --- claude: ~/.claude/projects/**/*.jsonl ---------------------------------------------------
_CLAUDE_AUTO = ('You are Claude Code', 'This session is being continued', '[Request interrupted',
                '[Workflow harness', 'Base directory for this skill', 'Caveat:')


def _claude_text(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        if any(isinstance(b, dict) and b.get('type') == 'tool_result' for b in content):
            return None
        parts = [b.get('text', '') for b in content if isinstance(b, dict) and b.get('type') == 'text']
        return '\n'.join(parts) if parts else None
    return None


def claude(root, drops):
    for f in sorted(Path(root).rglob('*.jsonl')):
        if 'subagents' in f.relative_to(root).parts:
            drops['subagent_file'] += 1
            continue
        prev = None  # last assistant text before the next human prompt (intake v2 context)
        for d in _lines(f, drops):
            if d.get('type') == 'assistant' and not d.get('isSidechain'):
                content = (d.get('message') or {}).get('content')
                if isinstance(content, list):
                    text = '\n'.join(b.get('text', '') for b in content
                                     if isinstance(b, dict) and b.get('type') == 'text').strip()
                    if text:
                        prev = text
                continue
            if d.get('type') != 'user':
                continue  # attachment/snapshot records are not user turns at all
            if (d.get('isMeta') or d.get('isSidechain') or d.get('isCompactSummary') or d.get('agentId')
                    or d.get('toolUseResult') is not None or d.get('sourceToolUseID')
                    or d.get('sourceToolAssistantUUID') or d.get('entrypoint') in ('sdk-py', 'sdk-ts', 'sdk-cli')):
                drops['not_human_record'] += 1
                continue
            t = _claude_text((d.get('message') or {}).get('content'))
            if t is None:
                drops['not_human_record'] += 1
                continue
            s = t.strip()
            if s.startswith('<') or s.startswith(_CLAUDE_AUTO):
                drops['injected_text'] += 1
                continue
            yield s, d.get('sessionId') or f.stem, d.get('timestamp'), prev
            prev = None


# --- codex: ~/.codex/sessions/**/rollout-*.jsonl + history.jsonl -----------------------------
_CODEX_REQ = '## My request for Codex:'
_CODEX_SKIP = ('<', '# AGENTS.md instructions', '# Files mentioned by the user', '# Files pasted by the user',
               '# In app browser', 'Automation:', 'PLEASE IMPLEMENT THIS PLAN')


def codex(root, drops):
    root = Path(root)
    seen = set()
    for f in sorted((root / 'sessions').rglob('rollout-*.jsonl')):
        sid, human = f.stem[-36:], False
        for r in _lines(f, drops):
            p = r.get('payload') if isinstance(r.get('payload'), dict) else {}
            if r.get('type') == 'session_meta':
                sid = p.get('id') or p.get('session_id') or sid
                # vscode = Codex Desktop, cli = TUI; exec is scripted, dict sources are subagents
                human = not p.get('parent_thread_id') and p.get('source') in ('vscode', 'cli')
                continue
            if r.get('type') == 'event_msg' and p.get('type') == 'user_message':
                found = [p.get('message') or '']
            elif r.get('type') == 'response_item' and p.get('type') == 'message' and p.get('role') == 'user':
                found = [c.get('text', '') for c in p.get('content') or []
                         if isinstance(c, dict) and c.get('type') == 'input_text']
            else:
                continue
            if not human:
                drops['automation_source'] += len(found)
                continue
            for t in found:
                t = t.strip()
                if _CODEX_REQ in t:
                    t = t.split(_CODEX_REQ, 1)[1].strip()
                elif t.startswith(_CODEX_SKIP):
                    drops['injected_text'] += 1
                    continue
                if (sid, t) in seen:  # resumed rollouts replay earlier turns
                    drops['replay_duplicate'] += 1
                    continue
                seen.add((sid, t))
                yield t, sid, r.get('timestamp')
    for r in _lines(root / 'history.jsonl', drops) if (root / 'history.jsonl').exists() else ():
        t, sid = (r.get('text') or '').strip(), r.get('session_id')
        if (sid, t) in seen:
            drops['replay_duplicate'] += 1
            continue
        seen.add((sid, t))
        yield t, sid, _epoch(r.get('ts'))


# --- hermes: ~/.hermes/state.db ----------------------------------------------------------------
_HERMES_SOURCES = ('desktop', 'cli', 'tui', 'whatsapp')  # cron/kanban/oneshot/subagent/tool = automation
_HERMES_DROP = (
    '[IMPORTANT:', '[System', '[SYSTEM', 'Resume prior conversation', "You've reached the maximum",
    'You just executed tool calls', '[ASYNC DELEGATION', '[Cron delivery', '[Your active task list',
    '[CONTEXT COMPACTION', '[image received]', '[The user sent', 'You said yes, but I verified', '━',
    'Complete a tarefa do bot', '[Background', '[Reaction:', 'Turn made no progress', 'Last login:',
)


def _hermes_clean(t):
    t = t.strip()
    if t.startswith('[OUT-OF-BAND USER MESSAGE'):
        t = t.split('\n', 1)[1] if '\n' in t else ''
        t = re.sub(r'\n?\[[^\]\n]*USER MESSAGE\]\s*$', '', t).strip()
    if t.startswith('Gateway message origin'):
        t = t.split('\n\n', 1)[1] if '\n\n' in t else ''
    if t.startswith('[Replying to'):
        i = t.find('"]')
        t = t[i + 2:] if i >= 0 else ''
    t = t.split('--- Attached Context ---', 1)[0]
    return re.sub(r'^(?:@(?:file|url|folder):(?:`[^`]*`|\S+)\s*)+', '', t.strip()).strip()


def hermes(root, drops):
    db = Path(root) / 'state.db'
    if not db.exists():
        return
    con = connect_ro(db)
    marks = ','.join('?' * len(_HERMES_SOURCES))
    seen = set()
    try:
        drops['automation_source'] += con.execute(
            f"select count(*) from messages m join sessions s on s.id=m.session_id where m.role='user' "
            f"and (s.source not in ({marks}) or s.source is null)", _HERMES_SOURCES).fetchone()[0]
        drops['not_human_record'] += con.execute(
            f"select count(*) from messages m join sessions s on s.id=m.session_id where m.role='user' "
            f"and s.source in ({marks}) and m.display_kind is not null and m.display_kind!='steer'",
            _HERMES_SOURCES).fetchone()[0]
        rows = con.execute(
            "select m.session_id, m.role, m.content, m.timestamp from messages m join sessions s on s.id=m.session_id "
            "where ((m.role='user' and (m.display_kind is null or m.display_kind='steer')) or m.role='assistant') "
            f"and s.source in ({marks}) order by m.timestamp, m.rowid", _HERMES_SOURCES)
        last = {}  # session -> last assistant text (intake v2 context)
        for sid, role, content, ts in rows:
            if role == 'assistant':
                if (content or '').strip():
                    last[sid] = content.strip()
                continue
            t = _hermes_clean(content or '')
            if t.startswith(_HERMES_DROP) or (t.startswith('Read the file ') and 'answer' in t[:200]):
                drops['injected_text'] += 1
                continue
            key = (t, int(ts or 0))  # compaction copies messages into child sessions
            if key in seen:
                drops['replay_duplicate'] += 1
                continue
            seen.add(key)
            yield t, sid, _epoch(ts), last.pop(sid, None)
    finally:
        con.close()


# --- antigravity: ~/.gemini/antigravity-cli/history.jsonl (other stores are protobuf/encrypted) --
def antigravity(root, drops):
    f = Path(root) / 'antigravity-cli' / 'history.jsonl'
    if not f.is_file():
        return
    prev = None
    for d in _lines(f, drops):
        text = (d.get('display') or '').strip()
        if not text:
            drops['empty'] += 1
            continue
        if d.get('type') == 'slash_command':
            drops['slash_command'] += 1
            continue
        if text and text == prev:  # client logs a retried submission twice
            drops['replay_duplicate'] += 1
            continue
        prev = text
        iso = _epoch(d.get('timestamp'), 1000)
        yield text, d.get('conversationId') or f"{d.get('workspace', '')}@{(iso or '')[:10]}", iso


# --- grok: ~/.grok/sessions/*/prompt_history.jsonl ---------------------------------------------
_LOGDUMP = re.compile(r'^\s*\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}')
_BAREPATH = re.compile(r'^\s*(/|~/)\S+\s*$')


def grok(root, drops):
    for f in sorted((Path(root) / 'sessions').glob('*/prompt_history.jsonl')):
        for d in _lines(f, drops):
            p = d.get('prompt')
            if d.get('is_bash'):
                drops['not_human_record'] += 1
                continue
            p = p if isinstance(p, str) else ''
            if _LOGDUMP.match(p) or _BAREPATH.match(p):
                drops['pasted_dump'] += 1
                continue
            yield p.strip(), d.get('session_id'), d.get('timestamp')


# --- cursor: ~/.cursor/projects/*/agent-transcripts/*/*.jsonl ----------------------------------
_UQ = re.compile(r'<user_query>(.*?)</user_query>', re.S)
_TS = re.compile(r'<timestamp>(.*?)</timestamp>', re.S)
# ponytail: prefix list of Cursor built-ins + agent-dispatched briefs; extend when new automation appears
_CURSOR_AUTO = re.compile(r'\s*(Execute the selected diff-tab|Briefly inform the user about|Verify these issues exist|'
                          r'agent worker start|Start multitasking|# Codex Task:|You are (a|an) (senior |veterinary )|'
                          r'You are working inside)', re.I)


def _cursor_iso(raw):
    m = re.match(r'\s*\w+, (\w+ \d+, \d{4}, \d+:\d+ [AP]M) \(UTC([+-]\d+)?\)', raw)
    if not m:
        return None
    tz = timezone(timedelta(hours=int(m.group(2) or 0)))
    return datetime.strptime(m.group(1), '%b %d, %Y, %I:%M %p').replace(tzinfo=tz).astimezone(timezone.utc).isoformat()


def cursor(root, drops):
    for f in sorted(Path(root).glob('projects/*/agent-transcripts/*/*.jsonl')):  # depth excludes subagents/
        for r in _lines(f, drops):
            if r.get('role') != 'user':
                continue
            content = (r.get('message') or {}).get('content') or []
            t = ''.join(b.get('text', '') for b in content if isinstance(b, dict) and b.get('type') == 'text')
            queries = _UQ.findall(t)
            if not queries:
                drops['not_human_record'] += 1
                continue
            ts = _TS.search(t)
            ts = _cursor_iso(ts.group(1)) if ts else None
            for q in queries:
                q = q.strip()
                if _CURSOR_AUTO.match(q):
                    drops['injected_text'] += 1
                    continue
                yield q, f.stem, ts


# --- opencode: ~/.local/share/opencode/opencode.db ---------------------------------------------
def opencode(root, drops):
    db = Path(root) / 'opencode.db'
    if not db.exists():
        return
    con = connect_ro(db)
    try:
        drops['not_human_record'] += con.execute(
            "select count(*) from part p join message m on m.id=p.message_id join session s on s.id=m.session_id "
            "where json_extract(m.data,'$.role')='user' and json_extract(p.data,'$.type')='text' "
            "and (s.parent_id is not null or coalesce(json_extract(p.data,'$.synthetic'),0)!=0)").fetchone()[0]
        rows = con.execute("""
            select m.id, m.session_id, m.time_created, p.data from message m
            join session s on s.id = m.session_id join part p on p.message_id = m.id
            where json_extract(m.data,'$.role') = 'user' and s.parent_id is null
              and json_extract(p.data,'$.type') = 'text' and coalesce(json_extract(p.data,'$.synthetic'),0) = 0
            order by m.time_created, m.id, p.id""")
        cur, buf = None, []
        for mid, sid, tc, data in [*rows, (None, None, None, None)]:
            if cur and cur[0] != mid:
                text = '\n'.join(buf).strip()
                if _LOGDUMP.match(text):
                    drops['pasted_dump'] += 1
                else:
                    yield text, cur[1], _epoch(cur[2], 1000)
            if mid is None:
                break
            if not cur or cur[0] != mid:
                cur, buf = (mid, sid, tc), []
            try:
                buf.append(json.loads(data).get('text') or '')
            except ValueError:
                drops['malformed_line'] += 1
    finally:
        con.close()


EXTRACTORS = {'claude': claude, 'codex': codex, 'hermes': hermes, 'antigravity': antigravity,
              'grok': grok, 'cursor': cursor, 'opencode': opencode}
DEFAULT_ROOTS = {'claude': HOME / '.claude' / 'projects', 'codex': HOME / '.codex', 'hermes': HOME / '.hermes',
                 'antigravity': HOME / '.gemini', 'grok': HOME / '.grok', 'cursor': HOME / '.cursor',
                 'opencode': HOME / '.local' / 'share' / 'opencode'}
_SLASH = re.compile(r'/[\w:.-]+')  # "/compact", "/model" with no args; "/Users/x" contains a second '/'


def _utc(ts):
    if not ts:
        return None
    try:
        d = datetime.fromisoformat(str(ts).replace('Z', '+00:00'))
    except ValueError:
        return None
    d = d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    return d.astimezone(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z')


def _existing_ids(path):
    if not path.exists():
        return set()
    recs = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line]
    if any(r.get('redaction_rules_sha256') != rl.RULESET_SHA256 for r in recs):
        # ids hash the redacted goal, so old-rule records would sit beside re-redacted copies
        raise SystemExit(f'{path} was redacted with an older ruleset; delete it and rerun')
    return {r['id'] for r in recs}


PREV_CHARS = 600  # tail of the agent's last turn: where its question or proposal sits


def run(roots=None, base=BASE, with_prev=False):
    roots = roots or DEFAULT_ROOTS
    base, out = Path(base), {}
    (base / 'imported').mkdir(parents=True, exist_ok=True)
    salt = rl._salt(base)  # same creation mechanism (O_EXCL, 0600) as the live logger
    now = datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')
    for source, root in roots.items():
        path = base / 'imported' / f'{source}.jsonl'
        drops, prior, seen, new, sessions = Counter(), _existing_ids(path), set(), [], set()
        root = Path(root).expanduser()
        for text, key, ts, *rest in EXTRACTORS[source](root, drops) if root.exists() else ():
            text = (text or '').strip()
            if not text:
                drops['empty'] += 1
                continue
            if _SLASH.fullmatch(text):
                drops['slash_command'] += 1
                continue
            if len(text) > rl.MAX_GOAL_CHARS:  # likely pasted context, not a goal
                drops['too_long'] += 1
                continue
            goal = rl.redact(text)[:rl.MAX_GOAL_CHARS]
            prev = rl.redact(rest[0])[-PREV_CHARS:] if with_prev and rest and rest[0] else None
            # with_prev: the same short reply after a different agent turn is a different request
            rid = hashlib.sha256((f'{source}\0{goal}' + (f'\0{prev}' if prev else '')).encode()).hexdigest()[:16]
            if rid in prior or rid in seen:
                drops['already_imported' if rid in prior else 'duplicate'] += 1
                continue
            seen.add(rid)
            shash = rl.session_hash(f'{source}:{key}', salt)
            sessions.add(shash)
            new.append({'id': rid, 'source': source, 'provenance': PROVENANCE, 'goal': goal,
                        'language': rl.detect_language(goal), 'session_hash': shash,
                        'timestamp_utc': _utc(ts), 'imported_at_utc': now,
                        'redaction_rules_sha256': rl.RULESET_SHA256,
                        **({'prev_agent': prev} if with_prev else {})})
        if new:
            with path.open('a', encoding='utf-8') as fh:
                fh.writelines(json.dumps(r, ensure_ascii=False) + '\n' for r in new)
        out[source] = {'root_found': root.exists(), 'written': len(new), 'sessions_written': len(sessions),
                       'dropped': dict(sorted(drops.items()))}
    return out


def summary(base=BASE):
    result = {}
    for path in sorted((Path(base) / 'imported').glob('*.jsonl')):
        recs = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line]
        stamps = sorted(r['timestamp_utc'] for r in recs if r.get('timestamp_utc'))
        result[path.stem] = {
            'total': len(recs),
            'sessions': len({r['session_hash'] for r in recs}),
            'by_language': dict(Counter(str(r.get('language') or 'unknown') for r in recs).most_common()),
            'missing_timestamp': len(recs) - len(stamps),
            'first': stamps[0] if stamps else None, 'last': stamps[-1] if stamps else None,
            'max_per_session': max(Counter(r['session_hash'] for r in recs).values(), default=0),
        }
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=('run', 'summary'))
    parser.add_argument('--base', type=Path, default=BASE)
    parser.add_argument('--sources', nargs='+', choices=sorted(EXTRACTORS), default=sorted(EXTRACTORS))
    parser.add_argument('--with-prev', action='store_true',
                        help="store the tail of the agent's previous turn (redacted); it joins the dedupe key")
    args = parser.parse_args()
    if args.command == 'run':
        result = run({s: DEFAULT_ROOTS[s] for s in args.sources}, args.base, args.with_prev)
    else:
        result = summary(args.base)
    print(json.dumps(result, indent=1, sort_keys=True))


if __name__ == '__main__':
    main()
