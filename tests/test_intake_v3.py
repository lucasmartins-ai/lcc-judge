import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from research import intake_v3
from research.intake_v3 import GeminiRefused, voted_views


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

    def test_refused_batch_is_retried_in_halves(self):
        def fake(batch):  # refuses any batch holding "a"
            if any(r['id'] == 'a' for r in batch):
                raise GeminiRefused('filtered')
            return {r['id']: 'x' for r in batch}

        with patch.object(intake_v3, '_gemini_vote', side_effect=fake) as vote:
            got = intake_v3._gemini_vote_halves([{'id': c} for c in 'abcd'])
        self.assertEqual(got, {'a': None, 'b': None, 'c': 'x', 'd': 'x'})
        self.assertEqual(vote.call_count, 3)
        with patch.object(intake_v3, '_gemini_vote', side_effect=fake):
            self.assertEqual(intake_v3._gemini_vote_halves([{'id': 'a'}]), {'a': None})


if __name__ == '__main__':
    unittest.main()
