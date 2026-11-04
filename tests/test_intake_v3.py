import tempfile
import unittest
from pathlib import Path

from research.intake_v3 import voted_views


class IntakeV3Tests(unittest.TestCase):
    def test_voted_views(self):
        votes = {'claude': {'a': 'x', 'b': 'y', 'c': 'z', 'd': None},
                 'codex': {'a': 'x', 'b': 'y', 'c': 'w', 'd': None},
                 'gemini': {'a': 'x', 'b': 'q', 'c': 'w', 'd': None}}
        rows = 'id,blind,final\n"a","x","x"\n"b","q","y"\n"c","z","z"\n"d","unsure","x"\n"e","",""\n'
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'g.csv'
            path.write_text(rows, encoding='utf-8')
            v = voted_views(path, votes)
        self.assertEqual(v['final'], {'a': 'x', 'b': 'y', 'c': 'z', 'd': 'x'})
        self.assertEqual(v['blind'], {'a': 'x', 'b': 'q', 'c': 'z'})
        # codex + gemini + owner-blind; "c" splits w/w/z -> w; no label from missing votes
        self.assertEqual(v['codex_gemini_owner_blind_majority'], {'a': 'x', 'b': 'q', 'c': 'w'})
        self.assertEqual(v['all_three_models_agree'], {'a': 'x'})


if __name__ == '__main__':
    unittest.main()
