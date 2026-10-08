from pathlib import Path
import tempfile
import unittest

from safetensors.torch import save_file

from research.audit_tool_relation_support import frozen_hash,normalized_semantic_rows
from research.audit_tool_role_support import reduce_metrics,thresholds_from_validation
from research.tool_relation_adaptation import configure_adaptation
from tests.test_tool_relation_adaptation import model
from tests.test_tool_role_policy import examples


class ToolRelationSupportAuditTests(unittest.TestCase):
    def test_independent_reduction_counts_new_unknown_annotations(self):
        rows,scores=examples()
        for row in rows:
            if row['label'] is None:row['unknown_kind']='diagnosis_goal'
        normalized=normalized_semantic_rows(rows)
        result=reduce_metrics(normalized,scores,thresholds_from_validation(normalized,scores))
        self.assertEqual(result['semantic_unknown'],2)
        self.assertEqual(result['semantic_unknown_recognition'],1.0)
        self.assertTrue(all(row['unknown_kind']=='diagnosis_goal' for row in rows if row['label'] is None))

    def test_stdlib_safetensors_recount_detects_changed_frozen_parameters(self):
        candidate=model();receipt=configure_adaptation(candidate,101)
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'weights.safetensors'
            state={k:v.detach().contiguous() for k,v in candidate.state_dict().items()}
            save_file(state,str(path))
            self.assertEqual(frozen_hash(path,receipt['frozen_names']),receipt['frozen_parameter_sha256'])
            changed=receipt['frozen_names'][0]
            state[changed]=state[changed].clone()+1
            altered=Path(directory)/'altered.safetensors';save_file(state,str(altered))
            self.assertNotEqual(frozen_hash(altered,receipt['frozen_names']),receipt['frozen_parameter_sha256'])


if __name__=='__main__':unittest.main()
