import csv
import json
from pathlib import Path
import tempfile
import unittest

try:
    from research.review_packet import COLUMNS, build, import_result, review, score
except ModuleNotFoundError:
    COLUMNS = build = import_result = review = score = None

SPLITS = ('train', 'validation', 'calibration', 'confirmation')


def read(path):
    with open(path, newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))


def write(path, rows):
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows)


class ReviewPacketTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if build is None:
            return
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.tmp.name) / 'a'
        cls.receipt = build(cls.out)
        cls.rows = read(cls.out / 'packet.csv')
        cls.key = json.loads((cls.out / 'key.json').read_text())

    @classmethod
    def tearDownClass(cls):
        if build is not None:
            cls.tmp.cleanup()

    def setUp(self):
        self.assertIsNotNone(build, 'research/review_packet.py is absent')

    def test_build_is_deterministic_and_seed_sensitive(self):
        again = Path(self.tmp.name) / 'b'
        build(again)
        for name in ('packet.csv', 'key.json'):
            self.assertEqual((self.out / name).read_bytes(), (again / name).read_bytes(), name)
        other = Path(self.tmp.name) / 'c'
        build(other, seed=self.receipt['seed'] + 1)
        self.assertNotEqual((self.out / 'packet.csv').read_bytes(), (other / 'packet.csv').read_bytes())

    def test_stratification_counts_and_shortfall(self):
        strata = self.receipt['strata']
        self.assertEqual(len(strata), 16)
        present = {k: v for k, v in strata.items() if v['available']}
        self.assertEqual(set(present), {f'{lang}|{group}|authored' for lang in ('en', 'pt')
                                        for group in ('supported', 'unknown')})
        for k, v in strata.items():
            self.assertEqual(v['sampled'], 15 if v['available'] else 0, k)
            self.assertEqual(v['shortfall'], 15 - v['sampled'], k)
        self.assertEqual(len(self.rows), 60)
        self.assertEqual(self.receipt['shortfall'], 180)
        self.assertEqual(set(self.receipt['missing_groups']), {'contrast', 'ambiguity'})
        from collections import Counter
        self.assertEqual(Counter(v['stratum'] for v in self.key['items'].values()),
                         Counter({k: 15 for k in present}))
        supported = [r for r in self.rows if not r['proposed_label'].startswith('UNKNOWN')]
        self.assertEqual(len({r['proposed_label'] for r in supported}), 8)  # round-robin covers all fields

    def test_packet_is_blind_to_split_sources_and_models(self):
        with open(self.out / 'packet.csv', newline='', encoding='utf-8') as f:
            self.assertEqual(next(csv.reader(f)), COLUMNS)
        secrets = {s for item in self.key['items'].values() for s in item['source_ids']}
        for row in self.rows:
            self.assertEqual((row['verdict'], row['corrected_label'], row['note']), ('', '', ''))
            for column, value in row.items():
                if column != 'question':
                    self.assertNotIn(value.lower(), SPLITS)
                    self.assertFalse(any(s in value for s in secrets), column)
                self.assertNotIn('score', column)
        self.assertEqual(set(self.key['items']), {r['item_id'] for r in self.rows})

    def test_score_math_and_pass_rule(self):
        tmp = Path(self.tmp.name)
        rows = [dict(r, verdict='agree') for r in self.rows]
        write(tmp / 'all.csv', rows)
        result = score(tmp / 'all.csv', self.out / 'key.json')
        self.assertEqual((result['agreement'], result['gate_pass'], result['plan_complete']), (1.0, True, False))
        stratum = 'en|supported|authored'
        hits = [r for r in rows if self.key['items'][r['item_id']]['stratum'] == stratum][:2]
        hits[0].update(verdict='disagree', corrected_label='retry_failures')
        hits[1].update(verdict='ambiguous')
        write(tmp / 'two.csv', rows)
        result = score(tmp / 'two.csv', self.out / 'key.json')
        self.assertAlmostEqual(result['agreement'], 58 / 60)
        self.assertAlmostEqual(result['strata'][stratum]['agreement'], 13 / 15)
        self.assertEqual(result['strata'][stratum]['disagree'], 1)
        self.assertFalse(result['gate_pass'])  # .9667 overall passes, .8667 stratum fails

    def test_build_refuses_to_overwrite_filled_packet(self):
        out = Path(self.tmp.name) / 'filled'
        build(out)
        build(out)  # blank packet: rebuilding is harmless
        rows = read(out / 'packet.csv')
        rows[0]['note'] = 'reviewer work'
        write(out / 'packet.csv', rows)
        before = (out / 'packet.csv').read_bytes()
        with self.assertRaises(FileExistsError):
            build(out)
        self.assertEqual((out / 'packet.csv').read_bytes(), before)
        build(out, force=True)
        self.assertEqual(read(out / 'packet.csv')[0]['note'], '')

    def test_score_rejects_invalid_packets(self):
        tmp = Path(self.tmp.name)
        good = [dict(r, verdict='agree') for r in self.rows]
        bad_cases = {
            'verdict': [dict(good[0], verdict='yes')] + good[1:],
            'blank': [dict(good[0], verdict='')] + good[1:],
            'bad_correction': [dict(good[0], verdict='disagree', corrected_label='retry_nonsense')] + good[1:],
            'missing': good[1:],
            'duplicate': good + good[:1],
            'tampered': [dict(good[0], question=good[0]['question'] + '?')] + good[1:],
        }
        for name, rows in bad_cases.items():
            with self.subTest(name=name), self.assertRaises(ValueError):
                write(tmp / f'{name}.csv', rows)
                score(tmp / f'{name}.csv', self.out / 'key.json')

    def test_disagree_without_correction_counts_as_uncorrected(self):
        tmp = Path(self.tmp.name)
        rows = [dict(r, verdict='agree') for r in self.rows]
        write(tmp / 'uncorrected.csv', [dict(rows[0], verdict='disagree')] + rows[1:])
        result = score(tmp / 'uncorrected.csv', self.out / 'key.json')
        self.assertEqual((result['agree'], result['uncorrected_disagreements']), (len(rows) - 1, 1))


if __name__ == '__main__':
    unittest.main()


class InteractiveReviewTests(unittest.TestCase):
    def test_review_fills_resumes_and_scores(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            build(out)
            n = len(read(out / 'packet.csv'))
            # first session: disagree on row 1 (label 1), agree on row 2, then quit
            answers = iter(['d', '1', 'nota', 'a', '', 'q'])
            review(out / 'packet.csv', ask=lambda _: next(answers), say=lambda _: None)
            rows = read(out / 'packet.csv')
            self.assertEqual([r['verdict'] for r in rows[:3]], ['disagree', 'agree', ''])
            self.assertTrue(rows[0]['corrected_label'])
            self.assertEqual(rows[0]['note'], 'nota')
            # resume: agree on everything left, then score accepts the packet
            answers = iter(['a', ''] * n)
            review(out / 'packet.csv', ask=lambda _: next(answers), say=lambda _: None)
            result = score(out / 'packet.csv', out / 'key.json')
            self.assertEqual((result['n'], result['agree']), (n, n - 1))


class PageResultImportTests(unittest.TestCase):
    def test_downloaded_result_imports_and_scores(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            build(out, languages=('pt',), quota=30)
            rows = read(out / 'packet.csv')
            self.assertTrue(rows and all(r['language'] == 'pt' for r in rows))
            self.assertFalse(any('Read ' in r['registry_definition'] for r in rows))
            # same CSV shape the page downloads: quoted fields, one disagree, one unclear with a quote in the note
            lines = ['item_id,verdict,corrected_label,note']
            for n, r in enumerate(rows):
                verdict, corrected, note = ('disagree', 'UNKNOWN:other', '') if n == 0 else (
                    ('unclear', '', 'texto "estranho"') if n == 1 else ('agree', '', ''))
                lines.append(','.join('"%s"' % v.replace('"', '""') for v in (r['item_id'], verdict, corrected, note)))
            (out / 'review-result.csv').write_text('\n'.join(lines))
            import_result(out / 'review-result.csv', out / 'packet.csv')
            self.assertEqual(read(out / 'packet.csv')[1]['note'], 'texto "estranho"')
            result = score(out / 'packet.csv', out / 'key.json')
            self.assertEqual((result['n'], result['agree'], result['unclear']), (len(rows), len(rows) - 2, 1))
