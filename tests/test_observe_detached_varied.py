import unittest

from research.observe_detached_varied import identity_matches, process_state


class DetachedObservationTests(unittest.TestCase):
    def test_interpreter_path_change_does_not_hide_the_same_live_study(self):
        expected=dict(pid=10,birth='same',command='/workspace/.venv/bin/python -m research.detached_varied_study supervise')
        current=dict(pid=10,birth='same',live=True,command='/Framework/Python -m research.detached_varied_study supervise')
        self.assertTrue(identity_matches(expected,current,['-m','research.detached_varied_study','supervise']))
        current['birth']='different'
        self.assertFalse(identity_matches(expected,current,['-m','research.detached_varied_study','supervise']))

    def test_transient_or_different_live_command_is_unknown_not_stopped(self):
        self.assertEqual(process_state(True,True,False,False,None),'UNKNOWN_PROCESS_IDENTITY')
        self.assertEqual(process_state(True,True,True,True,None),'RUNNING')
        self.assertEqual(process_state(False,True,False,True,None),'RUNNING_ORPHAN_CHILD')
        self.assertEqual(process_state(False,False,False,False,None),'STOPPED')
        self.assertEqual(process_state(False,False,False,False,dict(returncode=0,study_complete=True)),'COMPLETED')


if __name__=='__main__':unittest.main()
