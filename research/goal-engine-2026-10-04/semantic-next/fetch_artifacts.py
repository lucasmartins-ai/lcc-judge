"""Read-only, TLS-verified artifact preparation at an immutable upstream revision."""
import hashlib
import json
from pathlib import Path
import ssl
import urllib.request

import certifi

HERE = Path(__file__).resolve().parent
REPO = 'cross-encoder/mmarco-mMiniLMv2-L12-H384-v1'
REVISION = '8008f0154ca2387468013ed439df09d70c122412'
EXPECTED_API = '8008f0154ca2387468013ed439df09d70c122412'
DEST = Path.home() / '.cache/huggingface/hub/models--cross-encoder--mmarco-mMiniLMv2-L12-H384-v1/snapshots' / REVISION
FILES = ['README.md', 'config.json', 'model.safetensors', 'tokenizer.json',
         'tokenizer_config.json', 'special_tokens_map.json', 'sentencepiece.bpe.model']


def main():
    metadata = json.loads((HERE / 'upstream/model-api.json').read_text())
    assert metadata['id'] == REPO and metadata['sha'] == EXPECTED_API
    siblings = {r['rfilename']: r for r in metadata['siblings']}
    context = ssl.create_default_context(cafile=certifi.where())
    DEST.mkdir(parents=True, exist_ok=True)
    receipts = {}
    for name in FILES:
        meta = siblings[name]
        path = DEST / name
        if not path.exists():
            partial = path.with_name(path.name + '.download-partial')
            if partial.exists():
                raise ValueError(f'Inspect partial transfer before retry: {name}')
            url = f'https://huggingface.co/{REPO}/resolve/{REVISION}/{name}'
            with urllib.request.urlopen(url, context=context, timeout=60) as source, partial.open('xb') as target:
                while chunk := source.read(1024 * 1024):
                    target.write(chunk)
            data = partial.read_bytes()
        else:
            data = path.read_bytes()
        assert len(data) == meta['size'], name
        digest = hashlib.sha256(data).hexdigest()
        if 'lfs' in meta:
            assert digest == meta['lfs']['sha256'], name
        else:
            git_digest = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
            assert git_digest == meta['blobId'], name
        if not path.exists():
            partial.rename(path)
        receipts[name] = digest
        print(name, len(data), digest, flush=True)
    receipt = dict(repo_id=REPO, revision=REVISION, license='apache-2.0', files=receipts,
                   primary_source=f'https://huggingface.co/{REPO}/blob/{REVISION}/README.md',
                   upstream_blob_or_lfs_identity_verified=True, TLS_verified=True,
                   inference_executed=False, training_executed=False, adoption=False)
    target = HERE / 'upstream/artifacts.json'
    if target.exists():
        assert json.loads(target.read_text()) == receipt
    else:
        target.write_text(json.dumps(receipt, indent=2, allow_nan=False) + '\n')


if __name__ == '__main__':
    main()
