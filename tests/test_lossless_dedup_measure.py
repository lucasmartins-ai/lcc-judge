"""Stdlib-only tests for the independent lossless check in research/lossless_dedup_measure.py (no lcc)."""
import unittest

from research import lossless_dedup_measure as m
from research import real_context_bench as rcb


def blk(mi, kind, content, tid, err=False, role='user'):
    return dict(m=mi, role=role, kind=kind, tool_name='Bash', tool_use_id=tid, is_error=err, content=content)


HDR = 'Chunk ID: {}\nWall time: {} s\nProcess exited with code 0\nOriginal token count: 9\nOutput:\nline a\nline b'


class IndependentCheckTests(unittest.TestCase):
    def setUp(self):
        self.blocks = [blk(0, 'tool_use', '{"command": "x"}', 'a', role='assistant'),
                       blk(1, 'tool_result', HDR.format('aa', 1), 'a'),
                       blk(2, 'tool_use', '{"command": "x"}', 'b', role='assistant'),
                       blk(3, 'tool_result', HDR.format('bb', 2) + '\nline c', 'b')]

    def out(self, note):
        return rcb.render([dict(b, content=note) if b['kind'] == 'tool_result' and b['tool_use_id'] == 'a' else b
                           for b in self.blocks])

    def test_identical_rerun_with_volatile_header_passes(self):
        self.blocks[3]['content'] = HDR.format('bb', 2)
        dec = [dict(id='a', decision='dedupe', kept_at='b', note='[identical output kept at b]')]
        self.assertEqual(m.independent_check(self.blocks, dec, self.out(dec[0]['note'])), [])

    def test_line_range_pointer_must_name_the_exact_lines(self):
        self.blocks[1]['content'] = 'line a\nline b'
        ok = '[output = lines 6-7 of b]'
        dec = [dict(id='a', decision='dedupe', kept_at='b', note=ok)]
        self.assertEqual(m.independent_check(self.blocks, dec, self.out(ok)), [])
        # wrong range, a range-less note, or a false "identical" claim are all violations
        for bad in ('[output = lines 7-8 of b]', '[output contained in b]', '[identical output kept at b]'):
            dec = [dict(id='a', decision='dedupe', kept_at='b', note=bad)]
            self.assertTrue(m.independent_check(self.blocks, dec, self.out(bad)), bad)

    def test_header_contained_only_after_normalisation_is_not_a_line_range(self):
        dec = [dict(id='a', decision='dedupe', kept_at='b', note='[output = lines 1-7 of b]')]
        self.assertTrue(m.independent_check(self.blocks, dec, self.out(dec[0]['note'])))

    def test_exit_code_and_body_text_are_compared(self):
        self.blocks[3]['content'] = self.blocks[3]['content'].replace('code 0', 'code 1')
        dec = [dict(id='a', decision='dedupe', kept_at='b', note='[identical output kept at b]')]
        self.assertTrue(m.independent_check(self.blocks, dec, self.out('[x]')))
        self.blocks[3]['content'] = HDR.format('bb', 2).replace('line b', 'line B')
        self.assertTrue(m.independent_check(self.blocks, dec, self.out('[x]')))

    def test_target_replaced_or_error_flag_differs(self):
        dec = [dict(id='a', decision='dedupe', kept_at='b'), dict(id='b', decision='dedupe', kept_at='a')]
        self.assertTrue(m.independent_check(self.blocks, dec, self.out('[x]')))
        self.blocks[3]['is_error'] = True
        self.assertTrue(m.independent_check(self.blocks, dec[:1], self.out('[x]')))

    def test_mid_line_match_does_not_count(self):
        self.blocks[1]['content'], self.blocks[3]['content'] = 'ok', 'not ok'
        dec = [dict(id='a', decision='dedupe', kept_at='b', note='[identical output kept at b]')]
        self.assertTrue(m.independent_check(self.blocks, dec, self.out('[x]')))


if __name__ == '__main__':
    unittest.main()
