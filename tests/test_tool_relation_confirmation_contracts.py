from itertools import combinations
import unittest

from research.tool_relation_state_contracts import ROLES as OLD, PAIRS as SEEN, PT_CAPTIONS as OLD_PT
from research.tool_relation_confirmation_contracts import ROLES, PT_CAPTIONS, PAIRS, DIRECT_FRAMES, UNKNOWN_FRAMES


class ConfirmationContractsTests(unittest.TestCase):
    def test_all_edges_partition_into_unseen_primary_and_known_wording_control(self):
        self.assertEqual(set(map(tuple,PAIRS.values())),set(combinations(sorted(OLD),2)))
        known={tuple(sorted(v)) for v in SEEN.values()}
        self.assertEqual(sum(k.startswith('primary:') for k in PAIRS),101)
        self.assertEqual(sum(k.startswith('seen_control:') for k in PAIRS),52)
        self.assertTrue(all((tuple(v) in known)==k.startswith('seen_control:') for k,v in PAIRS.items()))

    def test_fresh_wording_preserves_primitive_units_and_receiver_observation_scope(self):
        for name,spec in ROLES.items():
            self.assertEqual(spec[:2],OLD[name][:2])
            for index in [2,3,4]:
                self.assertEqual(len(set(spec[index])),4)
                self.assertFalse(set(spec[index])&set(OLD[name][index]))
            self.assertEqual(len(set(PT_CAPTIONS[name])),4)
            self.assertFalse(set(PT_CAPTIONS[name])&set(OLD_PT[name]))
            if name.startswith('udp_received_'):
                self.assertTrue(all('recorded' in v and 'budget' in v for v in spec[2]+spec[4]))
                self.assertTrue(all('limite de leitura registrado' in v for v in spec[3]+PT_CAPTIONS[name]))
        self.assertEqual(set(DIRECT_FRAMES['final']),{'en','pt'})
        self.assertEqual(set(UNKNOWN_FRAMES['final']),{'derived_or_multifield_goal','diagnosis_goal','broader_usefulness_goal'})
        for name in ('git_index_edits', 'git_worktree_edits'):
            for phrase in ROLES[name][2] + ROLES[name][4]:
                if 'flag' in phrase or 'status-column' in phrase:
                    self.assertIn('excluding untracked and ignored entries', phrase)
            for phrase in ROLES[name][3] + PT_CAPTIONS[name]:
                if 'marca' in phrase or 'coluna preparada' in phrase:
                    self.assertIn('excluindo entradas não rastreadas e ignoradas', phrase)
        self.assertIn('Git index path names', ROLES['git_index_files'][2][1])
        self.assertIn('caminhos do índice Git', ROLES['git_index_files'][3][1])


if __name__=='__main__':unittest.main()
