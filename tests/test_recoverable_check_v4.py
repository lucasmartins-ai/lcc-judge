import json

import pytest

from research.recoverable_check_v4 import independent_check_v4


def _block(m, role, kind, tool, tid, content):
    return {'m': m, 'role': role, 'kind': kind, 'tool_name': tool, 'tool_use_id': tid, 'is_error': False,
            'content': content}


def _blocks(read_input, later_tool, later_input):
    return [
        _block(0, 'user', 'text', None, None, 'fix it'),
        _block(1, 'assistant', 'tool_use', 'Read', 'a', json.dumps(read_input)),
        _block(1, 'user', 'tool_result', None, 'a', 'x' * 300),
        _block(2, 'assistant', 'tool_use', later_tool, 'b', json.dumps(later_input)),
        _block(2, 'user', 'tool_result', None, 'b', 'ok'),
    ]


def _check(blocks, note):
    out = '\n'.join(note if b['tool_use_id'] == 'a' and b['kind'] == 'tool_result' else b['content'] for b in blocks)
    return independent_check_v4(blocks, [{'id': 'a', 'decision': 'replace', 'note': note}], out)


NOTE = '[removed: re-read /r/src/p.py to recover]'


@pytest.mark.parametrize('tool,inp', [
    ('Bash', {'command': 'make'}),
    ('Bash', {'command': 'python gen.py'}),
    ('Bash', {'command': 'git commit -am x'}),
    ('terminal', {'command': 'npm run build'}),
    ('exec_command', {'cmd': 'cargo fmt', 'workdir': '/r'}),
    ('exec_command', {'cmd': 'cd /r && make', 'workdir': '/other'}),
    ('mcp__fs__do', {'x': 1}),
])
def test_opaque_later_write_flags_a_file_pointer(tool, inp):
    bad = _check(_blocks({'file_path': '/r/src/p.py'}, tool, inp), NOTE)
    assert any('opaque later write' in v for v in bad), bad


@pytest.mark.parametrize('tool,inp', [
    ('Bash', {'command': 'ls src'}),
    ('Grep', {'pattern': 'x'}),
    ('TodoWrite', {'todos': []}),
    ('exec_command', {'cmd': 'make', 'workdir': '/other'}),
])
def test_pure_or_elsewhere_later_calls_pass(tool, inp):
    assert _check(_blocks({'file_path': '/r/src/p.py'}, tool, inp), NOTE) == []


def test_relative_file_pointer_without_cwd_is_flagged():
    bad = _check(_blocks({'file_path': 'src/p.py'}, 'Grep', {'pattern': 'x'}),
                 '[removed: re-read src/p.py to recover]')
    assert any('relative path' in v for v in bad), bad
