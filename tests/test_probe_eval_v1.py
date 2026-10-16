import random

from research import probe_eval_v1 as pe


def ev(kind, value, rules, refetched=False, generic=False, blocks=(1,)):
    return dict(kind=kind, value=value, rules=list(rules), refetched=refetched, generic=generic, blocks=list(blocks))


def test_frozen_texts_match_protocol():
    t = pe.frozen_texts()
    assert set(t) == set('AKQSGR') and t['A'].startswith('Before you act')


def test_artifact_gold_groups_keys_of_one_file():
    sets = [ev('path', '/Users/x/proj/src/auth/session_store.py', ['path_op']),
            ev('path', 'auth/session_store.py', ['path_op']),
            ev('path', 'session_store.py', ['edit_anchor']),
            ev('path', '/Users/x/proj/README_LONGNAME.md', ['path_op'], refetched=True),
            ev('path', '/Users/x/proj/docs/notes.md', ['text_ref'])]
    g = pe.artifact_gold(sets)
    assert len(g) == 1 and g[0][0] == '/Users/x/proj/src/auth/session_store.py'
    assert {'auth/session_store.py', 'session_store.py'} <= set(g[0])


def test_path_recall_and_hallucination():
    g = pe.artifact_gold([ev('path', '/Users/x/proj/src/auth/session_store.py', ['path_op']),
                          ev('path', '/Users/x/proj/src/api/routes_admin.py', ['path_op'])])
    ans = 'I will edit src/auth/session_store.py and /Users/x/proj/src/made_up_module.py'
    assert pe.path_recall(g, ans) == 0.5
    ctx = 'read /Users/x/proj/src/auth/session_store.py'
    assert pe.hallucinated_paths(ans, ctx, '') == ['/Users/x/proj/src/made_up_module.py']
    assert pe.path_recall(g, 'unknown') == 0.0


def test_recall_ranked_priority_and_seed():
    sets = [ev('ident', 'session_store', ['call_value']), ev('hex', 'a1b2c3d4e5', ['text_ref']),
            ev('ident', 'retryPolicy', ['text_ref']), ev('num', '0.9731', ['path_op']),
            ev('hex', 'deadbeef12', ['call_value'], refetched=True)]
    r = pe.recall_ranked(sets)
    assert r[0] == ('hex', 'a1b2c3d4e5') and [k for k, _ in r] == ['hex', 'ident', 'ident']
    assert r == pe.recall_ranked(sets)


def test_leaks():
    gold = {'session_store', '/Users/x/proj/src/auth/session_store.py'}
    assert pe.leaks('What did session_store return?', gold)
    assert pe.leaks('Which value of session_store.get did you use?', gold)
    assert pe.leaks('What happened in src/auth/session_store.py?', gold)
    assert not pe.leaks('Which store object held the login session data?', gold)


def test_first_call_and_target_match():
    events = [('text', 'ok'), ('call', 'Read', {'file_path': '/Users/x/proj/src/auth/session_store.py'}),
              ('call', 'Bash', {'command': 'pytest -q'})]
    c = pe.first_call(events)
    assert c['target_kind'] == 'path' and pe.target_match(c, 'Read src/auth/session_store.py first')
    c2 = pe.first_call([('call', 'Bash', {'command': 'cd /Users/x/proj && pytest -q tests/'})])
    assert c2['target'] == 'pytest -q' and pe.target_match(c2, 'run `pytest -q`') is True
    assert pe.first_call([('text', 'no calls')]) is None


def test_quote_and_mask():
    ctx = 'The user said: never push to main without asking first, ever.'
    assert pe.quote_ok('never push to main without   asking first', ctx, 'fix the bug')
    assert not pe.quote_ok('short', ctx, '')
    assert not pe.quote_ok('never push to main without asking first', ctx, 'never push to main without asking first')
    assert pe.mask('From the summary and [Old tool result content cleared] lcc pointer') .count('[masked]') == 4


def test_wilson_and_bootstrap():
    assert pe.wilson(0, 0) is None and pe.wilson(5, 10)[0] == 0.5
    diffs = [0.5] * 20 + [0.0] * 20
    groups = [f'g{i % 8}' for i in range(40)]
    m, lo, hi = pe.cluster_boot(diffs, groups)
    assert m == 0.25 and lo <= m <= hi
    assert pe.cluster_boot([1.0, 1.0], ['a', 'b'])[1] == 1.0


def test_pilot_sampling_is_seeded():
    ids = [f'{i:04d}' for i in range(100)]
    assert random.Random(pe.SEED).sample(ids, 10) == random.Random(pe.SEED).sample(ids, 10)


def test_find_obj_accepts_string_payloads():
    env = {'type': 'result', 'result': '', 'structured_output': {'summary': 'text'}}
    assert pe._find_obj(env, 'summary') == {'summary': 'text'}
    assert pe._find_obj({'result': '{"answers": {"1": "a"}}'}, 'answers') == {'answers': {'1': 'a'}}


def test_artifact_gold_is_files_only():
    sets = [ev('path', 'https://www.fiverr.com/x/create-a-chatbot', ['path_op']),
            ev('path', 'github.com/lucasmartins-ai/lcc', ['path_op']),
            ev('path', '/membros/ferramentas', ['path_op']),
            ev('path', 'filhote/prenhez/crônico', ['path_op']),
            ev('path', 'system_prompt_agente.html', ['path_op']),
            ev('path', '/Users/x/proj/src/server.ts', ['edit_anchor'])]
    heads = sorted(g[0] for g in pe.artifact_gold(sets))
    assert heads == ['/Users/x/proj/src/server.ts', 'system_prompt_agente.html']
    assert pe.hallucinated_paths('see https://example.com/a/b.html and /api/chat', '', '') == []


def test_qwk():
    assert pe.qwk([0, 1, 2, 3, 4, 5], [0, 1, 2, 3, 4, 5]) == 1.0
    assert pe.qwk([], []) is None
    assert pe.qwk([0, 5, 0, 5], [5, 0, 5, 0]) < 0
