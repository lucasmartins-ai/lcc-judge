import json
import unittest


class ObservationEngineTests(unittest.TestCase):
    def request(self):
        from lcc_engine.observations import ObservationRequest
        return ObservationRequest(entity='service-a', field='http_5xx_count',
                                  start='2027-01-01T12:00:00Z', end='2027-01-01T12:05:00Z')

    def text(self, **changes):
        obs = dict(time='2027-01-01T12:02:00Z', level='INFO', entity='service-a',
                   field='http_5xx_count', value=0, unit='count')
        obs.update(changes)
        return json.dumps(obs)

    def test_healthy_matches_and_unrelated_anomaly_drops(self):
        from lcc_engine.observations import ObservationEngine
        result = ObservationEngine().rank_observations(self.request(), [
            dict(id='healthy', text=self.text(value=0)),
            dict(id='other', text=self.text(entity='service-b', value=99)),
        ])
        self.assertEqual([item['decision'] for item in result['items']], ['KEEP', 'DROP'])
        self.assertFalse(result['necessity_estimated'])
        self.assertFalse(result['calibrated_probability'])

    def test_opaque_lines_and_ambiguous_records_keep_the_entire_block(self):
        from lcc_engine.observations import ObservationEngine
        for text in [self.text(entity='unresolved(service-a,service-b)'),
                     self.text(time='unknown'), self.text() + '\nprevious event explains cause']:
            item = ObservationEngine().rank_observations(self.request(), [dict(id='b', text=text)])['items'][0]
            self.assertEqual((item['status'], item['decision']), ('UNKNOWN', 'KEEP'))

    def test_unknown_line_overrides_an_obvious_match(self):
        from lcc_engine.observations import ObservationEngine
        item = ObservationEngine().rank_observations(self.request(),
                    [dict(id='b', text=self.text() + '\nopaque dependency')])['items'][0]
        self.assertEqual(item['status'], 'UNKNOWN')

    def test_invalid_timestamp_and_duplicate_json_keys_are_unknown(self):
        from lcc_engine.observations import ObservationEngine
        duplicate = self.text().replace('"entity": "service-a"', '"entity": "service-a", "entity": "service-b"')
        for text in [self.text(time='2027-99-99T12:02:00Z'), duplicate, self.text(value=True),
                     self.text(value=float('nan')), self.text(extra='undocumented')]:
            item = ObservationEngine().rank_observations(self.request(), [dict(id='b', text=text)])['items'][0]
            self.assertEqual(item['decision'], 'KEEP')
            self.assertEqual(item['status'], 'UNKNOWN')

    def test_window_is_inclusive_and_does_not_assume_nearby_time_is_relevant(self):
        from lcc_engine.observations import ObservationEngine
        for time, decision in [('2027-01-01T12:00:00Z','KEEP'), ('2027-01-01T12:05:00Z','KEEP'),
                               ('2027-01-01T11:59:59Z','DROP'), ('2027-01-01T12:05:01Z','DROP')]:
            item = ObservationEngine().rank_observations(self.request(), [dict(id='b', text=self.text(time=time))])['items'][0]
            self.assertEqual(item['decision'], decision)

    def test_block_ids_and_request_slots_are_validated(self):
        from lcc_engine.observations import ObservationEngine, ObservationRequest
        for start, end in [('bad', 'bad'), ('2027-01-01T12:05:00Z', '2027-01-01T12:00:00Z')]:
            with self.assertRaises(ValueError):
                ObservationRequest(entity='service-a', field='count', start=start, end=end)
        with self.assertRaises(ValueError):
            ObservationEngine().rank_observations(self.request(), [dict(id='b',text='x'),dict(id='b',text='y')])

    def test_supported_text_formats_and_kept_bytes_are_unchanged(self):
        import hashlib
        from lcc_engine.observations import ObservationEngine
        rows = [
            'time=2027-01-01T12:02:00Z level=INFO entity=service-a field=http_5xx_count value=0 unit=count',
            '2027-01-01T12:02:00Z | INFO | service-a | http_5xx_count=0 count',
            'At 2027-01-01T12:02:00Z, service-a reported http_5xx_count = 0 count (INFO).',
        ]
        for text in rows:
            item = ObservationEngine().rank_observations(self.request(), [dict(id='b',text=text)])['items'][0]
            self.assertEqual(item['status'], 'MATCH')
            self.assertEqual(item['text_sha256'], hashlib.sha256(text.encode()).hexdigest())

    def test_long_supported_records_do_not_inherit_a_transformer_window(self):
        from lcc_engine.observations import ObservationEngine
        text = (self.text(entity='service-b') + '\n') * 800 + self.text()
        item = ObservationEngine().rank_observations(self.request(), [dict(id='long', text=text)])['items'][0]
        self.assertEqual(item['status'], 'MATCH')
        self.assertEqual(item['records'], 801)

    def test_oversized_blocks_are_kept_without_partial_parsing(self):
        from lcc_engine.observations import ObservationEngine
        item = ObservationEngine(max_block_bytes=4).rank_observations(self.request(),
                    [dict(id='long', text=self.text(entity='service-b'))])['items'][0]
        self.assertEqual((item['status'], item['decision']), ('UNKNOWN', 'KEEP'))
        self.assertEqual(item['reason'], 'block_exceeds_byte_limit')

    def test_typed_engine_agrees_with_frozen_task_oracle_in_all_schemas(self):
        from research.relevance_corpus import build_split
        from lcc_engine.observations import ObservationEngine, ObservationRequest
        for row in build_split('final', 4):
            req = ObservationRequest(**row['request'])
            item = ObservationEngine().rank_observations(req, [dict(id='b', text=row['text'])])['items'][0]
            expected = {1: 'MATCH', 0: 'NO_MATCH', None: 'UNKNOWN'}[row['label']]
            self.assertEqual(item['status'], expected, row['kind'])


if __name__ == '__main__':
    unittest.main()
