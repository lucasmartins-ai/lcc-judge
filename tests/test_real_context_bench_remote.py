"""Fake-client tests for the v0.1 remote Jev arms of the real-context bench. No network, no lcc."""
import json
import math
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace

from research import real_context_bench as rcb

SECRET = 'sk-' + 'test-SECRET-never-write-me'  # split so secret scanners skip the fake key
COUNT = lambda payload: (len(json.dumps(payload)) // 4, 'test')  # noqa: E731


def meter(cap=1.0, **kw):
    kw.setdefault('rate_per_mtok', 1e6)  # 1 USD per token: easy arithmetic
    kw.setdefault('overhead_tokens', 0)
    kw.setdefault('count', lambda p: (p['tokens'], 'test'))
    kw.setdefault('allow_network', False)
    return rcb.Meter(cap, **kw)


class MeterTests(unittest.TestCase):
    def test_cap_aborts_before_the_call_that_would_exceed(self):
        m = meter(cap=10.0)
        sent = []
        post = m.wrap(lambda p: sent.append(p) or {'answers': {}})
        m.begin_item('a')
        post({'tokens': 4})
        post({'tokens': 6})  # exactly at the cap: allowed
        with self.assertRaises(rcb.CapExceeded):
            post({'tokens': 1})
        self.assertEqual(len(sent), 2)  # the third call never left
        self.assertTrue(m.state['aborted'])
        with self.assertRaises(rcb.CapExceeded):  # once aborted, nothing else goes out
            post({'tokens': 0})
        self.assertEqual(len(sent), 2)
        self.assertEqual(m.end_item()['calls'], 2)

    def test_spend_from_earlier_arms_counts_against_the_cap(self):
        m = meter(cap=10.0, spent_before=8.0)
        post = m.wrap(lambda p: {'answers': {}})
        m.begin_item('a')
        with self.assertRaises(rcb.CapExceeded):
            post({'tokens': 3})

    def test_arm_sub_cap(self):
        m = meter(cap=35.0, arm_cap_usd=5.0)
        post = m.wrap(lambda p: {'answers': {}})
        m.begin_item('a')
        post({'tokens': 5})
        with self.assertRaises(rcb.CapExceeded):
            post({'tokens': 1})
        self.assertIn('arm $5', m.state['abort_reason'])

    def test_run_order_is_seeded_and_complete(self):
        ids = [f'i{k}' for k in range(20)]
        order = rcb.run_order(ids, 20261009)
        self.assertEqual(sorted(order), sorted(ids))
        self.assertEqual(order, rcb.run_order(list(reversed(ids)), 20261009))
        self.assertNotEqual(order, sorted(ids))

    def test_cost_accounting_projection_overhead_and_api_usage(self):
        m = meter(cap=100.0, rate_per_mtok=1e6, overhead_tokens=2)
        replies = iter([{'answers': {}},  # no usage: projected cost stands
                        {'answers': {}, 'usage': {'input_tokens': 3, 'output_tokens': 1}},
                        {'answers': {}, 'usage': {'cost_usd': 0.5, 'input_tokens': 99}}])
        post = m.wrap(lambda p: next(replies))
        m.begin_item('a')
        for t in (5, 5, 5):
            post({'tokens': t})
        it = m.end_item()
        self.assertEqual(it['calls'], 3)
        self.assertAlmostEqual(it['projected_usd'], 21.0)  # 3 x (5 + 2)
        self.assertAlmostEqual(it['cost_usd'], 7.0 + 4.0 + 0.5)
        self.assertEqual(it['api_input_tokens'], 3 + 99)
        self.assertEqual(m.state['cost_sources'], {'projected': 1, 'api_usage': 1, 'api_cost': 1})
        self.assertAlmostEqual(m.state['spent_usd'], 11.5)

    def test_real_pricing_basis(self):
        self.assertAlmostEqual(rcb.projected_usd(44000), 0.1889, places=4)  # docs/JEV.md: $0.187 at 44K

    def test_failed_call_is_charged_its_projection_and_not_retried(self):
        m = meter(cap=100.0)
        calls = []

        def boom(p):
            calls.append(p)
            raise OSError('HTTP 503')
        post = m.wrap(boom)
        m.begin_item('a')
        with self.assertRaises(OSError):
            post({'tokens': 7})
        self.assertEqual(len(calls), 1)
        it = m.end_item()
        self.assertEqual((it['calls'], it['failed_calls'], it['cost_usd']), (1, 1, 7.0))

    def test_deadline_stops_further_calls(self):
        m = meter(cap=100.0)
        post = m.wrap(lambda p: {'answers': {}})
        m.begin_item('a', deadline=time.monotonic() - 1)
        with self.assertRaises(rcb.ItemDeadline):
            post({'tokens': 1})
        self.assertEqual(m.end_item()['calls'], 0)

    def test_cost_file_is_persisted(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / '_cost.json'
            m = meter(cap=100.0, path=path)
            m.begin_item('a')
            m.wrap(lambda p: {'answers': {}})({'tokens': 3})
            m.end_item()
            saved = json.loads(path.read_text())
            self.assertEqual((saved['calls'], saved['spent_usd'], saved['cap_usd']), (1, 3.0, 100.0))


def dossiers(n):
    blocks = [dict(m=0, role='user', kind='text', tool_name=None, tool_use_id=None, is_error=False, content='hi there')]
    return [dict(id=f'd{i}', category='general_question', goal='g', blocks=blocks, text=f'context {i}') for i in range(n)]


class RunRemoteTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.out = Path(self.tmp.name) / 'jev_block'
        self.out.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def runner_for(self, post, tokens=4, fail_ids=()):
        def make(d):
            def run(text, goal):
                post({'tokens': tokens})
                if d['id'] in fail_ids:
                    raise RuntimeError(f'jev exploded, key was {SECRET}')
                return 'out ' + text, {'keep_ids': ['b1'], 'note': f'echo {SECRET}'}
            return run
        return make

    def test_abort_cleanly_and_report_partial(self):
        m = meter(cap=10.0, path=self.out / '_cost.json')
        post = m.wrap(lambda p: {'answers': {}})
        res = rcb.run_remote('jev_block', dossiers(5), self.out, m, self.runner_for(post), COUNT, secrets=[SECRET])
        # 4 + 4 fit, the third item's call would reach 12 > 10
        self.assertEqual(res['status'], {'ok': 2, 'aborted_cap': 1})
        self.assertEqual((res['processed'], res['not_run'], res['partial']), (3, 2, True))
        rec = json.loads((self.out / 'd2.json').read_text())
        self.assertEqual((rec['status'], rec['jev_meter']['calls']), ('aborted_cap', 0))
        self.assertFalse((self.out / 'd3.json').exists())
        cost = json.loads((self.out / '_cost.json').read_text())
        self.assertTrue(cost['aborted'])
        self.assertEqual(cost['partial'], True)
        self.assertEqual(cost['spent_usd'], 8.0)

    def test_failed_item_is_recorded_once_and_the_run_continues(self):
        m = meter(cap=100.0)
        sent = []
        post = m.wrap(lambda p: sent.append(p) or {'answers': {}})
        res = rcb.run_remote('jev_block', dossiers(3), self.out, m, self.runner_for(post, fail_ids={'d1'}), COUNT,
                             secrets=[SECRET])
        self.assertEqual(res['status'], {'ok': 2, 'error': 1})
        self.assertEqual(len(sent), 3)  # one call per item: the failed one was not re-run
        self.assertFalse(res['partial'])
        with self.assertRaises(SystemExit):  # a second pass over the same arm dir is refused
            rcb.run_remote('jev_block', dossiers(3), self.out, meter(cap=100.0), self.runner_for(post), COUNT)

    def test_key_is_never_written(self):
        m = meter(cap=100.0, path=self.out / '_cost.json')
        post = m.wrap(lambda p: {'answers': {}})
        rcb.run_remote('jev_block', dossiers(2), self.out, m, self.runner_for(post, fail_ids={'d1'}), COUNT,
                       secrets=[SECRET])
        for p in self.out.iterdir():
            self.assertNotIn(SECRET, p.read_text(), p.name)
        self.assertIn('[redacted]', (self.out / 'd1.json').read_text())

    def test_client_is_built_without_retries_and_refuses_without_key(self):
        seen = {}

        class FakeJev:
            @classmethod
            def from_env(cls, **kw):
                seen.update(kw)
                return SimpleNamespace(api_key=SECRET)
        client = rcb.jev_client(Path(self.tmp.name) / 'ledger.jsonl', cls=FakeJev)
        self.assertEqual(seen['attempts'], 1)
        self.assertEqual(client.api_key, SECRET)

        class NoKey:
            @classmethod
            def from_env(cls, **kw):
                return None
        with self.assertRaises(SystemExit):
            rcb.jev_client(Path(self.tmp.name) / 'ledger.jsonl', cls=NoKey)


class TranscriptMappingTests(unittest.TestCase):
    BLOCKS = [
        dict(m=0, role='user', kind='text', tool_name=None, tool_use_id=None, is_error=False, content='do it'),
        dict(m=1, role='assistant', kind='text', tool_name=None, tool_use_id=None, is_error=False, content='ok'),
        dict(m=1, role='assistant', kind='tool_use', tool_name='Bash', tool_use_id='t1', is_error=False,
             content='{"command": "ls"}'),
        dict(m=1, role='assistant', kind='tool_use', tool_name='Read', tool_use_id='t2', is_error=False,
             content='{"file_path": "a.py"}'),
        dict(m=2, role='user', kind='tool_result', tool_name='Bash', tool_use_id='t1', is_error=False,
             content='a.py b.py'),
        dict(m=2, role='user', kind='tool_result', tool_name='Read', tool_use_id='t2', is_error=False,
             content='print(1)\n' * 50),
    ]

    def test_payload_groups_blocks_into_messages(self):
        p = rcb.transcript_payload(self.BLOCKS)
        self.assertEqual([m['role'] for m in p], ['user', 'assistant', 'user'])
        self.assertEqual(p[1]['text'], 'ok')
        self.assertEqual(p[1]['toolUses'], [dict(tool_use_id='t1', tool='Bash', input={'command': 'ls'}),
                                            dict(tool_use_id='t2', tool='Read', input={'file_path': 'a.py'})])
        self.assertEqual(p[2]['toolResults'][0], dict(tool_use_id='t1', text='a.py b.py'))

    def test_apply_drops_pairs_and_trims_results(self):
        msgs = [SimpleNamespace(tool_results=[SimpleNamespace(id='t2', text='print(1)\n[... trimmed ...]')])]
        decisions = [dict(id='t1', decision='drop'), dict(id='t2', decision='trim')]
        out = rcb.apply_transcript(self.BLOCKS, decisions, msgs)
        self.assertNotIn('{"command": "ls"}', out)
        self.assertNotIn('a.py b.py', out)
        self.assertIn('[... trimmed ...]', out)
        self.assertIn('{"file_path": "a.py"}', out)
        self.assertEqual(rcb.apply_transcript(self.BLOCKS, [], []), rcb.render(self.BLOCKS))


class OfflineArmsUnchangedTests(unittest.TestCase):
    V0_RECORD_KEYS = {'id', 'arm', 'status', 'error', 'latency_ms', 'in_bytes', 'out_bytes', 'in_tokens',
                      'out_tokens', 'token_method', 'guard_trips', 'output'}

    def test_v0_constants_and_protocol_untouched(self):
        self.assertEqual(rcb.LOCAL_ARMS, ('full', 'mechanical', 'specialist'))
        self.assertEqual(rcb.MECH_KW, dict(threshold=0.4, min_block_chars=40, max_block_chars=6000,
                                           trim_head_chars=300, model='gpt-4.1'))
        self.assertEqual(rcb.sha256_file(rcb.PROTOCOL),
                         'f5608429a3740bc74da04c6bd77071fe08cebd3ad887ae996a32ba1df5e490c3')

    def test_full_arm_record_shape_is_v0(self):
        runner, load_ms = rcb.make_runner('full')
        d = dossiers(1)[0]
        rec = rcb.run_item('full', d, runner, lambda s: (len(s), 'test'))
        self.assertIsNone(load_ms)
        self.assertEqual(set(rec), self.V0_RECORD_KEYS)
        self.assertEqual((rec['status'], rec['output']), ('ok', d['text']))

    def test_remote_arms_refused_without_flag(self):
        with self.assertRaises(SystemExit):
            rcb.check_arm('jev_block', json.loads(rcb.PROTOCOL.read_text()), allow_remote=False)
        with self.assertRaises(SystemExit):
            rcb.run_remote_phase('jev_transcript', allow_remote=False)


class ProtocolV01Tests(unittest.TestCase):
    def test_amendment_keeps_v0_sample_probes_metrics_and_stop(self):
        if not rcb.PROTOCOL_V01.exists():
            self.skipTest('v0.1 protocol not written yet')
        v0, v1 = json.loads(rcb.PROTOCOL.read_text()), json.loads(rcb.PROTOCOL_V01.read_text())
        for k in ('sample', 'context', 'probes', 'metrics', 'stop_criterion', 'pins', 'privacy'):
            self.assertEqual(v0[k], v1[k], k)
        self.assertEqual(v1['amends']['sha256'], rcb.sha256_file(rcb.PROTOCOL))
        self.assertEqual(v1['remote']['cap_usd'], 85)  # AMENDMENT-cap.md
        self.assertTrue(math.isclose(v1['remote']['pricing']['usd_per_mtok_input'], 4.25))


if __name__ == '__main__':
    unittest.main()


class CapBypassTests(unittest.TestCase):
    def test_remote_run_refuses_other_run_dirs_and_id_subsets(self):
        for kw in (dict(runs='runs-retry'), dict(ids={'x'})):
            with self.subTest(**{k: str(v) for k, v in kw.items()}), self.assertRaises(SystemExit) as cm:
                rcb.run_remote_phase('jev_block', allow_remote=True, **kw)
            self.assertIn('--runs/--ids', str(cm.exception))

    def test_spend_in_any_run_dir_counts_against_the_cap(self):
        root = Path(tempfile.mkdtemp())
        for rel, usd in (('runs/jev_transcript', 3.0), ('runs-old/jev_block', 5.0), ('runs/jev_block', 99.0)):
            (root / rel).mkdir(parents=True)
            (root / rel / '_cost.json').write_text(json.dumps(dict(spent_usd=usd)))
        self.assertEqual(rcb._spent_by_other_arms(root, 'runs', 'jev_block'), 8.0)
