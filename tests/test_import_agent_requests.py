"""Synthetic-fixture tests for the genuine agent prompt importer. Never touches real stores."""
import json
import sqlite3
import stat
import tempfile
import unittest
from collections import Counter
from pathlib import Path

try:
    from research import import_agent_requests as iar
except ImportError:  # lcc.request_log lives on LCC branch feat/opt-in-request-log until merged
    raise unittest.SkipTest('Needs lcc.request_log (LCC checkout on a branch that has it)')


def jl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(r) + '\n' for r in rows), encoding='utf-8')


def texts(gen):
    return [t for t, _, _ in gen]


class DenylistTests(unittest.TestCase):
    def test_credential_paths_are_denied(self):
        for p in ('/h/.codex/auth.json', '/h/.gemini/oauth_creds.json', '/x/server.pem', '/x/id.key',
                  '/x/.env', '/x/.env.local', '/b/Login Data', '/h/.codex/installation_id',
                  '/h/.gemini/google_accounts.json', '/x/api_key.txt', '/x/session-token',
                  '/x/browser-profile/History', '/x/Cookies', '/x/credentials.db', '/x/my_secret.json',
                  '/x/keychain.db', '/x/tokens.json'):
            self.assertTrue(iar.is_denied(Path(p)), p)

    def test_transcript_paths_are_allowed(self):
        for p in ('/h/.codex/sessions/2026/10/01/rollout-2026-abc.jsonl', '/h/.hermes/state.db',
                  '/h/.claude/projects/-Users-x-repo/0f1e.jsonl', '/h/.local/share/opencode/opencode.db',
                  '/h/.grok/sessions/%2Fx/prompt_history.jsonl', '/h/.gemini/antigravity-cli/history.jsonl'):
            self.assertFalse(iar.is_denied(Path(p)), p)

    def test_safe_open_refuses_denied_file_without_reading(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'auth.json'
            p.write_text('{"secret": 1}')
            with self.assertRaises(PermissionError):
                iar.safe_open(p)
            with self.assertRaises(PermissionError):
                iar.connect_ro(Path(d) / 'oauth.db')


class ExtractorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.drops = Counter()

    def tearDown(self):
        self.tmp.cleanup()

    def test_claude_keeps_only_human_typed_prompts(self):
        base = {'type': 'user', 'sessionId': 's1', 'timestamp': '2026-06-02T10:01:53.400Z'}
        jl(self.root / 'proj' / 's1.jsonl', [
            {**base, 'message': {'content': 'fix the login bug'}},
            {**base, 'message': {'content': [{'type': 'text', 'text': 'and add a test'}, {'type': 'image'}]}},
            {**base, 'message': {'content': [{'type': 'tool_result', 'content': 'x'}]}},
            {**base, 'isMeta': True, 'message': {'content': 'skill body'}},
            {**base, 'isCompactSummary': True, 'message': {'content': 'summary'}},
            {**base, 'entrypoint': 'sdk-py', 'message': {'content': 'Review this change'}},
            {**base, 'message': {'content': '<system-reminder>x</system-reminder>'}},
            {**base, 'message': {'content': '[Request interrupted by user]'}},
            {**base, 'message': {'content': 'You are Claude Code working on a task'}},
            {'type': 'assistant', 'message': {'content': 'hi'}},
            'not a dict',
        ])
        jl(self.root / 'proj' / 's1' / 'subagents' / 'a.jsonl', [{**base, 'message': {'content': 'subagent prompt'}}])
        got = list(iar.claude(self.root, self.drops))
        self.assertEqual(texts(got), ['fix the login bug', 'and add a test'])
        self.assertEqual(got[0][1:], ('s1', '2026-06-02T10:01:53.400Z'))
        self.assertGreater(sum(self.drops.values()), 0)

    def test_claude_pairs_each_prompt_with_the_agent_turn_before_it(self):
        base = {'type': 'user', 'sessionId': 's2', 'timestamp': '2026-10-24T10:00:00Z'}
        say = lambda t: {'type': 'assistant', 'message': {'content': [{'type': 'text', 'text': t}]}}  # noqa: E731
        jl(self.root / 'proj' / 's2.jsonl', [
            {**base, 'message': {'content': 'start'}},
            say('Option 1 or 2?'),
            {**base, 'message': {'content': [{'type': 'tool_result', 'content': 'x'}]}},
            say('Pick one: 1 or 2?'),
            {**base, 'message': {'content': 'sim'}},
            {**base, 'message': {'content': 'sim'}},
        ])
        got = list(iar.claude(self.root, self.drops, with_prev=True))
        self.assertEqual([(t, p) for t, _, _, p in got], [('start', None), ('sim', 'Pick one: 1 or 2?'), ('sim', None)])

    def test_codex_unwraps_request_and_skips_subagents_and_replays(self):
        sess = self.root / 'sessions' / '2026' / '10' / '01'
        meta = {'type': 'session_meta', 'payload': {'id': 'c1', 'source': 'vscode'}}
        def msg(t):
            return {'type': 'response_item', 'timestamp': '2026-10-01T00:00:00.000Z',
                    'payload': {'type': 'message', 'role': 'user', 'content': [{'type': 'input_text', 'text': t}]}}
        jl(sess / 'rollout-a-c1.jsonl', [meta, msg('<environment_context>x</environment_context>'),
                                          msg('# Files mentioned by the user\n- a.py\n## My request for Codex:\nrefactor a.py'),
                                          msg('Automation: nightly'), msg('ship it'), msg('ship it')])
        jl(sess / 'rollout-b-c2.jsonl', [{'type': 'session_meta', 'payload': {'id': 'c2', 'source': {'subagent': {}}}},
                                          msg('subagent text')])
        jl(sess / 'rollout-c-c3.jsonl', [{'type': 'session_meta', 'payload': {'id': 'c3', 'source': 'exec'}}, msg('scripted')])
        self.assertEqual(texts(iar.codex(self.root, self.drops)), ['refactor a.py', 'ship it'])

    def test_hermes_unwraps_gateway_and_drops_automation_sources(self):
        db = self.root / 'state.db'
        con = sqlite3.connect(db)
        con.executescript("""
            create table sessions(id text, source text);
            create table messages(session_id text, role text, content text, timestamp real, display_kind text);
            insert into sessions values ('h1','desktop'),('h2','cron');
            insert into messages values
              ('h1','user','[OUT-OF-BAND USER MESSAGE from x]\nplease check deploy\n[END USER MESSAGE]',1760000000.0,null),
              ('h1','user','[System note: compacted]',1760000001.0,null),
              ('h1','user','auto',1760000002.0,'auto_continue'),
              ('h1','assistant','done',1760000003.0,null),
              ('h2','user','cron job text',1760000004.0,null);
        """)
        con.commit()
        con.close()
        got = list(iar.hermes(self.root, self.drops))
        self.assertEqual(texts(got), ['please check deploy'])
        self.assertTrue(got[0][2].startswith('2025-10-09T'))

    def test_antigravity_drops_slash_and_resubmits(self):
        jl(self.root / 'antigravity-cli' / 'history.jsonl', [
            {'display': '/model', 'type': 'slash_command', 'timestamp': 1}, {'display': 'build the page', 'timestamp': 1760000000000, 'conversationId': 'g1'},
            {'display': 'build the page', 'timestamp': 1760000000001}, {'display': '  ', 'timestamp': 2}])
        got = list(iar.antigravity(self.root, self.drops))
        self.assertEqual(texts(got), ['build the page'])
        self.assertEqual(got[0][1], 'g1')

    def test_grok_drops_bash_and_log_dumps(self):
        jl(self.root / 'sessions' / '%2Fx' / 'prompt_history.jsonl', [
            {'prompt': 'ls', 'is_bash': True, 'session_id': 'k'}, {'prompt': '2026-07-12T22:06:52 ERROR boom', 'session_id': 'k'},
            {'prompt': 'improve LCP', 'session_id': 'k', 'timestamp': '2026-07-12T22:06:52.937753Z'}])
        self.assertEqual(texts(iar.grok(self.root, self.drops)), ['improve LCP'])

    def test_cursor_takes_user_query_only(self):
        t = '<plugin_info kind="x">ignore</plugin_info><user_query>\npode fazer\n</user_query>'
        jl(self.root / 'projects' / 'w' / 'agent-transcripts' / 'u1' / 'u1.jsonl', [
            {'role': 'user', 'message': {'content': [{'type': 'text', 'text': t}]}},
            {'role': 'user', 'message': {'content': [{'type': 'text', 'text': '<user_query># Codex Task: x</user_query>'}]}},
            {'role': 'assistant', 'message': {'content': [{'type': 'text', 'text': '<user_query>no</user_query>'}]}},
            {'type': 'status', 'status': 'ok'}])
        self.assertEqual(list(iar.cursor(self.root, self.drops)), [('pode fazer', 'u1', None)])

    def test_opencode_skips_synthetic_and_subagent_sessions(self):
        con = sqlite3.connect(self.root / 'opencode.db')
        con.executescript("""
            create table session(id text, parent_id text);
            create table message(id text, session_id text, time_created int, data text);
            create table part(id text, message_id text, session_id text, data text);
            insert into session values ('o1', null), ('o2', 'o1');
            insert into message values ('m1','o1',1760000000000,'{"role":"user"}'),
                                       ('m2','o2',1760000000001,'{"role":"user"}'),
                                       ('m3','o1',1760000000002,'{"role":"assistant"}');
            insert into part values ('p1','m1','o1','{"type":"text","text":"rode os testes"}'),
                                    ('p2','m1','o1','{"type":"text","text":"Called the Read tool","synthetic":true}'),
                                    ('p3','m2','o2','{"type":"text","text":"subagent"}'),
                                    ('p4','m3','o1','{"type":"text","text":"ok"}');
        """)
        con.commit()
        con.close()
        self.assertEqual(texts(iar.opencode(self.root, self.drops)), ['rode os testes'])


class RunTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        d = Path(self.tmp.name)
        self.base = d / 'request-log'
        self.root = d / 'gem'
        jl(self.root / 'antigravity-cli' / 'history.jsonl', [
            {'display': 'send report to ana@example.com with token=abc123secret', 'timestamp': 1760000000000, 'conversationId': 'g1'},
            {'display': 'corrija o bug da página', 'timestamp': 1760000001000, 'conversationId': 'g1'},
            {'display': '/compact', 'timestamp': 1760000002000, 'conversationId': 'g1'},
            {'display': 'x' * 1001, 'timestamp': 1760000003000, 'conversationId': 'g1'},
            {'display': 'corrija o bug da página', 'timestamp': 1760000004000, 'conversationId': 'g2'},
        ])
        self.roots = {'antigravity': self.root}

    def tearDown(self):
        self.tmp.cleanup()

    def test_run_writes_redacted_records_and_counts_drops(self):
        out = iar.run(self.roots, self.base)
        path = self.base / 'imported' / 'antigravity.jsonl'
        raw = path.read_text(encoding='utf-8')
        self.assertNotIn('ana@example.com', raw)
        self.assertNotIn('abc123secret', raw)
        recs = [json.loads(line) for line in raw.splitlines()]
        self.assertEqual(len(recs), 2)
        need = {'id', 'source', 'provenance', 'goal', 'language', 'session_hash', 'timestamp_utc',
                'imported_at_utc', 'redaction_rules_sha256'}
        for r in recs:
            self.assertEqual(set(r), need)
            self.assertEqual(r['provenance'], 'genuine_agent_prompt')
            self.assertEqual(r['source'], 'antigravity')
            self.assertLessEqual(len(r['goal']), iar.rl.MAX_GOAL_CHARS)
            self.assertTrue(r['timestamp_utc'].endswith('Z'))
        self.assertEqual(recs[0]['redaction_rules_sha256'], iar.rl.RULESET_SHA256)
        self.assertIn('<EMAIL>', recs[0]['goal'])
        self.assertEqual(recs[1]['language'], 'pt')
        d = out['antigravity']['dropped']
        self.assertEqual((out['antigravity']['written'], d['slash_command'], d['too_long'], d['duplicate']), (2, 1, 1, 1))
        salt = self.base / '.salt'
        self.assertEqual(stat.S_IMODE(salt.stat().st_mode), 0o600)

    def test_review_leak_shapes_never_reach_output(self):
        jl(self.root / 'antigravity-cli' / 'history.jsonl', [
            {'display': 'use abc_1XyzQWERTyUIOpA2Bc3D4e', 'timestamp': 1760000000000, 'conversationId': 'g1'},
            {'display': 'a senha minhasenha2024', 'timestamp': 1760000001000, 'conversationId': 'g1'},
            {'display': 'cpf 12345678901Fulano', 'timestamp': 1760000002000, 'conversationId': 'g1'},
        ])
        iar.run(self.roots, self.base)
        raw = (self.base / 'imported' / 'antigravity.jsonl').read_text(encoding='utf-8')
        for leak in ('QWERT', 'minhasenha2024', '12345678901'):
            self.assertNotIn(leak, raw)

    def test_run_refuses_to_mix_records_from_an_older_ruleset(self):
        path = self.base / 'imported' / 'antigravity.jsonl'
        jl(path, [{'id': 'old', 'redaction_rules_sha256': 'stale'}])
        before = path.read_bytes()
        with self.assertRaises(SystemExit):
            iar.run(self.roots, self.base)
        self.assertEqual(path.read_bytes(), before)

    def test_rerun_is_idempotent(self):
        iar.run(self.roots, self.base)
        path = self.base / 'imported' / 'antigravity.jsonl'
        before = path.read_bytes()
        out = iar.run(self.roots, self.base)
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(out['antigravity']['written'], 0)
        self.assertEqual(out['antigravity']['dropped']['already_imported'], 3)  # 2 written + 1 cross-session repeat

    def test_summary_has_counts_but_no_goal_text(self):
        iar.run(self.roots, self.base)
        s = iar.summary(self.base)
        self.assertEqual(s['antigravity']['total'], 2)
        self.assertEqual(s['antigravity']['sessions'], 1)
        self.assertEqual(s['antigravity']['by_language'].get('pt'), 1)
        self.assertNotIn('corrija', json.dumps(s))

    def test_missing_source_root_is_reported_not_fatal(self):
        out = iar.run({'grok': Path(self.tmp.name) / 'nope'}, self.base)
        self.assertEqual(out['grok']['written'], 0)


if __name__ == '__main__':
    unittest.main()
