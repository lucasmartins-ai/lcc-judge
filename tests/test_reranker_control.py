import hashlib
import json
from types import SimpleNamespace
import unittest

import torch

from research.reranker_control import PairReranker


class Tokenizer:
    def __call__(self, objective, text, **kwargs):
        if isinstance(text,str):
            return {'input_ids':[1]+list(range(1,len(text.split())+1))+[2]}
        sequences=[self(q,t)['input_ids'] for q,t in zip(objective,text)]
        width=max(map(len,sequences));ids=torch.zeros(len(sequences),width,dtype=torch.long)
        masks=torch.zeros_like(ids)
        for i,seq in enumerate(sequences):
            ids[i,:len(seq)]=torch.tensor(seq);masks[i,:len(seq)]=1
        return dict(input_ids=ids,attention_mask=masks)


class Model(torch.nn.Module):
    def __init__(self, invalid=False):
        super().__init__();self.config=SimpleNamespace(max_position_embeddings=8,num_labels=1)
        self.calls=0;self.invalid=invalid

    def forward(self,input_ids,attention_mask):
        self.calls+=1
        values=attention_mask.sum(1).float() if not self.invalid else torch.full((len(input_ids),),float('nan'))
        return SimpleNamespace(logits=values[:,None])


class RerankerControlTests(unittest.TestCase):
    def test_roberta_padding_positions_do_not_inflate_pair_window(self):
        from transformers import XLMRobertaConfig, XLMRobertaForSequenceClassification
        model = XLMRobertaForSequenceClassification(XLMRobertaConfig(
            vocab_size=16, hidden_size=8, num_hidden_layers=1, num_attention_heads=2,
            intermediate_size=16, max_position_embeddings=8, pad_token_id=1, num_labels=1))
        # Non-padding positions begin after pad index1. Seven tokens require
        # index8, which cannot fit in an eight-row position embedding table.
        with self.assertRaises((IndexError, RuntimeError)):
            model(input_ids=torch.tensor([[0,4,4,4,4,4,2]]), attention_mask=torch.ones((1,7),dtype=torch.long))
        tokenizer = Tokenizer()
        tokenizer.model_max_length = 6
        scorer = PairReranker(model, tokenizer)
        self.assertEqual(scorer.window, 6)
        calls = []
        model.register_forward_pre_hook(lambda *args: calls.append('called'))
        oversized = scorer.score(['q'], ['one two three four five'])[0]
        self.assertEqual(oversized['error'], 'input_exceeds_window')
        self.assertFalse(oversized['submitted'])
        self.assertEqual(calls, [])
        with self.assertRaises(ValueError):
            PairReranker(model, tokenizer, max_pair_tokens=7)

    def test_loader_metadata_is_strict_json_without_losing_key_names(self):
        from research.reranker_control import loading_info_for_json
        info={'missing_keys':set(), 'unexpected_keys':{'z.buffer','a.buffer'},
              'mismatched_keys':[], 'error_msgs':[]}
        encoded=json.dumps(loading_info_for_json(info),allow_nan=False)
        self.assertEqual(json.loads(encoded)['unexpected_keys'],['a.buffer','z.buffer'])
        self.assertEqual(json.loads(encoded)['missing_keys'],[])
        self.assertIsInstance(info['unexpected_keys'],set)

    def test_raw_logit_and_order_preserved_without_clipping(self):
        model=Model();scorer=PairReranker(model,Tokenizer(),max_pair_tokens=5,batch_size=2)
        results=scorer.score(['q','q','q'],['two words','too many words here again','one'])
        self.assertEqual([r['score'] for r in results],[4.,None,3.])
        self.assertEqual(model.calls,1)
        self.assertFalse(results[1]['submitted'])
        self.assertEqual(scorer.accounting['submitted_tokens'],7)
        self.assertEqual(scorer.accounting['counted_tokens'],14)
        self.assertEqual(results[0]['input_sha256'],hashlib.sha256(json.dumps(['q','two words'],sort_keys=True).encode()).hexdigest())

    def test_oversized_input_never_reaches_model(self):
        model=Model();scorer=PairReranker(model,Tokenizer(),max_pair_tokens=3)
        item=scorer.score(['q'],['two words'])[0]
        self.assertIsNone(item['score']);self.assertEqual(item['error'],'input_exceeds_window')
        self.assertEqual(model.calls,0);self.assertEqual(scorer.accounting['submitted_tokens'],0)

    def test_nonfinite_score_retains_submitted_accounting(self):
        scorer=PairReranker(Model(invalid=True),Tokenizer())
        item=scorer.score(['q'],['one'])[0]
        self.assertIsNone(item['score']);self.assertEqual(item['error'],'nonfinite_score')
        self.assertTrue(item['submitted']);self.assertTrue(item['forward_completed'])
        self.assertEqual(scorer.accounting['submitted_tokens'],3)
        self.assertEqual(scorer.accounting['valid_score_tokens'],0)

    def test_configuration_limits_are_not_silently_capped(self):
        for value in [0,True,9]:
            with self.assertRaises(ValueError):PairReranker(Model(),Tokenizer(),max_pair_tokens=value)


if __name__=='__main__':unittest.main()
