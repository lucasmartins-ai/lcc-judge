import unittest


class HFFrontierTests(unittest.TestCase):
    def test_common_prefix_preserves_whole_evidence_under_pair_budget(self):
        from research.hf_frontier import fit_prefix
        class Tokenizer:
            def __call__(self, objective, text, **kwargs):
                return {'input_ids': list(range(len(objective)+len(text)+3))}
        prefix = fit_prefix(Tokenizer(), 'goal', ['FACT END', 'HEALTHY END', 'OTHER END'],
                            ['line number one', 'another whole line']*20, 90)
        self.assertTrue(prefix.endswith('\n'))
        for middle in ['FACT END', 'HEALTHY END', 'OTHER END']:
            self.assertLessEqual(len(Tokenizer()('goal', prefix+middle)['input_ids']), 90)
            self.assertTrue((prefix+middle).endswith(middle))
        self.assertIn('line number one\n', prefix)


if __name__ == '__main__': unittest.main()
