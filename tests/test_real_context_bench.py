"""Synthetic-fixture tests for the real-context bench v0 harness. Never touches real transcripts."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from research import real_context_bench as rcb

PROTO = json.loads(rcb.PROTOCOL.read_text())


def jl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(r) + '\n' for r in rows), encoding='utf-8')


def rec(uuid, parent, type_, content, **kw):
    role = 'assistant' if type_ == 'assistant' else 'user'
    return dict(uuid=uuid, parentUuid=parent, type=type_, message=dict(role=role, content=content), **kw)


def blk(role, kind, content, tool_name=None, tool_use_id=None, is_error=False):
    return dict(m=0, role=role, kind=kind, tool_name=tool_name, tool_use_id=tool_use_id,
                is_error=is_error, content=content)


class ContextWalkTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / 'proj' / 's.jsonl'
        jl(self.path, [
            rec('a0', None, 'user', 'before the boundary, must never appear'),
            dict(uuid='cb', parentUuid='a0', type='system', subtype='compact_boundary'),
            rec('u1', 'cb', 'user', 'first kept user message', isMeta=True),
            rec('a1', 'u1', 'assistant', [
                dict(type='thinking', thinking='secret reasoning', signature='x'),
                dict(type='text', text='assistant says hello'),
                dict(type='tool_use', id='t1', name='Bash', input=dict(command='git status')),
            ]),
            dict(uuid='att', parentUuid='a1', type='attachment'),
            rec('r1', 'att', 'user', [dict(type='tool_result', tool_use_id='t1', is_error=False, content=[
                dict(type='text', text='On branch main'), dict(type='image', source={}),
                dict(type='text', text='clean')])]),
            rec('side', 'r1', 'assistant', [dict(type='text', text='sibling branch, excluded')]),
            rec('a2', 'r1', 'assistant', [dict(type='text', text='latest reply')]),
            rec('p', 'a2', 'user', 'the prompt itself'),
        ])

    def tearDown(self):
        self.tmp.cleanup()

    def test_walk_excludes_prompt_siblings_and_stops_at_boundary(self):
        prompt, records = rcb.context_records(self.path, 'p')
        self.assertEqual(rcb.claude_text(prompt['message']['content']), 'the prompt itself')
        self.assertEqual([r['uuid'] for r in records], ['u1', 'a1', 'r1', 'a2'])

    def test_render_blocks_and_headers(self):
        _, records = rcb.context_records(self.path, 'p')
        blocks = rcb.render_blocks(records)
        self.assertEqual([(b['m'], b['role'], b['kind'], b['tool_name']) for b in blocks], [
            (0, 'user', 'text', None), (1, 'assistant', 'text', None), (1, 'assistant', 'tool_use', 'Bash'),
            (2, 'user', 'tool_result', 'Bash'), (3, 'assistant', 'text', None)])
        self.assertEqual(blocks[2]['content'], '{"command": "git status"}')
        self.assertEqual(blocks[3]['content'], 'On branch main\n[image omitted]\nclean')
        text = rcb.render(blocks)
        self.assertTrue(text.startswith('[m0000 user text]\nfirst kept user message\n\n'))
        self.assertIn('[m0001 assistant tool_use Bash]\n{"command"', text)
        self.assertNotIn('secret reasoning', text)
        self.assertNotIn('the prompt itself', text)

    def test_build_dossier_checks_id_with_injected_redact(self):
        goal = 'the prompt itself'
        item = dict(id=hashlib.sha256(f'claude\0{goal.upper()}'.encode()).hexdigest()[:16], category='git_ship',
                    label_source='x', confidence='high', path=str(self.path), uuid='p', session_hash='h')
        d = rcb.build_dossier(item, redact=str.upper)
        self.assertTrue(d['id_ok'])
        self.assertEqual(d['goal'], goal)
        self.assertEqual(d['text'], rcb.render(d['blocks']))
        self.assertFalse(rcb.build_dossier(dict(item, id='0' * 16), redact=str.upper)['id_ok'])


class AllocationTests(unittest.TestCase):
    def test_four_per_stratum_then_round_robin_with_one_rng(self):
        pool = {f'{c}{i}': dict(ctx_assistant=1) for c, k in (('a', 9), ('b', 2), ('c', 6)) for i in range(k)}
        pool['z0'] = dict(ctx_assistant=0)  # no assistant record: ineligible
        pool['a0'].update(label='a', confidence='low', label_source='llm_v2_pass')  # low: ineligible
        extra = {i: dict(label=i[0], confidence='high', label_source='bench') for i in pool if i != 'a0'}
        ids, eligible = rcb.allocate(pool, extra, seed=7, n=11)
        self.assertEqual(eligible, {'a': 8, 'b': 2, 'c': 6})
        per = {k: sum(i.startswith(k) for i in ids) for k in 'abc'}
        self.assertEqual(per, {'a': 5, 'b': 2, 'c': 4})
        self.assertEqual(ids, rcb.allocate(pool, extra, seed=7, n=11)[0])
        self.assertNotIn('a0', ids)


DOSSIER_BLOCKS = [
    blk('user', 'text', 'please look at src/app.py and the docs'),
    blk('assistant', 'tool_use', '{"todos": ["write the harness for real"]}', 'TodoWrite', 't0'),
    blk('assistant', 'tool_use', '{"command": "git status --short"}', 'Bash', 't1'),
    blk('user', 'tool_result', 'M src/app.py\n?? new file here', 'Bash', 't1'),
    blk('assistant', 'tool_use', '{"command": "pytest -q"}', 'Bash', 't2'),
    blk('user', 'tool_result', 'Traceback (most recent call last): boom', 'Bash', 't2', True),
    blk('assistant', 'tool_use', '{"file_path": "src/app.py", "content": "print(1)"}', 'Write', 't3'),
    blk('user', 'tool_result', 'File written successfully', 'Write', 't3'),
    blk('assistant', 'text', 'S' * 600),
    blk('assistant', 'text', 'Done: I edited src/app.py as asked.'),
]


def dossier(category, goal, blocks=DOSSIER_BLOCKS):
    return dict(id='x', category=category, goal=goal, blocks=blocks, text=rcb.render(blocks))


class ProbeTests(unittest.TestCase):
    LONG = ' '.join(['word'] * 20)  # >= 15 words: no short-goal additions

    def test_probe_targets_cover_every_definition(self):
        b = DOSSIER_BLOCKS
        t = lambda name, goal=self.LONG: rcb.probe_targets(name, b, goal, 12)  # noqa: E731
        self.assertEqual(t('LAST_AGENT_TURN'), [b[9]['content']])
        self.assertEqual(t('TASK_STATE'), [b[1]['content']])
        self.assertEqual(t('LAST_TOOL_RESULT'), [b[7]['content']])
        self.assertEqual(t('ERROR_RESULT'), [b[5]['content']])
        self.assertIsNone(t('ERROR_RESULT', 'it fails with Traceback (most recent call last) again'))
        self.assertEqual(t('GIT_STATE'), [b[3]['content']])
        self.assertEqual(t('LATEST_SUMMARY'), [b[8]['content']])
        self.assertEqual(t('LAST_ARTIFACT_EDIT'), [b[6]['content']])
        # NAMED_REFS: latest block naming each ref; refs absent from the context are skipped
        self.assertEqual(t('NAMED_REFS', 'fix src/app.py and https://nowhere.example/x'), [b[9]['content']])
        self.assertIsNone(t('NAMED_REFS', 'fix the thing in other.py'))

    def test_absent_or_short_targets_are_not_applicable(self):
        short = [blk('assistant', 'text', 'ok'), blk('user', 'tool_result', 'tiny', 'Bash', 't')]
        for name in ('LAST_AGENT_TURN', 'LAST_TOOL_RESULT', 'TASK_STATE', 'GIT_STATE', 'LATEST_SUMMARY',
                     'LAST_ARTIFACT_EDIT', 'ERROR_RESULT', 'NAMED_REFS'):
            self.assertIsNone(rcb.probe_targets(name, short, 'see a/b', 12), name)

    def test_probes_for_category_and_short_goal_rule(self):
        self.assertEqual(rcb.probes_for('git_ship', self.LONG, PROTO), ['GIT_STATE'])
        self.assertEqual(rcb.probes_for('git_ship', 'ship it', PROTO), ['GIT_STATE', 'LAST_AGENT_TURN', 'TASK_STATE'])
        self.assertEqual(rcb.probes_for('general_question', self.LONG, PROTO), [])
        self.assertEqual(rcb.probes_for('approve_or_pick', 'yes', PROTO), ['LAST_AGENT_TURN', 'TASK_STATE'])

    def test_score_item_whitespace_collapse_pass_fail_and_na(self):
        d = dossier('failure_report', self.LONG)
        ok = rcb.score_item(d, dict(status='ok', output='x\n' + DOSSIER_BLOCKS[5]['content'].replace(' ', '\n  ')), PROTO)
        self.assertEqual(ok['probes'], {'ERROR_RESULT': True})
        self.assertTrue(ok['item_pass'])
        bad = rcb.score_item(d, dict(status='ok', output='nothing'), PROTO)
        self.assertEqual((bad['probes'], bad['item_pass']), ({'ERROR_RESULT': False}, False))
        na = rcb.score_item(dossier('failure_report', 'Traceback (most recent call last) ' + self.LONG),
                            dict(status='ok', output=''), PROTO)
        self.assertEqual((na['probes'], na['item_pass']), ({'ERROR_RESULT': None}, None))
        err = rcb.score_item(d, dict(status='error', output=None), PROTO)
        self.assertEqual((err['probes'], err['item_pass']), ({'ERROR_RESULT': False}, False))


class ScoreTests(unittest.TestCase):
    def test_aggregate_full_sanity_verdict_and_counts_only_copy(self):
        dossiers = [dossier('failure_report', ProbeTests.LONG), dossier('general_question', ProbeTests.LONG)]
        dossiers[1]['id'] = 'y'
        n = len(dossiers[0]['text'])

        def run(out, toks, lat=5, status='ok'):
            return dict(status=status, output=out, in_bytes=n, out_bytes=len(out or ''), in_tokens=100,
                        out_tokens=toks, token_method='approximate', latency_ms=lat, guard_trips=0)
        runs = {
            'full': {d['id']: run(d['text'], 100) for d in dossiers},
            'mechanical': {'x': run(DOSSIER_BLOCKS[5]['content'], 10), 'y': run('', 0)},
            'specialist': {d['id']: run(d['text'], 100, 900) for d in dossiers},
        }
        s = rcb.aggregate(dossiers, runs, PROTO)
        self.assertEqual(s['arms']['full']['retention_item']['rate'], 1.0)
        self.assertFalse(s['void'])
        self.assertEqual(s['arms']['mechanical']['retention_item']['k'], 1)
        self.assertEqual(s['arms']['mechanical']['retention_item']['n'], 1)  # general_question: no probes
        self.assertAlmostEqual(s['arms']['mechanical']['reduction_tokens']['pooled'], 0.95)
        self.assertEqual(s['verdict']['specialist']['wins'], False)
        public = rcb.counts_only(s)
        self.assertNotIn('"x"', json.dumps(public))
        self.assertNotIn('items', public)

        runs['full']['x'] = run('', 0)
        self.assertTrue(rcb.aggregate(dossiers, runs, PROTO)['void'])

    def test_wilson_and_p90(self):
        lo, hi = rcb.wilson(5, 10)
        self.assertAlmostEqual(lo, 0.2366, places=3)
        self.assertAlmostEqual(hi, 0.7634, places=3)
        self.assertEqual(rcb.wilson(0, 0), (None, None))
        self.assertEqual(rcb.quantile(list(range(1, 11)), 0.9), 9)

    def test_specialist_at_mechanical_budget(self):
        blocks = [('b1', 'protected one'), ('b2', 'second block'), ('b3', 'third block text')]
        out = rcb.at_budget(blocks, protected={'b1'}, ranking=['b3', 'b2'], budget=3, count=lambda s: len(s.split()))
        self.assertEqual(out, 'protected one\n\nthird block text')


class GuardTests(unittest.TestCase):
    def test_remote_arm_refused_without_flag(self):
        with self.assertRaises(SystemExit):
            rcb.check_arm('jev_block', PROTO, allow_remote=False)
        with self.assertRaises(SystemExit):
            rcb.check_arm('jev_transcript', PROTO, allow_remote=False)
        with self.assertRaises(SystemExit):
            rcb.check_arm('laya', PROTO, allow_remote=True)
        rcb.check_arm('mechanical', PROTO, allow_remote=False)

    def test_protocol_hash_mismatch_refuses(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'protocol.json'
            p.write_text('{}')
            (Path(tmp) / 'protocol.json.sha256').write_text('0' * 64 + '  protocol.json\n')
            with self.assertRaises(SystemExit):
                rcb.load_protocol(p)

    def test_socket_guard_counts_and_raises(self):
        import socket
        before = rcb.GUARD['trips']
        with rcb.network_guard():
            with self.assertRaises(OSError):
                socket.create_connection(('127.0.0.1', 9))
        self.assertEqual(rcb.GUARD['trips'], before + 1)
        self.assertIsNot(socket.create_connection, rcb._blocked)


if __name__ == '__main__':
    unittest.main()
