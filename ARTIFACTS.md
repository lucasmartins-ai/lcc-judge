# Artifacts and reproducibility

Source code, cases and historical receipts belong in the repository. Model weights,
optimizer state, container images and compiled executables are separate artifacts.
The local inventory is [artifacts/models.json](artifacts/models.json); it records
file hashes and measured provenance, not download URLs or a published model release.

The supported backbone for current specialist loads is
`answerdotai/ModernBERT-base@8949b909ec900327062f0ebf497f51aef5e6f0c8`.
Model and tokenizer use the same immutable revision. Historical checkpoint configs
did not record that revision; the current loader pin must not be presented as proof
of their original load. Their adapted tensors and corpus metadata are preserved.

Fetch the backbone explicitly before offline inference:

```python
from huggingface_hub import snapshot_download
snapshot_download(
    "answerdotai/ModernBERT-base",
    revision="8949b909ec900327062f0ebf497f51aef5e6f0c8",
    allow_patterns=["*.json", "*.safetensors", "*.txt", "LICENSE*", "README.md"],
)
```

No public specialist-weight download exists yet. In this workspace,
`models/exp02e-unfreeze2` and `models/exp02e-line-attn` are the clean v0.4 research
controls. The v0.3 checkpoints are historical, have holdout contamination and are
unsuitable for a clean claim. None passes the long-context gate.

To create a new checkpoint rather than overwrite an old one:

```sh
python -m specialist.corpus data/reproduced-v04
python -m specialist.train --data-dir data/reproduced-v04 \
  --out models/reproduced-v04-unfreeze2 --pooling line-attn \
  --unfreeze-last-n 2 --epochs 3 --seed 0 --device cpu --offline
```

The corrected pooling implementation is a new experiment condition; this command
does not reproduce old scores bit for bit. New runs save the backbone revision,
dataset digest and an atomic `resume.pt` containing weights, optimizer and RNG.
`--resume` requires this complete state and matching training settings. Legacy
checkpoints without RNG state cannot honestly resume a reproducible trajectory.

Releasing weights requires a model card, license/attribution, immutable hosting,
checksums, tokenizer/backbone identity, trained epochs/seeds, data license and exact
evaluation receipts. The local inventory is preparation for that release.

Additional research derivatives: [compact relation](artifacts/compact-relation.json)
and [three-class support](artifacts/tool-role-support.json), followed by
[retained multilingual ranking](artifacts/tool-relation-support.json). Every candidate fails
its recorded quality gate. They are separate MiniLM architectures, are not hosted
and cannot be loaded as native ModernBERT checkpoints. The inventories preserve
weight hashes and direct epoch metadata, not an adoption or download claim.

The later [factorized conditional development artifact](artifacts/factorized-relation-dev.json)
records one seed/three finite epochs on exposed data. Train ordering fits, but
validation/policy fail. It is rejected, has no fresh final or public download and
does not replace the native provider.

The [varied-state development data](research/goal-engine-2026-10-04/tool-relation-states-v2/RESULTS.md)
adds complete SHA-bound raw captures, frozen source/declaration snapshots and gzip
JSONL supervision/views. Its separate checked worker
build repeats the pinned private Debian/wheel blobs under a new ignored build
directory; images and dependency blobs remain external artifacts. Gzip preserves
all rows and prevents large duplicate-row files from entering the source release.

The subsequent [varied conditional development artifact](artifacts/varied-relation-dev.json)
records one seed/three finite epochs with direct metadata. Exposed train and
validation pass, and private/frozen weights independently verify. Subsequent fresh
confirmation rejects all three seeds; useful semantic LCC outcomes remain
unverified. No native-provider substitution, public download or adoption. See
[scoped development](research/goal-engine-2026-10-04/varied-relation-dev-v2/RESULTS.md)
and [failed confirmation](research/goal-engine-2026-10-04/varied-relation-confirm-v1/RESULTS.md).

The [held-goal-wording pilot artifact](artifacts/wording-development-pilot.json)
records one fixed seed/three finite epochs on eight known relevance fields. Both
development policies fail. Its independent audit verifies private/frozen weights
and all executed data hashes, explicitly correcting the interpretation of a
preserved relative-path metadata typo. No fresh final, public download, adoption
or native ModernBERT compatibility follows. See
[pilot scope and receipts](research/goal-engine-2026-10-04/wording-development-pilot-v1/RESULTS.md).
