import unittest


class FakeBackend:
    is_local = True
    window_tokens = 8192
    identity = dict(model='tensor-control', checkpoint_sha256='test-only')

    def __init__(self, **result):
        self.result = dict(logit=-3.0, actual_tokens=7, latency_ms=1.0,
                           truncated=False, error=None, **result)
        self.seen = []

    def score(self, objective, text):
        self.seen.append((objective,text))
        return self.result


class ContextEngineTests(unittest.TestCase):
    def test_counted_inputs_are_distinct_from_tokens_forwarded_to_encoder(self):
        from lcc_engine import ContextEngine
        for tokens, logit in [(9000, None), (7, 3.)]:
            backend=FakeBackend()
            backend.result.update(actual_tokens=tokens,logit=logit,forwarded=False)
            result=ContextEngine(backend=backend).rank_context('Inspect',[dict(id='b',text='facts')])
            self.assertEqual(result['items'][0]['status'],'UNKNOWN')
            self.assertEqual(result['counted_input_tokens'],tokens)
            self.assertEqual(result['encoded_tokens'],0)

    def test_native_result_is_a_ranking_signal_and_preserves_bytes_in_shadow(self):
        from lcc_engine import ContextEngine
        backend = FakeBackend()
        engine = ContextEngine(backend=backend)
        text = 'keep spaces  \n\nUnicode: ação\n'
        result = engine.rank_context('Inspect the incident', [dict(id='b1',text=text)])
        self.assertEqual(backend.seen, [('Inspect the incident',text)])
        self.assertEqual(result['items'][0]['logit'], -3)
        self.assertEqual(result['items'][0]['decision'], 'KEEP')
        self.assertIs(result['calibrated_probability'], False)
        self.assertNotIn('noul', str(result))
        self.assertFalse(engine.supports_operation('noul'))
        self.assertTrue(engine.supports_operation('rank_context'))

    def test_unusable_scores_are_unknown_and_kept(self):
        from lcc_engine import ContextEngine
        for change in [dict(logit=float('nan')),dict(truncated=True),dict(error='failed')]:
            with self.subTest(change=change):
                backend = FakeBackend()
                backend.result.update(change)
                item = ContextEngine(backend=backend).rank_context('Inspect', [dict(id='b',text='facts')])['items'][0]
                self.assertEqual(item['status'], 'UNKNOWN')
                self.assertEqual(item['decision'], 'KEEP')
                self.assertIsNone(item['logit'])

    def test_missing_runtime_is_unknown_and_never_falls_back_to_network(self):
        from lcc_engine import ContextEngine
        class BrokenBackend(FakeBackend):
            def score(self,*_):
                raise RuntimeError('runtime unavailable')
        result = ContextEngine(backend=BrokenBackend()).rank_context('Inspect',[dict(id='b',text='facts')])
        self.assertEqual(result['items'][0]['status'],'UNKNOWN')
        self.assertEqual(result['items'][0]['decision'],'KEEP')

    def test_duplicate_ids_and_empty_objective_are_rejected(self):
        from lcc_engine import ContextEngine
        engine = ContextEngine(backend=FakeBackend())
        for objective,blocks in [('',[dict(id='b',text='facts')]),
                                 ('Inspect',[dict(id='b',text='facts'),dict(id='b',text='other')])]:
            with self.assertRaises(ValueError):
                engine.rank_context(objective,blocks)

    def test_many_blocks_do_not_consume_one_shared_sequence_window(self):
        from lcc_engine import ContextEngine
        backend = FakeBackend()
        backend.result['actual_tokens']=6000
        result = ContextEngine(backend=backend).rank_context('Inspect',
                    [dict(id=str(i),text='facts') for i in range(10)])
        self.assertEqual(result['encoded_tokens'],60000)
        self.assertEqual(len(backend.seen),10)
        self.assertTrue(all(item['status']=='SCORED' for item in result['items']))

    def test_malformed_backend_token_count_is_unknown(self):
        from lcc_engine import ContextEngine
        backend=FakeBackend()
        backend.result['actual_tokens']='7'
        result=ContextEngine(backend=backend).rank_context('Inspect',[dict(id='b',text='facts')])
        self.assertEqual(result['items'][0]['status'],'UNKNOWN')
        self.assertIsNone(result['items'][0]['actual_tokens'])
        self.assertEqual(result['encoded_tokens'],0)

    def test_unknown_backend_locality_cannot_be_advertised_as_offline(self):
        from lcc_engine import ContextEngine
        backend=FakeBackend()
        backend.is_local=False
        self.assertFalse(ContextEngine(backend=backend).is_local)


if __name__ == '__main__':
    unittest.main()
