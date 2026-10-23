import tempfile
import unittest
from pathlib import Path

from research.intake_judge import Judge, export, features
from research.intake_v1 import fit, macro_f1


class IntakeV1Tests(unittest.TestCase):
    def test_fit_export_load_roundtrip_separates_classes(self):
        cats = ['approve_or_pick', 'failure_report', 'git_ship']
        texts = ['sim', 'pode seguir', 'continua', 'ok vai',
                 'deu erro no build', 'falhou o deploy de novo', 'traceback no teste', 'erro 500 na api',
                 'faz o commit', 'push na main', 'abre o pr', 'commit e push']
        y = [cats[0]] * 4 + [cats[1]] * 4 + [cats[2]] * 4
        W, b = fit(texts, y, cats, 'char+word', 3.0, iters=200)
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'm.json'
            export(path, cats, 'char+word', W, b)
            j = Judge.load(path)
        self.assertEqual([j.predict(t)[0] for t in texts], y)
        self.assertAlmostEqual(sum(j.proba('qualquer coisa')), 1.0, places=6)

    def test_features_are_normalised_and_deterministic(self):
        f = features('Fix the BUG', 'char+word')
        self.assertEqual(f, features('fix the bug', 'char+word'))
        self.assertAlmostEqual(sum(v * v for v in f.values()), 1.0)
        self.assertTrue(features('', 'char'))

    def test_macro_f1_over_gold_classes(self):
        self.assertEqual(macro_f1(['a', 'a', 'b'], ['a', 'a', 'b']), 1.0)
        self.assertAlmostEqual(macro_f1(['a', 'b'], ['a', 'a']), (2 / 3 + 0) / 2)


if __name__ == '__main__':
    unittest.main()
