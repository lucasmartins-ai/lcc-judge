"""Held-out v3 session filter on synthetic session tables (no transcript store is read)."""
import unittest

from research import heldout_v3 as h

CUT = '2026-10-13T00:00:00.000Z'


class Qualifying(unittest.TestCase):
    def test_rules(self):
        sessions = {
            'new': dict(first='2026-10-14T09:00:00.000Z', n=3, files={'/p/new.jsonl'}),
            'early': dict(first='2026-10-12T23:59:59.000Z', n=5, files=set()),
            'old_sid': dict(first='2026-10-15T00:00:00.000Z', n=4, files=set()),
            'old_file': dict(first='2026-10-15T00:00:00.000Z', n=4, files={'/p/resumed.jsonl'}),
            'child': dict(first='2026-10-15T00:00:00.000Z', n=4, parent='p0'),
            'single': dict(first='2026-10-15T00:00:00.000Z', n=1, files=set()),
            'nots': dict(first=None, n=4, files=set()),
        }
        old = {'claude:old_sid': 'g', 'claude:file:/p/resumed.jsonl': 'g', 'claude:p0': 'g'}
        ok, why = h.qualifying('claude', sessions, old, CUT)
        self.assertEqual(ok, {'new'})
        self.assertEqual(dict(why), {'started_before_cutoff': 2, 'in_old_lineage': 2, 'parent_in_old_lineage': 1,
                                     'fewer_than_2_prompts': 1})

    def test_day_before(self):
        self.assertEqual(h._day_before('2026-10-01'), '2026-09-30')


if __name__ == '__main__':
    unittest.main()
