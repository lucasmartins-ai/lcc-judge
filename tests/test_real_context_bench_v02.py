"""Stdlib-only tests for the v0.2 rules arm path of the real-context bench (no lcc, no network)."""
import unittest

from research import real_context_bench_v02 as v02


def blk(m, kind, content, tid=None, name=None, err=False, role='user'):
    return dict(m=m, role=role, kind=kind, tool_name=name, tool_use_id=tid, is_error=err, content=content)


def arm(rate, pooled, trips=0):
    return dict(retention_item=dict(rate=rate), reduction_tokens=dict(pooled=pooled), guard_trips=trips)


class V02Tests(unittest.TestCase):
    def test_payload_forwards_is_error_only_where_set(self):
        blocks = [blk(0, 'tool_use', '{"command": "x"}', 'a', 'Bash', role='assistant'),
                  blk(0, 'tool_use', '{"command": "y"}', 'b', 'Bash', role='assistant'),
                  blk(1, 'tool_result', 'boom', 'a', 'Bash', err=True),
                  blk(1, 'tool_result', 'fine', 'b', 'Bash')]
        res = {r['tool_use_id']: r for m in v02.rules_payload(blocks) for r in m['toolResults']}
        self.assertIs(res['a'].get('is_error'), True)
        self.assertNotIn('is_error', res['b'])

    def test_verdict(self):
        self.assertTrue(v02.verdict(arm(.98, .3), arm(.98, .0))['wins'])
        self.assertFalse(v02.verdict(arm(.97, .3), arm(.98, .0))['wins'])  # retention below
        self.assertFalse(v02.verdict(arm(.98, .0), arm(.98, .0))['wins'])  # reduction must be strictly higher
        self.assertFalse(v02.verdict(arm(1, .3, trips=1), arm(.98, .0))['wins'])


if __name__ == '__main__':
    unittest.main()
