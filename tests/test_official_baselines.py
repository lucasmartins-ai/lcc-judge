import unittest
import torch
from types import SimpleNamespace
from bakeoff.adapters import OfficialEmbeddingAdapter, default_roster


class OfficialBaselineTests(unittest.TestCase):
    def test_query_prefix_is_not_applied_to_passage(self):
        adapter=OfficialEmbeddingAdapter.bge()
        self.assertEqual(adapter.prepare_text('query',query=True),
                         'Represent this sentence for searching relevant passages: query')
        self.assertEqual(adapter.prepare_text('passage',query=False),'passage')

    def test_gte_has_no_prefix_and_separate_code_pin(self):
        adapter=OfficialEmbeddingAdapter.gte()
        self.assertEqual(adapter.prepare_text('query',query=True),'query')
        self.assertEqual(adapter.prepare_text('passage',query=False),'passage')
        self.assertEqual(len(adapter.code_revision),40)
        self.assertNotEqual(adapter.revision,adapter.code_revision)

    def test_official_pooling_uses_normalized_cls(self):
        adapter=OfficialEmbeddingAdapter.bge()
        hidden=torch.tensor([[[3.,4.],[300.,400.]]])
        pooled=adapter.pool(hidden)
        self.assertTrue(torch.allclose(pooled,torch.tensor([.6,.8])))

    def test_new_roster_does_not_reuse_historical_recipe_names(self):
        names={a.name for a in default_roster()}
        self.assertIn('bge-small-en-v1.5-official',names)
        self.assertIn('gte-multilingual-base-official',names)
        self.assertNotIn('gte-multilingual-base',names)

    def test_gte_derived_buffers_are_restored_after_meta_loading(self):
        class Embeddings(torch.nn.Module):
            def __init__(self):
                super().__init__()
                self.register_buffer('position_ids',torch.zeros(8,dtype=torch.long),persistent=False)
                self.calls=[]
            def _init_rope(self,config): self.calls.append(config)
        model=SimpleNamespace(embeddings=Embeddings(),config=SimpleNamespace(max_position_embeddings=8))
        OfficialEmbeddingAdapter.restore_gte_buffers(model)
        self.assertEqual(model.embeddings.position_ids.tolist(),list(range(8)))
        self.assertEqual(model.embeddings.calls,[model.config])


if __name__=='__main__': unittest.main()
