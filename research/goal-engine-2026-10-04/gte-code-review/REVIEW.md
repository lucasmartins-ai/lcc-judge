# Pinned GTE implementation

Source: [Alibaba-NLP/new-impl](https://huggingface.co/Alibaba-NLP/new-impl/tree/40ced75c3017eb27626c9d4ea981bde21a2662f4),
revision `40ced75c3017eb27626c9d4ea981bde21a2662f4`, Apache-2.0 with the
upstream copyright notices preserved in both source files.

The embedding checkpoint has a separate revision,
`9bbca17d9273fd0d03d5725c7a4b0f6b45142062`. Enabling custom code is restricted
to these pins and offline loading. The source imports Torch/Transformers and an
optional xformers module; the CPU recipe disables memory-efficient attention and
unpadding. A static call inspection found no direct subprocess, socket, file-write,
dynamic-evaluation or HTTP calls in these two implementation files. This inspection
is not a complete security audit of dependencies.

The Transformers 5 loader left nonpersistent `position_ids`, `inv_freq`,
`cos_cached` and `sin_cached` buffers invalid. The pre-fix smoke receipt is retained
in `../official-baseline-smoke-before-buffer-fix.json`. The adapter now reconstructs
position IDs and invokes the pinned implementation's `_init_rope(config)` after
loading learned weights. This is a compatibility correction using the original
formulas. Unexpected classifier weights are allowed because the embedding model
does not use that checkpoint head; missing encoder weights or other unexpected keys
are refused.

`../gte-buffer-corrected-smoke.json` records equal scores from two independently
loaded models and checks the complete position-ID buffer. The five small recipe
tests cover normalized CLS pooling, prefix placement, separate revisions and buffer
restoration. Larger matched-text results are a separate experiment.

Official recipes: [BGE](https://huggingface.co/BAAI/bge-small-en-v1.5)
uses normalized CLS with a retrieval prefix on queries only;
[GTE](https://huggingface.co/Alibaba-NLP/gte-multilingual-base)
uses normalized CLS without that prefix. Historical mean-pooling scores retain
their historical names and are not overwritten by the new `*-official` recipes.
