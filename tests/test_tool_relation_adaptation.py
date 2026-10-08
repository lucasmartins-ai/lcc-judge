import unittest

import torch
from transformers import XLMRobertaConfig,XLMRobertaForSequenceClassification

from research.tool_relation_adaptation import configure_adaptation,frozen_parameter_sha256
from research.tool_role_training import classification_loss
from specialist.numerical import finite_update


def model():
    return XLMRobertaForSequenceClassification(XLMRobertaConfig(vocab_size=30,hidden_size=16,
        intermediate_size=32,num_attention_heads=2,num_hidden_layers=3,max_position_embeddings=16,num_labels=1))


class ToolRelationAdaptationTests(unittest.TestCase):
    def test_actual_xlm_tail_and_classifier_only_receive_finite_updates(self):
        candidate=model()
        receipt=configure_adaptation(candidate,101,last_n=2)
        names={name for name,p in candidate.named_parameters() if p.requires_grad}
        self.assertTrue(any(name.startswith('roberta.encoder.layer.1.') for name in names))
        self.assertTrue(any(name.startswith('roberta.encoder.layer.2.') for name in names))
        self.assertTrue(any(name.startswith('classifier.dense.') for name in names))
        self.assertFalse(any(name.startswith('roberta.encoder.layer.0.') for name in names))
        self.assertFalse(any(name.startswith('roberta.embeddings.') for name in names))
        before=frozen_parameter_sha256(candidate)
        weights=candidate.classifier.out_proj.weight.detach().clone()
        encoded=dict(input_ids=torch.tensor([[0,4,5,2],[0,7,8,2],[0,9,10,2]]),
                     attention_mask=torch.ones((3,4),dtype=torch.long))
        optimizer=torch.optim.AdamW([p for p in candidate.parameters() if p.requires_grad],lr=2e-5)
        loss=classification_loss([dict(class_id=i) for i in [0,1,2]],candidate(**encoded).logits,[1,1,1])
        finite_update(loss,candidate,optimizer)
        self.assertEqual(before,frozen_parameter_sha256(candidate))
        self.assertEqual(before,receipt['frozen_parameter_sha256'])
        self.assertFalse(torch.equal(weights,candidate.classifier.out_proj.weight))

    def test_invalid_trainability_request_is_rejected_before_expansion_or_freezing(self):
        candidate=model();head=candidate.classifier.out_proj
        for n in [0,4,True]:
            with self.assertRaises(ValueError):configure_adaptation(candidate,101,last_n=n)
        self.assertIs(candidate.classifier.out_proj,head)
        self.assertEqual(candidate.config.num_labels,1)
        self.assertTrue(all(p.requires_grad for p in candidate.parameters()))


if __name__=='__main__':unittest.main()
