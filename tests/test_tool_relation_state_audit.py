from copy import deepcopy
import unittest

from research.audit_tool_relation_states import git_blob,recount_git


def receipt():
    head={'clean':'00','removed':'ff'};index={'clean':'00','new':'0102'};current=dict(index)
    return dict(head_tree_stdout=''.join('100644 blob '+git_blob(value)+'\t'+path+'\0' for path,value in head.items()),
        head_paths_stdout='clean\0removed\0',index_stage_stdout=''.join('100644 '+git_blob(value)+' 0\t'+path+'\0' for path,value in index.items()),
        index_stdout='clean\0new\0',untracked_stdout='',ignored_stdout='',status_stdout='D  removed\0A  new\0',
        current_file_hex=current,authored=dict(baseline_file_hex=head,index_file_hex=index,current_file_hex=current,
                                              untracked_file_hex={},ignored_file_hex={}))


class ToolRelationStateAuditTests(unittest.TestCase):
    def test_independent_blob_recount_proves_staged_delete_and_rejects_changed_index_bytes(self):
        raw=receipt();result=recount_git(raw)
        self.assertEqual(result['git_index_edits'],2)
        self.assertEqual(result['git_index_files'],2)
        self.assertEqual(result['git_clean_tracked_files'],1)
        changed=deepcopy(raw);changed['authored']['index_file_hex']['new']='03'
        with self.assertRaises(AssertionError):recount_git(changed)
        changed=deepcopy(raw);changed['status_stdout']=' M clean\0A  new\0D  removed\0'
        with self.assertRaises(AssertionError):recount_git(changed)

    def test_null_git_paths_preserve_newline_without_normalization(self):
        raw=receipt();new='clean\nfile'
        for field in ['head_tree_stdout','head_paths_stdout','index_stage_stdout','index_stdout']:
            raw[field]=raw[field].replace('clean',new)
        for mapping in [raw['authored']['baseline_file_hex'],raw['authored']['index_file_hex'],raw['current_file_hex']]:
            if 'clean' in mapping:mapping[new]=mapping.pop('clean')
        self.assertEqual(recount_git(raw)['git_index_files'],2)


if __name__=='__main__':unittest.main()
