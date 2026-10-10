import json

from research.recoverable_dev_measure import independent_replace_check


def _blocks(later):
    return [
        dict(m=0, role='assistant', kind='tool_use', tool_name='Read', tool_use_id='a', is_error=False,
             content=json.dumps({'file_path': '/r/src/Card.tsx'})),
        dict(m=1, role='user', kind='tool_result', tool_name=None, tool_use_id='a', is_error=False, content='x' * 200),
        dict(m=2, role='assistant', kind='tool_use', tool_name='Edit', tool_use_id='b', is_error=False,
             content=json.dumps({'file_path': later})),
        dict(m=2, role='user', kind='tool_result', tool_name=None, tool_use_id='b', is_error=False, content='ok'),
        dict(m=3, role='assistant', kind='tool_use', tool_name='Bash', tool_use_id='c', is_error=False,
             content=json.dumps({'command': 'ls src'})),
        dict(m=3, role='user', kind='tool_result', tool_name=None, tool_use_id='c', is_error=False, content='y' * 200),
    ]


def _out(blocks, notes):
    return '\n'.join(notes.get(b['tool_use_id'], b['content']) if b['kind'] == 'tool_result' else b['content'] for b in blocks)


def test_independent_check():
    ok = {'a': '[removed: re-read /r/src/Card.tsx to recover]', 'c': '[removed: re-run `ls src` to recover]'}
    dec = [dict(id=k, decision='replace', note=v) for k, v in ok.items()]
    b = _blocks('/r/src/GlassCard.tsx')  # a different file whose name ends the same: not a write
    assert independent_replace_check(b, dec, _out(b, ok)) == []
    b = _blocks('/r/src/Card.tsx')  # the read file is edited later: violation
    assert any('written later' in v for v in independent_replace_check(b, dec, _out(b, ok)))
    bad = dict(ok, c='[removed: re-run `rm -rf src` to recover]')
    dec = [dict(id=k, decision='replace', note=v) for k, v in bad.items()]
    b = _blocks('/r/x.ts')
    assert any('own read-only command' in v for v in independent_replace_check(b, dec, _out(b, bad)))
