"""Portable historical evidence checks. Archived sources are never executed here."""
from collections import Counter
import hashlib
import json
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verified_sources(directory, sources, archive='executed-source'):
    paths = []
    for name, expected in sources.items():
        source = Path(directory)/archive/name
        assert sha(source) == expected, f'Archived source changed: {source}'
        paths.append(str(Path(archive)/name))
    return paths


def read_ledger(directory):
    directory = Path(directory)
    manifest = json.loads((directory/'ledger-manifest.json').read_text())
    path = directory/'canonical-ledger.jsonl'
    assert sha(path) == manifest['export_sha256'], 'Ledger export changed'
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    assert len(rows) == manifest['entries']
    assert all(r['feature'] == manifest['feature'] for r in rows)
    assert all(set(r) <= {'ts', 'feature', 'model', 'status', 'input_tokens',
                         'output_tokens', 'answers'} for r in rows)
    assert sum(r['input_tokens'] for r in rows) == manifest['input_tokens']
    return rows


def call_fingerprints(rows, question):
    return Counter((r['input_tokens'], r['output_tokens'], r['answers'][question]['noul'])
                   for r in rows)
