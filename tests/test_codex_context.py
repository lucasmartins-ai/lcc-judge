"""Stdlib-only tests for the Codex context adapter on synthetic rollouts (no lcc, no ~/.codex)."""
import json
import tempfile
import unittest
from pathlib import Path

from research import codex_context as cc
from research import real_context_bench as rcb
from research import real_context_bench_v02 as v02


def ri(payload):
    return dict(type='response_item', payload=payload)


def msg(role, text, kind=None):
    kind = kind or ('output_text' if role == 'assistant' else 'input_text')
    return ri(dict(type='message', role=role, content=[dict(type=kind, text=text)]))


def meta(sid='s1', source='vscode', parent=None):
    return dict(type='session_meta', payload=dict(id=sid, source=source, parent_thread_id=parent))


def write(dirpath, name, records):
    p = Path(dirpath) / name
    p.write_text(''.join(json.dumps(r) + '\n' for r in records))
    return str(p)


ROLLOUT = [
    meta(),
    msg('developer', 'permissions blurb'),
    msg('user', '# AGENTS.md instructions for /repo\nbe nice'),
    msg('user', 'fix the build please'),
    dict(type='event_msg', payload=dict(type='user_message', message='fix the build please')),
    ri(dict(type='reasoning', summary=[], encrypted_content='x')),
    msg('assistant', 'Running the build.'),
    ri(dict(type='function_call', name='exec_command', arguments='{"cmd": "npm run build"}', call_id='c1')),
    ri(dict(type='function_call_output', call_id='c1',
            output='Chunk ID: a\nWall time: 1 seconds\nProcess exited with code 2\nOutput:\nError: boom\nExit code: 0\n')),
    ri(dict(type='custom_tool_call', name='apply_patch', input='*** Begin Patch', call_id='c2')),
    ri(dict(type='custom_tool_call_output', call_id='c2',
            output='{"output":"Success","metadata":{"exit_code":0,"duration_seconds":0.1}}')),
    ri(dict(type='function_call', namespace='mcp__node_repl__', name='js', arguments='{"code": "1"}', call_id='c3')),
    ri(dict(type='function_call_output', call_id='c3', output=[dict(type='input_text', text='ok'),
                                                                dict(type='input_image', image_url='data:')])),
    ri(dict(type='web_search_call', action=dict(query='q'))),
    msg('assistant', 'Build fails on boom.'),
    msg('user', 'now add a test'),  # index 15: the second prompt
    msg('assistant', 'Added.'),
]


class CodexContextTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = write(self.tmp.name, 'rollout-1.jsonl', ROLLOUT)

    def tearDown(self):
        self.tmp.cleanup()

    def test_index_prompts_follows_importer_rules(self):
        idx = cc.index_prompts([self.path], redact=lambda s: s)
        goals = sorted(v['goal'] for v in idx.values())
        self.assertEqual(goals, ['fix the build please', 'now add a test'])  # AGENTS.md block skipped
        first = next(v for v in idx.values() if v['goal'] == 'fix the build please')
        self.assertEqual(first['index'], 3)  # first record carrying it; the event_msg copy is a replay
        self.assertEqual(first['sid'], 's1')
        rid = cc.prompt_id('now add a test', lambda s: s)
        self.assertEqual(idx[rid]['index'], 15)

    def test_subagent_and_automation_sessions_are_skipped(self):
        for i, m in enumerate((meta(source='exec'), meta(parent='p'), meta(source={'subagent': 'x'}))):
            p = write(self.tmp.name, f'rollout-x{i}.jsonl', [m, msg('user', 'scripted prompt')])
            self.assertEqual(cc.index_prompts([p], redact=lambda s: s), {})

    def test_context_excludes_prompt_and_maps_blocks(self):
        recs = cc.read_rollout(self.path)
        items = cc.context_items(recs, 15)
        self.assertEqual(cc.assistant_turns(items), 2)
        blocks = cc.render_blocks(items)
        texts = [b['content'] for b in blocks if b['kind'] == 'text']
        self.assertNotIn('now add a test', texts)
        self.assertNotIn('permissions blurb', texts)  # developer message dropped
        self.assertIn('fix the build please', texts)
        uses = {b['tool_use_id']: b for b in blocks if b['kind'] == 'tool_use'}
        self.assertEqual(json.loads(uses['c1']['content']), {'cmd': 'npm run build'})
        self.assertEqual(uses['c3']['tool_name'], 'mcp__node_repl__js')
        self.assertEqual(json.loads(uses['c2']['content']), {'input': '*** Begin Patch'})
        self.assertTrue(any(b['tool_name'] == 'web_search' and b['tool_use_id'] for b in blocks))
        res = {b['tool_use_id']: b for b in blocks if b['kind'] == 'tool_result'}
        self.assertTrue(res['c1']['is_error'])          # header exit code 2 (the 'Exit code: 0' in output is ignored)
        self.assertFalse(res['c2']['is_error'])         # apply_patch metadata exit 0
        self.assertFalse(res['c3']['is_error'])         # no exit code recorded
        self.assertEqual(res['c3']['content'], 'ok\n[image omitted]')
        self.assertEqual(res['c1']['tool_name'], 'exec_command')
        self.assertTrue(all(b['role'] == 'user' for b in res.values()))

    def test_compaction_restarts_context_from_replacement_history(self):
        recs = ROLLOUT[:7] + [dict(type='compacted', payload=dict(
            message='', replacement_history=[msg('user', 'summary of work')['payload']]))] + ROLLOUT[7:]
        items = cc.context_items(recs, len(recs) - 2)
        blocks = cc.render_blocks(items)
        self.assertEqual(blocks[0]['content'], 'summary of work')
        self.assertNotIn('Running the build.', [b['content'] for b in blocks])

    def test_payload_shape_and_is_error_forwarding(self):
        blocks = cc.render_blocks(cc.context_items(cc.read_rollout(self.path), 15))
        payload = v02.rules_payload(blocks)
        self.assertTrue(all(set(m) == {'role', 'text', 'toolUses', 'toolResults'} for m in payload))
        res = {r['tool_use_id']: r for m in payload for r in m['toolResults']}
        self.assertTrue(res['c1'].get('is_error'))
        self.assertNotIn('is_error', res['c2'])
        uses = [u for m in payload for u in m['toolUses']]
        self.assertTrue(all(isinstance(u['input'], dict) and u['tool_use_id'] for u in uses))

    def test_build_dossier_rereads_goal_and_checks_id(self):
        rid = cc.prompt_id('now add a test', lambda s: s)
        item = dict(id=rid, category='specified_task', label_source='x', confidence='high', session_hash='h',
                    path=self.path, index=15)
        d = cc.build_dossier(item, lambda s: s, rcb.render)
        self.assertTrue(d['id_ok'])
        self.assertEqual(d['goal'], 'now add a test')
        self.assertIn('[m0002 user text]\nfix the build please', d['text'])
        self.assertFalse(cc.build_dossier(dict(item, id='0' * 16), lambda s: s, rcb.render)['id_ok'])

    def test_exit_codes_from_code_mode_parts(self):
        out = [dict(type='input_text', text='Script completed\nOutput:\n'),
               dict(type='input_text', text='{"chunk_id":"x","exit_code":1,"output":"Exit code: 0"}')]
        self.assertEqual(cc.exit_codes(out), [1])


if __name__ == '__main__':
    unittest.main()
