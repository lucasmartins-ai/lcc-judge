"""Tests for the Hermes context adapter on a synthetic state.db (never touches ~/.hermes)."""
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

try:
    from research import hermes_context as hc
    IAR = hc._importer()
except ImportError:  # lcc.request_log needed by the importer
    raise unittest.SkipTest('Needs lcc.request_log (LCC checkout on a branch that has it)')
from research import real_context_bench as rcb
from research import real_context_bench_v02 as v02

ID = lambda s: s  # noqa: E731
T0 = 1760000000.0


def call(cid, name, args):
    return dict(id=cid, call_id=cid, type='function', function=dict(name=name, arguments=json.dumps(args)))


# (id, session, role, content, tool_calls, tool_call_id, tool_name, dt, display_kind, summary)
ROWS = [
    (1, 'h1', 'user', 'fix the build please', None, None, None, 0, None, 0),
    (2, 'h1', 'assistant', 'Running the build.', [call('c1', 'terminal', {'command': 'npm run build'}),
                                                  call('c2', 'read_file', {'path': 'a.py'})], None, None, 1, None, 0),
    (3, 'h1', 'tool', json.dumps({'output': 'Error: boom', 'exit_code': 2, 'error': None}), None, 'c1', 'terminal', 2, None, 0),
    (4, 'h1', 'tool', json.dumps({'content': '1|x = 1', 'total_lines': 1}), None, 'c2', 'read_file', 3, None, 0),
    # later flush copies of rows 2 and 3, the assistant one pruned to one call: ignored
    (10, 'h1', 'assistant', 'Running the build.', [call('c1', 'terminal', {'command': 'npm run build'})], None, None, 1, None, 0),
    (11, 'h1', 'tool', json.dumps({'output': 'Error: boom', 'exit_code': 2}), None, 'c1', 'terminal', 2, None, 0),
    (5, 'h1', 'assistant', 'Build fails on boom.', None, None, None, 4, None, 0),
    (6, 'h1', 'session_meta', '{}', None, None, None, 4.5, None, 0),
    (7, 'h1', 'user', 'now add a test', None, None, None, 5, None, 0),
    (8, 'h1', 'assistant', 'Added.', None, None, None, 6, None, 0),
    (20, 'h2', 'user', 'cron job text', None, None, None, 7, None, 0),
]


def make_db(root):
    con = sqlite3.connect(Path(root) / 'state.db')
    con.executescript("""
        create table sessions(id text, source text);
        create table messages(id integer primary key, session_id text, role text, content text, tool_calls text,
                              tool_call_id text, tool_name text, timestamp real, display_kind text,
                              _compressed_summary integer not null default 0);
        insert into sessions values ('h1','desktop'),('h2','cron');
    """)
    con.executemany('insert into messages values (?,?,?,?,?,?,?,?,?,?)',
                    [(i, s, r, c, json.dumps(tc) if tc else None, tid, tn, T0 + dt, dk, sm)
                     for i, s, r, c, tc, tid, tn, dt, dk, sm in ROWS])
    con.commit()
    return con


class HermesContextTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        make_db(self.tmp.name).close()
        self.con = hc.connect(self.tmp.name)

    def tearDown(self):
        self.con.close()
        self.tmp.cleanup()

    def test_index_prompts_uses_importer_rules(self):
        idx = hc.index_prompts(self.tmp.name, ID)
        self.assertEqual(sorted(v['goal'] for v in idx.values()), ['fix the build please', 'now add a test'])
        v = idx[hc.prompt_id('now add a test', ID)]
        self.assertEqual(v['sid'], 'h1')
        self.assertAlmostEqual(v['ts'], T0 + 5, places=3)

    def test_dedup_keeps_first_written_copy(self):
        rows = hc.session_rows(self.con, 'h1')
        self.assertEqual([r['id'] for r in rows], [1, 2, 3, 4, 5, 6, 7, 8])

    def test_context_excludes_prompt_and_maps_blocks(self):
        rows = hc.session_rows(self.con, 'h1')
        pr = hc.prompt_row(rows, T0 + 5, 'now add a test', IAR._hermes_clean)
        self.assertEqual(pr['id'], 7)
        blocks = hc.render_blocks(hc.context_rows(rows, pr['timestamp']))
        self.assertEqual(hc.counts(blocks), (2, 2))
        texts = [b['content'] for b in blocks if b['kind'] == 'text']
        self.assertEqual(texts, ['fix the build please', 'Running the build.', 'Build fails on boom.'])
        uses = {b['tool_use_id']: b for b in blocks if b['kind'] == 'tool_use'}
        self.assertEqual(json.loads(uses['c1']['content']), {'command': 'npm run build'})
        self.assertEqual(uses['c2']['m'], blocks[1]['m'])  # text and calls of one row share m
        res = {b['tool_use_id']: b for b in blocks if b['kind'] == 'tool_result'}
        self.assertTrue(res['c1']['is_error'])
        self.assertFalse(res['c2']['is_error'])
        self.assertEqual(res['c2']['tool_name'], 'read_file')
        self.assertTrue(all(b['role'] == 'user' for b in res.values()))

    def test_is_error(self):
        self.assertTrue(hc.is_error('{"success": false}'))
        self.assertTrue(hc.is_error('{"error": "nope"}'))
        self.assertFalse(hc.is_error('{"exit_code": 0, "error": null}'))
        self.assertFalse(hc.is_error('{"exit_code": true}'))
        self.assertFalse(hc.is_error('plain text'))

    def test_compression_summary_restarts_context(self):
        rows = hc.session_rows(self.con, 'h1')
        rows.insert(4, dict(id=99, role='user', content='summary of work', tool_calls=None, tool_call_id=None,
                            tool_name=None, timestamp=T0 + 3.5, _compressed_summary=1))
        blocks = hc.render_blocks(hc.context_rows(rows, T0 + 5))
        self.assertEqual([b['content'] for b in blocks], ['summary of work', 'Build fails on boom.'])

    def test_payload_shape_and_is_error_forwarding(self):
        rows = hc.session_rows(self.con, 'h1')
        payload = v02.rules_payload(hc.render_blocks(hc.context_rows(rows, T0 + 5)))
        self.assertTrue(all(set(m) == {'role', 'text', 'toolUses', 'toolResults'} for m in payload))
        res = {r['tool_use_id']: r for m in payload for r in m['toolResults']}
        self.assertTrue(res['c1'].get('is_error'))
        self.assertNotIn('is_error', res['c2'])

    def test_build_dossier_rereads_goal_and_checks_id(self):
        item = dict(id=hc.prompt_id('now add a test', ID), category='specified_task', label_source='x',
                    confidence='high', session_hash='h', sid='h1', ts=T0 + 5)
        d = hc.build_dossier(item, self.con, ID, rcb.render, IAR._hermes_clean)
        self.assertTrue(d['id_ok'])
        self.assertEqual(d['goal'], 'now add a test')
        self.assertEqual(len(d['blocks']), 7)
        bad = hc.build_dossier(dict(item, id='0' * 16), self.con, ID, rcb.render, IAR._hermes_clean)
        self.assertFalse(bad['id_ok'])
        self.assertEqual(bad['blocks'], [])


if __name__ == '__main__':
    unittest.main()
