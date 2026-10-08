import json
from pathlib import Path
import tempfile
import unittest


class LedgerExportTests(unittest.TestCase):
    def test_mixed_question_export_reconciles_without_request_or_key(self):
        from research.export_ledger import export
        from research.archives import read_ledger
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);source=root/'ledger.jsonl'
            row=dict(ts='now',feature='study',model='pinned',status='ok',input_tokens=22,output_tokens=8,
                     answers={'keep_b1':{'noul':.3,'confidence':.9},'consistent':{'noul':.8}},
                     api_key='must-never-be-exported',state={'private':'request text'})
            source.write_text(json.dumps(row)+'\n')
            export(source,root/'out','study','*')
            rows=read_ledger(root/'out')
            self.assertEqual(len(rows),1)
            self.assertEqual(rows[0]['answers'],{'keep_b1':{'noul':.3},'consistent':{'noul':.8}})
            self.assertNotIn('must-never-be-exported',(root/'out/canonical-ledger.jsonl').read_text())
            self.assertNotIn('private',(root/'out/canonical-ledger.jsonl').read_text())


if __name__=='__main__':unittest.main()
