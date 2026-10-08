import json
import unittest

from research.measurement_projection import project_measurement


ENTITY = 'tool-123456abcdef'
GOAL = f'How much CPU time was used? Report evidence for {ENTITY}; ordinary and unusual values both count.'


class MeasurementProjectionTests(unittest.TestCase):
    def test_two_record_forms_keep_question_measurement_and_value(self):
        body = dict(entity=ENTITY, level='ERROR', measurement='Combined user and system CPU duration', value=7)
        for text in [json.dumps(body), f'Tool report {ENTITY} [WARN]: Combined user and system CPU duration: 7.']:
            result = project_measurement(GOAL, text)
            self.assertEqual(result['status'], 'PROJECTED')
            self.assertEqual(result['objective'], 'How much CPU time was used?')
            self.assertEqual(result['text'], 'Combined user and system CPU duration: 7.')
            self.assertNotIn(ENTITY, result['text'])
            self.assertEqual(result['original_text'], text)

    def test_healthy_value_is_not_filtered(self):
        text = json.dumps(dict(entity=ENTITY, level='INFO', measurement='Successful cache hits', value=0))
        self.assertEqual(project_measurement(GOAL, text)['text'], 'Successful cache hits: 0.')

    def test_ambiguous_or_mismatched_scope_keeps_original_and_never_scores(self):
        valid = json.dumps(dict(entity=ENTITY, level='INFO', measurement='Resident bytes', value=10))
        invalid = [valid.replace(ENTITY, 'tool-abcdef123456'), valid[:-1]+',"extra":true}',
                   valid[:-1]+',"value":200}', valid.replace('10', 'true'),
                   'Tool report '+ENTITY+' [INFO]: missing value.', 'unstructured log']
        for text in invalid:
            result = project_measurement(GOAL, text)
            self.assertEqual(result['status'], 'UNKNOWN')
            self.assertIsNone(result['objective'])
            self.assertIsNone(result['text'])
            self.assertEqual(result['original_text'], text)
        self.assertEqual(project_measurement('Keep useful context', valid)['status'], 'UNKNOWN')


if __name__ == '__main__':
    unittest.main()
