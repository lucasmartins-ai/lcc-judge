"""v5c2 harness on synthetic blocks only (no private data, no lcc, no model files)."""
import unittest

from research import v5c2


def blk(src, kind='text', is_error=False):
    return dict(src=list(src), kind=kind, is_error=is_error)


class Rebuild(unittest.TestCase):
    def test_rebuild_and_pairing(self):
        texts = ['[m0000 user text]\nfix it', '[m0001 assistant tool_use Read]\n{"file_path": "a.py"}',
                 '[m0002 user tool_result Read]\nline 1', 'line 2 after a blank line',
                 'tail of a fence\n\n[m0003 assistant text]\ndone']
        blocks = [blk((0, 0)), blk((1, 1), 'tool_use'), blk((2, 2), 'tool_result'), blk((2, 2), 'tool_result'),
                  blk((2, 3), 'tool_result')]
        dos = v5c2.rebuild(blocks, texts)
        self.assertEqual([d['kind'] for d in dos], ['text', 'tool_use', 'tool_result', 'text'])
        self.assertEqual(dos[2]['content'], 'line 1\n\nline 2 after a blank line\n\ntail of a fence')
        self.assertEqual(dos[2]['parts'], [2, 3, 4])
        self.assertEqual(dos[3]['parts'], [4])
        pl, res_of, orphans = v5c2.payload(dos)
        self.assertEqual(res_of, {2: 'c1'})
        self.assertEqual(pl[1]['toolUses'][0]['input'], {'file_path': 'a.py'})
        self.assertEqual(orphans, [])

    def test_rebuild_refuses_a_bad_map(self):
        with self.assertRaises(v5c2.Rebuild):
            v5c2.rebuild([blk((0, 1))], ['[m0000 user text]\nno inner header'])


class Budget(unittest.TestCase):
    def test_drop_set_and_cache_tie(self):
        pool = [('a', 10, 0), ('b', 10, 5), ('c', 10, 9)]
        sc = {'a': 1.0, 'b': 1.1, 'c': 5.0}
        self.assertEqual(v5c2.drop_set(pool, sc, 10), {'a'})
        self.assertEqual(v5c2.drop_set(pool, sc, 10, cache_tie=True), {'b'})  # same 0.5 bucket: later first
        self.assertEqual(v5c2.drop_set(pool, sc, 11), {'a', 'b'})

    def test_item_metrics_cache_cost(self):
        f = frozenset
        it = dict(blocks=[(100, False, False, False, f()), (50, True, True, True, f({'r1'})),
                          (30, True, False, False, f({'r2'})), (20, False, False, False, f())])
        m = v5c2.item_metrics(it, {'r2'}, note_tokens=10)
        self.assertEqual((m['recall'], m['all_kept'], m['first_mutation_offset'], m['invalidated_tokens']),
                         (1.0, True, 150, 50))
        self.assertEqual(m['break_even_reuses'], round(50 * 1.15 / (20 * 0.10), 2))
        m = v5c2.item_metrics(it, {'r1'}, note_tokens=10)
        self.assertEqual((m['recall'], m['all_kept'], m['used_results_stashed']), (0.0, False, 1))


if __name__ == '__main__':
    unittest.main()
