"""LLM-judge arm: parsing, safety flags and resume, on synthetic output only (no CLI is ever spawned)."""
import json
import tempfile
import unittest
from pathlib import Path

from research import llm_judge_arm as lj

IDS = ['b1', 'b2']


def ans(**kw):
    return {'answers': {f'keep_{k}': v for k, v in kw.items()}}


class Parse(unittest.TestCase):
    def test_claude_structured_output(self):
        env = {'type': 'result', 'is_error': False, 'result': '',
               'structured_output': ans(b1={'noul': 0.9, 'confidence': 0.8}, b2={'noul': 0.1, 'confidence': 0.7})}
        self.assertEqual(lj.parse_output(json.dumps(env), '', 0, IDS), {'b1': 0.9, 'b2': 0.1})

    def test_result_text_with_fence_and_missing_answer(self):
        text = '```json\n' + json.dumps(ans(b1={'noul': 0.4, 'confidence': 0.5})) + '\n```'
        env = {'type': 'result', 'is_error': False, 'result': text}
        self.assertEqual(lj.parse_output(json.dumps(env), '', 0, IDS), {'b1': 0.4, 'b2': None})

    def test_out_of_range_is_unscored(self):
        out = json.dumps({'response': json.dumps(ans(b1={'noul': 1.7, 'confidence': 0.5},
                                                     b2={'noul': 0.2, 'confidence': 0.5}))})
        self.assertEqual(lj.parse_output(out, '', 0, IDS), {'b1': None, 'b2': 0.2})

    def test_plain_text_stdout(self):
        out = 'Here you go: ' + json.dumps(ans(b1={'noul': 0.3, 'confidence': 0.9}, b2={'noul': 0.6, 'confidence': 0.9}))
        self.assertEqual(lj.parse_output(out, '', 0, IDS), {'b1': 0.3, 'b2': 0.6})

    def test_limit_errors_raise_limithit(self):
        env = {'type': 'result', 'is_error': True, 'result': "Claude AI usage limit reached|1760000000"}
        with self.assertRaises(lj.LimitHit):
            lj.parse_output(json.dumps(env), '', 1, IDS)
        with self.assertRaises(lj.LimitHit):
            lj.parse_output('', 'Error: 429 RESOURCE_EXHAUSTED', 1, IDS)

    def test_other_errors_raise_runtimeerror(self):
        with self.assertRaises(RuntimeError) as c:
            lj.parse_output('not json', 'boom', 2, IDS)
        self.assertNotIsInstance(c.exception, lj.LimitHit)
        # an error envelope is never parsed for answers, even if it carries some
        env = dict(ans(b1={'noul': 0.9, 'confidence': 0.9}), is_error=True)
        with self.assertRaises(RuntimeError):
            lj.parse_output(json.dumps(env), '', 0, IDS)


class Safety(unittest.TestCase):
    def test_argv(self):
        for arm in lj.ARMS:
            a = lj.argv_for(arm)
            self.assertFalse(any('dangerously' in x for x in a))
            self.assertIn('--output-format', a)
        c = lj.argv_for('opus')
        self.assertEqual(c[c.index('--tools') + 1], '')
        self.assertEqual(c[c.index('--model') + 1], 'opus')
        g = lj.argv_for('gemini-flash')
        self.assertEqual(g[g.index('--mode') + 1], 'plan')
        self.assertIn('--sandbox', g)

    def test_prompt_mirrors_jev_question(self):
        from lcc.relevance.compactor import KEEP_INSTRUCTIONS
        p = lj.prompt('fix the parser', [('b1', 'def parse(): pass')])
        state = json.loads(p.split('STATE:\n', 1)[1].split('\n\nQUESTIONS:', 1)[0])
        self.assertEqual(state, {'objective': 'fix the parser', 'blocks': [{'id': 'b1', 'text': 'def parse(): pass'}]})
        self.assertIn(KEEP_INSTRUCTIONS.format(block_id='b1'), p)

    def test_batches_follow_lcc_limits(self):
        pairs = [(f'b{i}', 'x' * 3000) for i in range(10)]
        bs = lj.batches(pairs)
        self.assertTrue(all(sum(len(t) for _, t in b) <= 12000 for b in bs))
        self.assertEqual([i for b in bs for i, _ in b], [i for i, _ in pairs])
        self.assertLessEqual(max(len(b) for b in bs), 8)


class Run(unittest.TestCase):
    def items(self):
        return [('it1', 'goal one', [(f'a{i}', f'block {i} ' * 40) for i in range(10)]),
                ('it2', 'goal two', [('c0', 'short block text here')])]

    def fake(self, log, limit_after=None):
        def caller(arm, text, cwd):
            self.assertFalse(any(Path(cwd).iterdir()))
            log.append(text)
            if limit_after is not None and len(log) > limit_after:
                return '', 'You have hit your limit', 1
            st = json.loads(text.split('STATE:\n', 1)[1].split('\n\nQUESTIONS:', 1)[0])
            return json.dumps({'is_error': False, 'structured_output': {'answers': {
                f"keep_{b['id']}": {'noul': 0.5, 'confidence': 0.5} for b in st['blocks']}}}), '', 0
        return caller

    def test_resume_and_limit_stop(self):
        with tempfile.TemporaryDirectory() as root:
            log = []
            r = lj.run('opus', 'synthetic', root=root, caller=self.fake(log, limit_after=1), items=self.items())
            self.assertTrue(r['stopped'].startswith('limit'))
            self.assertEqual(len(log), 2)  # one success, then the limit call; no retry
            log2 = []
            r = lj.run('opus', 'synthetic', root=root, caller=self.fake(log2), items=self.items())
            self.assertIsNone(r['stopped'])
            self.assertEqual(r['items_done'], 2)
            sc = lj.scores('opus', 'synthetic', root=root)
            self.assertEqual(len(sc['it1']), 10)
            self.assertEqual(sc['it2'], {'c0': 0.5})
            n_batches = len(log) - 1 + len(log2)
            log3 = []
            lj.run('opus', 'synthetic', root=root, caller=self.fake(log3), items=self.items())
            self.assertEqual(log3, [])  # everything cached
            self.assertGreater(n_batches, 2)

    def test_max_calls(self):
        with tempfile.TemporaryDirectory() as root:
            log = []
            r = lj.run('opus', 'synthetic', root=root, caller=self.fake(log), items=self.items(), max_calls=1)
            self.assertEqual((r['calls'], r['stopped']), (1, 'max_calls'))
            self.assertEqual(lj.scores('opus', 'synthetic', root=root), {})

    def test_shards_are_disjoint(self):
        with tempfile.TemporaryDirectory() as root:
            lj.run('opus', 'synthetic', root=root, caller=self.fake([]), items=self.items(), shard=(1, 2))
            self.assertEqual(sorted(lj.scores('opus', 'synthetic', root=root)), ['it2'])
            lj.run('opus', 'synthetic', root=root, caller=self.fake([]), items=self.items(), shard=(0, 2))
            self.assertEqual(sorted(lj.scores('opus', 'synthetic', root=root)), ['it1', 'it2'])


if __name__ == '__main__':
    unittest.main()
