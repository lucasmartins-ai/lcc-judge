"""Opt-in consumer integration; requires a LCC checkout on PYTHONPATH."""
import tempfile
from pathlib import Path
import unittest

try:
    from lcc.relevance.compactor import RelevanceCompactionReport, RelevanceCompactionRequest, compact_context
except ModuleNotFoundError as exc:
    if exc.name != 'lcc':
        raise
    RelevanceCompactionRequest = None
else:
    # An LCC checkout without provider="specialist" (e.g. a stale local main) would
    # silently fall back to lexical dropping; skip instead of failing on that checkout.
    if 'specialist_ranking' not in RelevanceCompactionReport.__dataclass_fields__:
        RelevanceCompactionRequest = None

from lcc_engine import ContextEngine


class Backend:
    is_local = True
    window_tokens = 8192
    identity = dict(model='control',checkpoint_sha256='test-only')
    def score(self,objective,text):
        return dict(logit=-99.,actual_tokens=10,latency_ms=1.,truncated=False,error=None)


@unittest.skipIf(RelevanceCompactionRequest is None,'Put an LCC checkout with provider="specialist" on PYTHONPATH')
class LCCIntegrationTests(unittest.TestCase):
    text = ('noise from a different subsystem '*10+'\n\n'+
            'more unrelated verbose output '*10+'\n')

    def request(self, **kwargs):
        return RelevanceCompactionRequest(text=self.text,question='Find the invoice failure',
            provider='specialist',min_block_chars=30,max_block_chars=350,
            deterministic_protection=False,enable_sufficiency=False,**kwargs)

    def test_opt_in_shadow_scores_without_mutating_context(self):
        engine=ContextEngine(backend=Backend())
        result=compact_context(self.request(client=engine))
        self.assertEqual(result.compacted_text,self.text)
        self.assertEqual(result.report.provider_used,'specialist_shadow')
        self.assertEqual(result.report.semantic_guarantee,'none')
        self.assertIsNotNone(result.report.specialist_ranking)
        self.assertTrue(all(item['decision']=='KEEP' for item in result.report.specialist_ranking['items']))

    def test_missing_specialist_keeps_context_instead_of_lexical_dropping(self):
        result=compact_context(self.request())
        self.assertEqual(result.compacted_text,self.text)
        self.assertEqual(result.report.degradation_reason,'specialist_unavailable')
        self.assertEqual(result.report.semantic_guarantee,'none')

    def test_shadow_rejects_a_decision_cache_until_the_policy_is_validated(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError,'shadow.*cache'):
                compact_context(self.request(client=ContextEngine(backend=Backend()),
                                               decisions_cache_path=Path(temp)/'cache.json'))

    def test_nonlocal_client_is_not_called(self):
        class RemoteClient:
            is_local=False
            def rank_context(self,*_):
                raise AssertionError('This client must not receive context')
        result=compact_context(self.request(client=RemoteClient()))
        self.assertEqual(result.compacted_text,self.text)
        self.assertEqual(result.report.degradation_reason,'specialist_unavailable')


if __name__ == '__main__':
    unittest.main()
