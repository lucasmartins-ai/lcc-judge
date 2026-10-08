import copy
import unittest

from research.wording_development_pilot import designs, validate_wording


class WordingPilotTests(unittest.TestCase):
    def test_whole_goal_families_are_disjoint_and_record_vocabulary_stays_known(self):
        recipes = designs()
        validate_wording(recipes)
        self.assertEqual(len(recipes['train']['roles']), 18)
        self.assertEqual(recipes['train']['pairs'],recipes['validation']['pairs'])
        for role in recipes['train']['roles']:
            self.assertEqual(recipes['train']['roles'][role][4],recipes['validation']['roles'][role][4])
        changed = copy.deepcopy(recipes)
        changed['validation']['roles']['retry_attempts'][2][0] = changed['train']['roles']['retry_attempts'][2][0]
        with self.assertRaises(AssertionError):
            validate_wording(changed)


if __name__ == '__main__':
    unittest.main()
