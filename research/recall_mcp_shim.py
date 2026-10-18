"""Stashed recall v1: a stdio MCP server exposing exactly one tool, `recall`, over one item's stash.

Wraps `lcc.relevance.transcript_stash.recall` at the pin (import path from PYTHONPATH). Every call is logged
to $RECALL_LOG (JSONL). Caps: $RECALL_MAX_CALLS calls per answer (default 8), $RECALL_MAX_TOKENS tokens per
call (default 20000; longer text returns its first tokens plus a note to pass `lines`). The stash is
$LCC_STASH_DIR, one dir per item, so an item can only recall its own blobs.
Protocol: newline-delimited JSON-RPC 2.0 (MCP stdio transport).
"""
import json
import os
import sys

TOOL = {
    'name': 'recall',
    'description': 'Return the exact text of an old tool result that was removed from the context and replaced '
                   'by a marker [removed: N tokens · lcc recall <id>]. Pass the id from the marker.',
    'inputSchema': {'type': 'object', 'required': ['id'], 'properties': {
        'id': {'type': 'string', 'description': 'the id after "lcc recall" in the marker'},
        'lines': {'type': 'string', 'description': 'optional 1-based inclusive line range, e.g. "40-120"'}}},
}


def _log(rec):
    path = os.environ.get('RECALL_LOG')
    if path:
        with open(path, 'a') as f:
            f.write(json.dumps(rec) + '\n')


def _tokens(text):
    from lcc.token_budget.counters import count_tokens
    return count_tokens(text, 'gpt-4.1').value  # same counter as the bench (rcb.lcc_count)


def _truncate(text, max_tokens):
    if _tokens(text) <= max_tokens:
        return text, False
    lo, hi = 0, len(text)  # longest prefix within the cap
    while lo < hi:
        mid = (lo + hi + 1) // 2
        lo, hi = (mid, hi) if _tokens(text[:mid]) <= max_tokens else (lo, mid - 1)
    return text[:lo], True


def do_recall(args, state):
    from lcc.relevance.transcript_stash import StashError, parse_lines, recall
    max_calls = int(os.environ.get('RECALL_MAX_CALLS', '8'))
    max_tokens = int(os.environ.get('RECALL_MAX_TOKENS', '20000'))
    state['calls'] += 1
    rec = dict(n=state['calls'], id=args.get('id'), lines=args.get('lines'))
    if state['calls'] > max_calls:
        _log(dict(rec, ok=False, error='cap'))
        return f'recall limit reached ({max_calls} calls per answer); answer with what you have.', True
    try:
        text = recall(str(args.get('id', '')).strip(), parse_lines(args['lines']) if args.get('lines') else None)
    except StashError as e:
        _log(dict(rec, ok=False, error=str(e)[:200]))
        return f'recall failed: {e}', True
    text, cut = _truncate(text, max_tokens)
    _log(dict(rec, ok=True, truncated=cut, chars=len(text), tokens=_tokens(text)))
    if cut:
        text += f'\n[recall truncated at {max_tokens} tokens; pass lines="a-b" for the rest]'
    return text, False


def handle(msg, state):
    method, mid = msg.get('method'), msg.get('id')
    if method == 'initialize':
        result = {'protocolVersion': msg.get('params', {}).get('protocolVersion', '2025-06-18'),
                  'capabilities': {'tools': {}}, 'serverInfo': {'name': 'stash', 'version': '1'}}
    elif method == 'tools/list':
        result = {'tools': [TOOL]}
    elif method == 'tools/call':
        p = msg.get('params') or {}
        if p.get('name') != 'recall':
            _log(dict(n=state['calls'], ok=False, error=f"unknown tool {p.get('name')}"))
            return {'jsonrpc': '2.0', 'id': mid, 'error': {'code': -32602, 'message': 'unknown tool'}}
        text, err = do_recall(p.get('arguments') or {}, state)
        result = {'content': [{'type': 'text', 'text': text}], 'isError': err}
    elif method == 'ping':
        result = {}
    elif mid is None:  # notifications (initialized, cancelled, ...)
        return None
    else:
        return {'jsonrpc': '2.0', 'id': mid, 'error': {'code': -32601, 'message': f'no method {method}'}}
    return {'jsonrpc': '2.0', 'id': mid, 'result': result}


def main():
    state = dict(calls=0)
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            msg = json.loads(line)
        except ValueError:
            continue
        out = handle(msg, state)
        if out is not None:
            sys.stdout.write(json.dumps(out) + '\n')
            sys.stdout.flush()


if __name__ == '__main__':
    main()
