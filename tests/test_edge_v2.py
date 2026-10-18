"""Edge suite v2: generator validation and the dev-edge fixtures (synthetic only; no CLI, no sealed files)."""
import json
import unittest

from research import edge_cases_build as eb
from research import edge_suite as es
from research import edge_v2 as e2
from research import opus_cli


def raw(blocks, **kw):
    case = dict(id='Some Case!', category='specified_task', use_case='u', goal='arruma isso', situation='s',
                must_keep='m', may_drop='d', why_judges_fail='w', blocks=blocks)
    case.update(kw)
    return dict(plan=dict(n=7, edge_type='coreference', lang='pt-BR', harness='codex', seed=1), case=case)


def blk(gold='may', role='tool', kind='tool_result', text='x' * 40, tool='exec_command', **kw):
    return dict(gold=gold, role=role, kind=kind, text=text, tool=tool, **kw)


GOOD = [blk(role='user', kind='text', tool=None, text='primeiro pedido')] + [blk(text=f'log line {i} ' * 30) for i in range(3)] + [
    blk('must', text='TypeError: x is undefined at a.ts:3'),
    blk(role='assistant', kind='tool_call', tool=None, text='apply_patch(file="a.ts")'),
    blk(kind='tool_result', tool=None, text='Done'),
    blk(text='', filler='build_log', n=30), blk(text='', filler='test_log', n=20),
    blk(role='assistant', kind='text', tool=None, text='notes', filler='chatter', n=8)]


class Generator(unittest.TestCase):
    def test_valid_case_becomes_fixture(self):
        fx = e2.to_fixture(raw(GOOD), set())
        self.assertTrue(fx['id'].startswith('v2_007_some_case'))
        self.assertEqual(fx['edge_type'], 'coreference')
        self.assertTrue(eb.validate(fx)['must_tokens'] > 0)
        tools = {b['text']: b['tool'] for b in fx['blocks'] if b['part'] == 0}
        self.assertEqual(tools['apply_patch(file="a.ts")'], 'apply_patch')  # inferred from the call text
        self.assertEqual(tools['Done'], 'apply_patch')  # result inherits the preceding call's tool
        self.assertTrue(es.score_case(fx, es.oracle(fx), 70)['passed'])

    def test_rejections(self):
        bad = {
            'kept evidence trivially most recent': GOOD[:-1] + [blk('must', text='late')],
            'kept evidence trivially largest': [blk('must', text='y' * 1100)] + GOOD[1:7] + [blk(text='short')],
            'bad gold': [blk('keep')] + GOOD[1:],
            'filler marked as kept': GOOD[:-1] + [blk('must', filler='pip_log', n=9)],
            'secret-shaped string': GOOD + [blk(text='key sk-' + 'a' * 24)],
            'one: group with a single member': GOOD + [blk('one:a')],
        }
        for why, blocks in bad.items():
            with self.assertRaises(ValueError, msg=why) as c:
                e2.to_fixture(raw(blocks), set())
            self.assertIn(why, str(c.exception))

    def test_plan_is_fixed_and_covers_every_type(self):
        p = e2.plan()
        self.assertEqual(p, e2.plan())
        self.assertEqual({x[1] for x in p}, set(e2.TYPES))
        self.assertEqual(len(p), sum(k for k, _ in e2.TYPES.values()))


class OpusCli(unittest.TestCase):
    def test_argv_is_safe(self):
        a = opus_cli.argv('sys', {'type': 'object'})
        self.assertFalse(any('dangerously' in x for x in a))
        self.assertEqual(a[a.index('--tools') + 1], '')
        self.assertEqual(a[a.index('--system-prompt') + 1], 'sys')
        self.assertIn('--no-session-persistence', a)

    def test_cache_ledger_and_cap(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as d:
            env = json.dumps(dict(is_error=False, structured_output={'ok': 1}))
            run = lambda p: (env, '', 0)  # noqa: E731
            self.assertEqual(opus_cli.call('s', {}, 'p', 't', root=d, runner=run), {'ok': 1})
            self.assertEqual(opus_cli.call('s', {}, 'p', 't', root=d, runner=run), {'ok': 1})  # cached
            self.assertEqual(opus_cli.calls_used(Path(d) / 'opus-calls.jsonl'), 1)
            limit = lambda p: (json.dumps(dict(is_error=True, result='usage limit reached')), '', 1)  # noqa: E731
            with self.assertRaises(opus_cli.lj.LimitHit):
                opus_cli.call('s', {}, 'q', 't', root=d, runner=limit)
            old, opus_cli.CAP = opus_cli.CAP, 2
            try:
                with self.assertRaises(SystemExit):
                    opus_cli.call('s', {}, 'r', 't', root=d, runner=run)
            finally:
                opus_cli.CAP = old


class DevEdgeFixtures(unittest.TestCase):
    def test_dev_edge_fixtures_are_valid(self):
        cases = e2.load_dev()
        if not cases:
            self.skipTest('dev-edge v2 not built')
        for c in cases:
            eb.validate(c)
            self.assertIn(c['edge_type'], e2.TYPES)
            self.assertTrue(es.score_case(c, es.oracle(c), 70)['passed'], c['id'])
        rc = json.loads((e2.OUT / 'edge-v2-receipt.json').read_text())
        self.assertEqual(rc['n_dev'], len(cases))
        self.assertEqual(sum(rc['dev'].values()), len(cases))
        self.assertEqual(sum(rc['sealed'].values()), len(rc['sealed_sha256']))
