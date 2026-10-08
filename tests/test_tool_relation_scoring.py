import json
import math
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest import mock

import torch

from research.tool_relation_support_study import score_population


def cohort():
    from hashlib import sha256
    rows,views=[],[]
    for index in range(2):
        question,report='Direct counter request','Counter report: 4.'
        identity=str(index)
        key=sha256(json.dumps([question,report],sort_keys=True).encode()).hexdigest()
        rows.append(dict(id=identity,content_hash='original'+identity,projected_input_hash=key,label=index))
        views.append(dict(id=identity,projected_tokens=4,
            view=dict(status='PROJECTED',objective=question,text=report)))
    return rows,views


class Tokenizer:
    def __call__(self,questions,reports,**kwargs):
        assert kwargs['truncation'] is False
        return dict(input_ids=torch.ones((len(questions),4),dtype=torch.long),
                    attention_mask=torch.ones((len(questions),4),dtype=torch.long))


class ToolRelationScoringTests(unittest.TestCase):
    def test_mismatched_receipts_cannot_reach_the_model(self):
        rows,views=cohort();views[0]['id']='wrong'
        model=mock.Mock()
        scorer=SimpleNamespace(model=model,tokenizer=Tokenizer(),window=512)
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                score_population(scorer,rows,views,dict(sha256='protocol',batch_size=1),Path(directory)/'scores.json')
        model.assert_not_called()

    def test_partial_forward_receipts_survive_a_later_failure(self):
        rows,views=cohort()
        model=mock.Mock(side_effect=[SimpleNamespace(logits=torch.tensor([[0.,2.,-3.]])),RuntimeError('simulated forward failure')])
        scorer=SimpleNamespace(model=model,tokenizer=Tokenizer(),window=512)
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'scores.json'
            with self.assertRaises(RuntimeError):
                score_population(scorer,rows,views,dict(sha256='protocol',batch_size=1),path)
            saved=json.loads(path.read_text())
            self.assertEqual(saved['rows'][0]['status'],'SCORED')
            self.assertEqual(saved['rows'][1]['status'],'UNKNOWN')
            self.assertEqual(saved['accounting']['submitted_pairs'],2)
            self.assertEqual(saved['accounting']['forward_completed_pairs'],1)
            self.assertEqual(saved['accounting']['valid_score_pairs'],1)
            self.assertFalse(saved['complete'])
            self.assertEqual(model.call_count,2)

    def test_score_axes_are_exactly_recoverable_from_saved_float_logits(self):
        rows,views=cohort()
        logits=torch.tensor([[-9.11,7.03,1.2],[3.4,1.2,-2.]])
        scorer=SimpleNamespace(model=mock.Mock(return_value=SimpleNamespace(logits=logits)),tokenizer=Tokenizer(),window=512)
        with tempfile.TemporaryDirectory() as directory:
            raw=score_population(scorer,rows,views,dict(sha256='protocol',batch_size=2),Path(directory)/'scores.json')
        for score in raw['rows']:
            values=score['logits'];largest=max(values[:2])
            self.assertEqual(score['score'],values[1]-values[0])
            self.assertEqual(score['support_score'],values[2]-largest-math.log(sum(math.exp(v-largest) for v in values[:2])))


if __name__=='__main__':unittest.main()
