import json
from pathlib import Path
import tempfile
import unittest

from research.request_taxonomy_review import pick, page, score


def fixture(root):
    cats = [dict(id=c, name_pt=c.upper(), definition_pt='def') for c in ('a', 'b')]
    (root / 'taxonomy.json').write_text(json.dumps(dict(categories=cats)))
    goals, labels = [], []
    for n in range(12):
        goals.append(dict(id=f'r{n}', goal=f'pedido </script> {n}'))
        labels.append(dict(id=f'r{n}', label=('a', 'b', 'UNKNOWN')[n % 3],
                           confidence=('high', 'low', 'medium')[n % 3]))
    (root / 'chunk-0.jsonl').write_text('\n'.join(map(json.dumps, goals)))
    (root / 'labels-0.jsonl').write_text('\n'.join(map(json.dumps, labels)))
    return labels


class RequestTaxonomyReviewTests(unittest.TestCase):
    def test_pick_is_deterministic_balanced_and_low_confidence_first(self):
        labels = {x['id']: x for x in fixture(Path(tempfile.mkdtemp()))}
        a, b = pick(labels, per_category=2), pick(labels, per_category=2)
        self.assertEqual([x['id'] for x in a], [x['id'] for x in b])
        self.assertEqual(sorted(x['label'] for x in a), ['UNKNOWN', 'UNKNOWN', 'a', 'a', 'b', 'b'])

    def test_page_escapes_script_and_score_counts(self):
        root = Path(tempfile.mkdtemp())
        fixture(root)
        body = page(root).read_text()
        self.assertNotIn('pedido </script>', body)
        (root / 'r.csv').write_text('id,verdict,corrected\n"r0","right",""\n"r1","wrong","a"\n"r2","unsure",""\n')
        result = score(root / 'r.csv', root)
        self.assertEqual((result['judged'], result['right'], result['unsure']), (2, 1, 1))
        self.assertEqual(result['corrections'], {'b -> a': 1})
        (root / 'bad.csv').write_text('id,verdict,corrected\n"r0","yes",""\n')
        with self.assertRaises(ValueError):
            score(root / 'bad.csv', root)
