from pathlib import Path
import tempfile
import unittest

import torch
from safetensors.torch import save_file

from research.audit_tool_relation_support import frozen_hash as first_parser
from research.audit_tool_relation_weights import frozen_hash
from research.tool_relation_adaptation import configure_adaptation
from tests.test_tool_relation_adaptation import model


class ToolRelationWeightsAuditTests(unittest.TestCase):
    def test_known_integer_position_buffer_is_checked_but_not_hashed_as_a_parameter(self):
        candidate=model();receipt=configure_adaptation(candidate,101)
        state={k:v.detach().contiguous() for k,v in candidate.state_dict().items()}
        state['roberta.embeddings.position_ids']=torch.arange(514,dtype=torch.int64).reshape(1,514)
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'weights.safetensors';save_file(state,str(path))
            with self.assertRaises(AssertionError):first_parser(path,receipt['frozen_names'])
            self.assertEqual(frozen_hash(path,receipt['frozen_names']),receipt['frozen_parameter_sha256'])
            state['roberta.embeddings.position_ids']=state['roberta.embeddings.position_ids']+1
            altered=Path(directory)/'altered.safetensors';save_file(state,str(altered))
            with self.assertRaises(AssertionError):frozen_hash(altered,receipt['frozen_names'])


if __name__=='__main__':unittest.main()
