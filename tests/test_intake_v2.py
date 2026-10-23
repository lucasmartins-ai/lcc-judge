import math
import tempfile
import unittest
from pathlib import Path

from research.intake_judge_v2 import P, Q, WIDTH, Judge, export, family_rows, vector
from research.intake_v2 import _threshold, fit_vectors


class IntakeV2Tests(unittest.TestCase):
    def test_blocks_live_in_their_own_ranges_and_are_normalised(self):
        v = vector('sim', 'Quer que eu faça o commit?', 'B')
        prompt = {k: x for k, x in v.items() if k < P}
        prev = {k: x for k, x in v.items() if P <= k < P + Q}
        self.assertEqual(len(prompt) + len(prev), len(v))
        for block in (prompt, prev):
            self.assertAlmostEqual(math.sqrt(sum(x * x for x in block.values())), 1.0)
        self.assertEqual(vector('sim', None, 'B'), vector('sim', None, 'A'))

    def test_previous_turn_changes_the_prediction_after_training(self):
        cats = ['approve_or_pick', 'git_ship']
        items = [('sim', 'Quer que eu siga com a opção 2?', 'approve_or_pick'),
                 ('sim', 'Posso seguir com o plano?', 'approve_or_pick'),
                 ('sim', 'Quer que eu faça o commit e o push?', 'git_ship'),
                 ('sim', 'Faço o commit agora?', 'git_ship')]
        W, b = fit_vectors([vector(p, q, 'B') for p, q, _ in items], [c for *_, c in items], cats, 10.0, iters=300)
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'm.json'
            export(path, cats, 'B', W, b)
            j = Judge.load(path)
        self.assertEqual([j.predict(p, q)[0] for p, q, _ in items], [c for *_, c in items])

    def test_family_rows_cover_width_for_hybrid(self):
        self.assertEqual(len(family_rows('H')), WIDTH)
        self.assertEqual(len(family_rows('A')), P)

    def test_threshold_is_lowest_cut_reaching_point_eight(self):
        pairs = [(0.9, True)] * 8 + [(0.3, False)] * 8 + [(0.5, True)] * 2
        self.assertEqual(_threshold(pairs)[0], 0.35)


if __name__ == '__main__':
    unittest.main()
