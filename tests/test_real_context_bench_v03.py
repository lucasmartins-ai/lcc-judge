"""Stdlib-only tests for the v0.3 audit sampler and packet helpers (no lcc, no network)."""
import unittest

from research import real_context_bench_v03 as v03


def blk(m, kind, content, role='user'):
    return dict(m=m, role=role, kind=kind, tool_name=None, tool_use_id=None, is_error=False, content=content)


class V03Tests(unittest.TestCase):
    def test_audit_select_caps_per_item_and_is_seeded(self):
        per_item = {'big': [f'b{i}' for i in range(40)], 'mid': [f'm{i}' for i in range(5)], 'one': ['o0']}
        picked = v03.audit_select(per_item, seed=1, n=10, cap=6)
        self.assertEqual(len(picked), 10)
        self.assertEqual(len(set(picked)), 10)
        self.assertLessEqual(sum(r == 'big' for r, _ in picked), 6)
        self.assertEqual(picked, v03.audit_select(per_item, seed=1, n=10, cap=6))
        self.assertEqual(len(v03.audit_select(per_item, seed=1, n=100, cap=6)), 12)  # 6 + 5 + 1

    def test_clip_keeps_head_and_tail_within_budget(self):
        s = 'H' * 50 + 'x' * 1000 + 'T' * 50
        c = v03.clip(s, 100)
        self.assertTrue(c.startswith('H' * 50) and c.endswith('T' * 50))
        self.assertIn('1000 chars omitted', c)
        self.assertEqual(v03.clip('short', 100), 'short')

    def test_last_turns_groups_by_record_and_skips_tool_blocks(self):
        blocks = [blk(0, 'text', 'first'), blk(1, 'text', 'a1', 'assistant'), blk(1, 'text', 'a2', 'assistant'),
                  blk(2, 'tool_result', 'out'), blk(3, 'text', 'u2'), blk(4, 'text', 'last', 'assistant')]
        turns = v03.last_turns(blocks)
        self.assertEqual([t['text'] for t in turns], ['a1\na2', 'u2', 'last'])


if __name__ == '__main__':
    unittest.main()
