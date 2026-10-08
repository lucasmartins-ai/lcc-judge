"""Explicit one-time export of non-secret call evidence; no private path defaults."""
import argparse
import hashlib
import json
from pathlib import Path


def export(source, output, feature, question):
    source = Path(source)
    output = Path(output)
    rows = [json.loads(line) for line in source.read_text().splitlines() if line.strip()]
    entries = []
    for row in rows:
        answers = row.get('answers', {})
        selected = list(answers) if question == '*' else [question]
        if row.get('feature') != feature or not answers or any(q not in answers for q in selected):
            continue
        keep = {k: row[k] for k in ['ts', 'feature', 'model', 'status', 'input_tokens',
                                    'output_tokens'] if k in row}
        keep['answers'] = {q: {'noul': answers[q]['noul']} for q in selected}
        entries.append(keep)
    path = output/'canonical-ledger.jsonl'
    text = ''.join(json.dumps(row, sort_keys=True, ensure_ascii=False)+'\n' for row in entries)
    if path.exists():
        assert path.read_text() == text, 'Existing export differs; create a new run archive'
        return
    output.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    manifest = dict(schema='lcc-ledger-export/0.1', feature=feature, question=question,
                    entries=len(entries), input_tokens=sum(r['input_tokens'] for r in entries),
                    excluded_feature_entries_without_question=sum(
                        r.get('feature') == feature and (not r.get('answers') if question == '*' else question not in r.get('answers', {})) for r in rows),
                    source_snapshot_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                    export_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                    contains_request_content=False, contains_credentials=False,
                    exported_after_execution=True, externally_attested=False)
    (output/'ledger-manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--feature', required=True)
    parser.add_argument('--question', required=True)
    args = parser.parse_args()
    export(args.source, args.output, args.feature, args.question)
