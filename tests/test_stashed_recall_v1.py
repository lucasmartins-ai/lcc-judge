import hashlib
import json

from research import recall_mcp_shim as shim
from research import stashed_recall_v1 as sr


def test_where_locates_in_view_stash_only_and_neither():
    blobs = {'a' * 64: sr.nal.collapse('the value is src/auth/session_store.py here')}
    view = sr.nal.collapse('context mentions README_LONGNAME.md')
    assert sr.where(['README_LONGNAME.md'], view, blobs) == ('in_view', [])
    assert sr.where(['src/auth/session_store.py'], view, blobs) == ('stash_only', ['a' * 64])
    assert sr.where(['nowhere.py'], view, blobs) == ('neither', [])


def test_gold_features_per_probe_type():
    assert sr.gold_features(dict(type='artifact', gold=[['/x/a_long_name.py', 'a_long_name.py']]), {}) == [
        ('/x/a_long_name.py', ['/x/a_long_name.py', 'a_long_name.py'])]
    assert sr.gold_features(dict(type='recall', gold='0xdeadbeef'), {}) == [('0xdeadbeef', ['0xdeadbeef'])]
    assert sr.gold_features(dict(type='decision', gold='g', quote='a quote long enough to count here'), {})[0][0] \
        == 'a quote long enough to count here'
    cont = dict(type='continuation', gold=dict(name='Bash', input={}, target='pytest -q', target_kind='command'))
    assert sr.gold_features(cont, {}) == [('pytest -q', ['pytest -q'])]


def test_independent_stash_check_catches_tampering(tmp_path):
    text = 'original tool output'
    digest = hashlib.sha256(text.encode()).hexdigest()
    (tmp_path / digest).write_text(text)
    blocks = [dict(kind='tool_result', tool_use_id='t1', content=text)]
    good = f'[removed: 3 tokens · lcc recall {digest[:12]}]'
    assert sr.independent_stash_check(blocks, {'t1': good}, tmp_path) == []
    assert sr.independent_stash_check(blocks, {'t1': '[removed: 3 tokens · lcc recall 000000000000]'},
                                      tmp_path)[0]['why'] == 'sha_mismatch'
    (tmp_path / digest).write_text('tampered')
    assert sr.independent_stash_check(blocks, {'t1': good}, tmp_path)[0]['why'] == 'blob_missing_or_corrupt'


def test_mask_hides_markers_and_recall_words():
    out = sr.mask('I recalled [removed: 12 tokens · lcc recall abcdef012345] and read it')
    assert 'recall' not in out.lower() and 'abcdef012345' not in out


def test_shim_lists_one_tool_recalls_verified_bytes_and_caps(tmp_path, monkeypatch):
    from lcc.relevance.transcript_stash import put
    monkeypatch.setenv('LCC_STASH_DIR', str(tmp_path / 'stash'))
    monkeypatch.setenv('RECALL_LOG', str(tmp_path / 'log.jsonl'))
    monkeypatch.setenv('RECALL_MAX_CALLS', '2')
    digest = put('line one\nline two\n')
    st = dict(calls=0)
    tools = shim.handle(dict(jsonrpc='2.0', id=1, method='tools/list'), st)['result']['tools']
    assert [t['name'] for t in tools] == ['recall']
    call = lambda args: shim.handle(dict(jsonrpc='2.0', id=2, method='tools/call',  # noqa: E731
                                         params=dict(name='recall', arguments=args)), st)['result']
    r = call(dict(id=digest[:12], lines='2-2'))
    assert r['content'][0]['text'] == 'line two\n' and not r['isError']
    assert call(dict(id='0' * 12))['isError']
    assert 'limit' in call(dict(id=digest[:12]))['content'][0]['text']
    log = [json.loads(x) for x in (tmp_path / 'log.jsonl').read_text().splitlines()]
    assert [x['ok'] for x in log] == [True, False, False] and log[2]['error'] == 'cap'
    assert shim.handle(dict(jsonrpc='2.0', method='notifications/initialized'), st) is None


def test_shim_truncates_long_blobs(monkeypatch):
    text, cut = shim._truncate('word ' * 5000, 100)
    assert cut and shim._tokens(text) <= 100


def test_stash_candidates_exclude_view_and_goal_and_rank_kinds():
    blobs = {'b' * 64: 'commit 3f9a2c1e7b request_id_v2 value 48213 parse_config_v3'}
    view = sr.nal.collapse('we saw parse_config_v3 earlier')
    c = sr.stash_candidates(blobs, view, 'fix request_id_v2 please')
    vals = [v for _, v, _ in c]
    assert 'parse_config_v3' not in vals and 'request_id_v2' not in vals
    kinds = [k for k, _, _ in c]
    assert kinds == sorted(kinds, key=sr.STASH_KINDS.index) and all(s == ['b' * 64] for _, _, s in c)
    assert c == sr.stash_candidates(blobs, view, 'fix request_id_v2 please')  # deterministic
