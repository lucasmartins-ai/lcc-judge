import copy
import unittest
from unittest import mock

import torch
from transformers import BertConfig,BertForSequenceClassification,XLMRobertaConfig,XLMRobertaForSequenceClassification

from research.ranking_support_initialization import retain_ranking_prior


class RankingSupportInitializationTests(unittest.TestCase):
    def check_margin(self,model):
        model.eval();ids=torch.tensor([[0,4,5,2],[0,7,8,2]])
        arguments=dict(input_ids=ids,attention_mask=torch.ones_like(ids))
        with torch.inference_mode():original=model(**arguments).logits[:,0].clone()
        parameters={name:p.detach().clone() for name,p in model.named_parameters()}
        dense=model.classifier.dense if model.config.model_type=='xlm-roberta' else None
        receipt=retain_ranking_prior(model,101)
        self.assertEqual(receipt['classes'],['IRRELEVANT','RELEVANT','UNKNOWN'])
        self.assertEqual(model.config.num_labels,3)
        self.assertEqual(model.num_labels,3)
        if dense is not None:self.assertIs(model.classifier.dense,dense)
        with torch.inference_mode():expanded=model(**arguments).logits
        torch.testing.assert_close(expanded[:,1]-expanded[:,0],original,atol=1e-6,rtol=1e-6)
        for name,p in model.named_parameters():
            if not (name.startswith('classifier.') and ('out_proj.' in name or dense is None)):
                torch.testing.assert_close(p,parameters[name],atol=0,rtol=0)
        return receipt

    def test_xlm_classifier_dense_and_scalar_ordering_survive_expansion(self):
        config=XLMRobertaConfig(vocab_size=30,hidden_size=16,intermediate_size=32,
                                num_attention_heads=2,num_hidden_layers=1,max_position_embeddings=16,num_labels=1)
        self.check_margin(XLMRobertaForSequenceClassification(config))

    def test_bert_ranking_head_is_encoded_as_a_margin_not_discarded(self):
        config=BertConfig(vocab_size=30,hidden_size=16,intermediate_size=32,
                          num_attention_heads=2,num_hidden_layers=1,max_position_embeddings=16,num_labels=1)
        model=BertForSequenceClassification(config)
        second=copy.deepcopy(model)
        state=torch.random.get_rng_state().clone()
        first=self.check_margin(model)
        # check_margin has no dropout and initialization restores RNG state.
        torch.testing.assert_close(torch.random.get_rng_state(),state,atol=0,rtol=0)
        same=retain_ranking_prior(second,101)
        self.assertEqual(first['initial_output_head_sha256'],same['initial_output_head_sha256'])

    def test_non_scalar_input_is_rejected_before_model_mutation(self):
        model=BertForSequenceClassification(BertConfig(vocab_size=30,hidden_size=16,intermediate_size=32,
            num_attention_heads=2,num_hidden_layers=1,max_position_embeddings=16,num_labels=2))
        original=model.classifier
        with self.assertRaises(ValueError):retain_ranking_prior(model,101)
        self.assertIs(model.classifier,original)
        self.assertEqual(model.config.num_labels,2)

    def test_cpu_initialization_does_not_seed_other_device_generators(self):
        model=BertForSequenceClassification(BertConfig(vocab_size=30,hidden_size=16,intermediate_size=32,
            num_attention_heads=2,num_hidden_layers=1,max_position_embeddings=16,num_labels=1))
        # torch.manual_seed also changes accelerator RNGs, even for a CPU model.
        # A local CPU generator must supply UNKNOWN initialization instead.
        with mock.patch('torch.manual_seed',side_effect=AssertionError('global device RNG was reseeded')):
            retain_ranking_prior(model,101)


if __name__=='__main__':
    unittest.main()
