# Attribution and licenses

Project-authored code, documentation and synthetic research fixtures are MIT.
The MIT license does not replace licenses on imported sources, dependencies or
model artifacts. No endorsement by upstream authors is claimed.

| Component | Source | License and use |
| --- | --- | --- |
| LCC | [lucasmartins-ai/lcc](https://github.com/lucasmartins-ai/lcc) | MIT; shared keep-question wording and integration contract; copyright Local Context Compiler contributors |
| ModernBERT | [Answer.AI/LightOn model card](https://huggingface.co/answerdotai/ModernBERT-base) | Apache-2.0; pretrained architecture/backbone/tokenizer. Adapted checkpoint distribution must retain upstream attribution and license |
| BGE | [BAAI model card](https://huggingface.co/BAAI/bge-small-en-v1.5) | MIT; comparison baseline; historical generic pooling differs from the official recipe |
| multilingual GTE | [Alibaba-NLP model card](https://huggingface.co/Alibaba-NLP/gte-multilingual-base) | Apache-2.0; baseline includes custom upstream model code; model and code revisions must both be pinned |
| Laya | [Convai Innovations](https://github.com/NandhaKishorM/laya) | Apache-2.0; optional comparison model; no weights are bundled |
| MiniLM passage reranker | [pinned Cross-Encoder card](https://huggingface.co/cross-encoder/ms-marco-MiniLM-L6-v2/blob/233902d25c440f23af6f7d6e94d2946bac0bee0a/README.md) | Apache-2.0 declared upstream; measured research controls and unadopted derivatives, card/file hashes saved; weights are not bundled and no LCC outcome for these derivatives is claimed |
| Multilingual MiniLMv2 passage reranker | [pinned Cross-Encoder card](https://huggingface.co/cross-encoder/mmarco-mMiniLMv2-L12-H384-v1/blob/8008f0154ca2387468013ed439df09d70c122412/README.md) | Apache-2.0 declared upstream; next ranking diagnostic uses verified local artifacts separately from the native provider; upstream training includes machine-translated mMARCO Portuguese, which does not establish LCC quality. No weights are bundled |
| Git and retry observation tooling | [Git](https://git-scm.com/docs/git-status), [Tenacity](https://pypi.org/project/tenacity/9.1.4/) | Git GPL-2.0 and Tenacity Apache-2.0; versioned binaries/dependencies prepared as private container artifacts only. No executable/wheel is bundled in this source repository; dependency distributions retain their copyright/license files. Captures remain authored fixtures |
| GNU/Python tool observations | [source contracts](research/tool_role_contracts.py) | Executables/APIs run in a pinned third-party container on authored fixtures; only command/API receipts and authored language bindings are saved, no executable binaries or manual passages are bundled |
| Kubernetes reference excerpts | [source manifest](research/pdb-routing-2026-10-04/upstream/source-manifest.json) | Apache-2.0; original headers retained in saved reference files; license in [licenses/APACHE-2.0.txt](licenses/APACHE-2.0.txt) |
| TypeSafe/Jev | [TypeSafe](https://typesafe.ai/) | External service; only saved response evidence is in historical runs; no Jev weights or credentials are included |

Python dependencies retain their distributions' own license files. Container base
images remain third-party artifacts and are identified by immutable digest.

Citation for the backbone: Warner et al., *Smarter, Better, Faster, Longer: A Modern
Bidirectional Encoder for Fast, Memory Efficient, and Long Context Finetuning and
Inference*, [arXiv:2412.13663](https://arxiv.org/abs/2412.13663).
