# LCC Context Engine

A specialized local ranking engine for [LCC](https://github.com/lucasmartins-ai/lcc).
The research question is whether a narrower decision task can provide more useful
context and lower total cost than the general Laya/Jev decision path inside LCC.
The contribution is evaluated as **engine + LCC**, with task outcomes and preserved
evidence as the deciding measurements.

> **Current state (2026-10-11): start with [STATUS.md](STATUS.md).** No learned
> candidate passed outside training; the checkpoint stays shadow-only and is not
> adopted. What shipped is deterministic, in LCC: the opt-in request log (#40), Jev
> request fitting (#44) and the offline `rules` provider with lossless (default) and
> recoverable modes (#45). On real sessions Jev block mode cuts 3.5% of tokens, lossy
> rules failed two blind audits, and lossless/recoverable cut about 1%. Laya has not
> been run on the real-session bench. The history below is kept as written.

The neural engine ranks `(objective, block)` pairs using an adapted ModernBERT
encoder. Its operation, `rank_context`, runs offline after explicit artifact setup.
A separate dependency-free `rank_observations` operation retrieves explicit
entity/field/UTC-window records in supported schemas. LCC owns parsing,
protections, cache handling and downstream policy.
This separation lets the engine specialize without becoming a general question
answering model.

**Research status:** the long-context quality gate has failed. Existing scores are
relevance signals; they do not establish calibrated probabilities, counterfactual
necessity or sufficiency of a selected set. The initial provider runs in shadow
mode and preserves every block. A wider configured window does not establish wider
useful context. See [the experiment log](research/experiments.md),
[Sprint 2](SPRINT_02_BAKEOFF.md) and [the active goal](research/goal-engine-2026-10-04/PLAN.md).

[MODEL_CARD.md](MODEL_CARD.md) defines the checkpoint's actual supervision and
limits. Incident/healthy discrimination differs from LCC's KEEP relevance question;
healthy evidence can still be useful. The new direct-P1 study corrects that label
alignment but still fails its .90 quality gate (selected last-two adaptation:
mean final AUC .7145). It does not promote the compression policy.
The later tool-measurement semantic study also fails (selected mean AUC .5661
on complete pairs≤79 HF tokens). Its original numerical failure is preserved;
a separate CPU protocol and finite-update/checkpoint guards are documented.
A later22.7M ranking-pretrained MiniLM adaptation uses eight new final pair families:
selected mean pooled AUC.8279, within-objective ordering.8542 and rejection.3776.
Every seed fails; a fixed generic-report control also fails. These derivatives
remain research artifacts and are not exposed by the native ModernBERT provider.
The later supervised-data phase captured68authored fixtures with actual GNU/Python
measurements. Three completed P1+UNKNOWN adaptations all fail: mean final pooled
AUC.7332, within-goal.7338 and negative rejection.1024. They drop7/16/8 unknown
rows in Portuguese; EN/PT pooled means are.8457/.6263. Those candidates are not
adopted. See [the support study](research/goal-engine-2026-10-04/tool-role-support-v1/RESULTS.md)
and [captured-data scope](research/goal-engine-2026-10-04/tool-role-grounded-v1/RESULTS.md).
A frozen multilingual control improves the same exposed pairs to pooled.7857,
within-goal.8468 (Portuguese pooled.7428), still below.90. It has no support/DROP
authority; see [the multilingual diagnostic](research/goal-engine-2026-10-04/semantic-next/multilingual-frozen-v1/RESULTS.md).
The next data phase adds 68 new authored fixtures with 1,224 actual Retry/UDP/Git
measurements, independently audited direct-record supervision and crossed training
wording. A checked initializer preserves the pretrained ranking margin. The
subsequent three fixed adaptations all fail: mean pooled AUC .6440, within-goal
.6662, negative rejection .0883 and Portuguese rejection zero. Derived counters, diagnosis and broader
usefulness stay UNKNOWN. See [the new data and scope](research/goal-engine-2026-10-04/tool-relations-grounded-v1/RESULTS.md).
The [retained-ranking results](research/goal-engine-2026-10-04/tool-relation-support-v1/RESULTS.md)
include raw/weight audits and an exposed fit diagnosis; no candidate is adopted.
A subsequent independent-support/conditional-ranking development experiment fits
train (pooled .9763) but fails validation (.5563) and negative rejection (.0127).
It scores no new final and is rejected; see [development results](research/goal-engine-2026-10-04/factorized-relation-dev-v1/RESULTS.md).
The current data phase adds96actual authored Retry/UDP/Git fixtures with varied
termination/read/index states, bilingual reports and a connected52pair graph.
Independent raw/label/input/token audits pass:60,288/30,144development rows,
zero split overlap or truncation, maximum76projected pair tokens. The subsequent
balanced conditional development completes one seed/three finite epochs:
train/validation pooled AUC.9831/.9689, validation within-goal.9773 and negative
DROP.8105. Both development gates and independent weight/math audits pass;
validation binary UNKNOWN is.3892 and preservation counts KEEP or UNKNOWN.
All fields/tools/pair edges are known, so fresh three-seed confirmation and useful
LCC8K/32K outcomes are still required. No provider substitution or adoption.
See [measured data](research/goal-engine-2026-10-04/tool-relation-states-v2/RESULTS.md)
and [development results](research/goal-engine-2026-10-04/varied-relation-dev-v2/RESULTS.md).
Independent development seeds202/303 have now completed and passed receipt/weight
audits. The [fresh confirmation](research/goal-engine-2026-10-04/varied-relation-confirm-v1/STATE.md)
completed on64fresh authored fixtures:101unseen cross-tool pairs and52known-pair
wording controls, with every primitive still known. All three weights and cutoffs
were frozen before scoring. All three fail: pooled AUC.8502–.8703 and positive
retention.5564–.6555, with1220–1716semanticUNKNOWN DROPs perseed. The independent
audit validates receipts; no candidate is adopted. See [final results](research/goal-engine-2026-10-04/varied-relation-confirm-v1/RESULTS.md).
Saved-logit diagnosis then showed that retention-fitted global cutoffs still
reject about 35–40% of negative records while dropping semantic UNKNOWNs. A separate
one-seed, three-epoch goal-wording development pilot also fails: validation
pooled AUC .6256, within-goal .6948, negative DROP .0020, binary UNKNOWN .9980. Its independent
audit validates receipts with a preserved metadata-path erratum. This eight-field
pilot changes scope/workload jointly and supplies no independent final or LCC
outcome. See [pilot results and redirect](research/goal-engine-2026-10-04/wording-development-pilot-v1/RESULTS.md).
The subsequent [eight-field goal-only probe](research/goal-engine-2026-10-04/goal-interpreter-probe-v1/RESULTS.md)
also fails: exploratory accepted precision .1880 and UNKNOWN recognition .0982.
Its immutable recipe and receipt audits are complete; the automated MEASURED
claim gate blocks certification. No fresh confirmation or LCC utility follows.
Two later [separate support/field pilots](research/goal-engine-2026-10-04/goal-embedding-pilot-v1/RESULTS.md)
also fail. Cached-score heads have no feasible train policy; direct frozen-query
heads pass train but validation accepts70 queries with9 correct bindings and55
unsupported accepts. Exposed exploratory counts are independently recomputed;
the MEASURED claim gate blocks certification. No useful replacement is established.
The [experiment contract](research/goal-engine-2026-10-04/RELEVANCE_NEXT.md)
defines the reduced scope; the [current report](research/goal-engine-2026-10-04/REPORT.md)
records completed studies and remaining decisions.

## Install

Python 3.11+ is declared. Installed inference has been checked on Python 3.14/macOS
arm64 and Python 3.13/Linux arm64; other platforms and versions remain unverified.
See the scoped receipts in [the validation report](research/goal-engine-2026-10-04/REPORT.md).

```sh
python -m venv .venv
source .venv/bin/activate
python -m pip install '.[research]'
```

For Linux CPU deployments, install the CPU PyTorch build before the research
extra to avoid CUDA packages. The scoped Linux arm64/Python 3.13 smoke uses an
immutable CPU wheel; its recipe is saved with the validation report. The general
CPU installation route is documented by [PyTorch](https://pytorch.org/get-started/locally/).

```sh
python -m pip install torch==2.12.0 --index-url https://download.pytorch.org/whl/cpu
python -m pip install '.[research]'
```

`pip install .` installs the dependency-free native interface. The research extra
pins the ML stack used for current experiments. Checkpoints and model weights are
separate artifacts and are excluded from Git; setup is described in
[ARTIFACTS.md](ARTIFACTS.md). No checkpoint is downloaded by inference.

```python
from lcc_engine import ContextEngine

engine = ContextEngine("models/exp02e-unfreeze2", device="cpu", max_len=8192)
result = engine.rank_context(
    "Investigate payment failures",
    [{"id": "b1", "text": "payment retry exhausted; timeout_ms=30000"}],
)
```

The result includes raw logits, input hashes, actual HF pair-token counts and
artifact identity. `mode="shadow"` means all decisions are `KEEP`. Inputs exceeding
the pair window return `UNKNOWN`; they are never silently shortened. The total
dossier may contain many separately scored blocks. Its useful coverage must be
measured with LCC outcomes rather than inferred by adding capacities.

The prepared consumer integration in the local LCC checkout uses the explicit
Python request `provider="specialist", client=engine`. It calls native ranking,
records the result as `specialist_ranking`, and keeps the existing LCC deterministic
protections/sanitization. The option is shadow-only and is not a CLI/default provider
or a released upstream integration. See [examples/lcc_shadow.py](examples/lcc_shadow.py).
Decision caches and arbitrary semantic verification are refused for this shadow path.

For callers with explicit observation slots, see
[the observation API](docs/10_OBSERVATION_OPERATION.md) and the prepared
[LCC example](examples/lcc_observations.py). It keeps healthy evidence in scope,
drops only supported NO_MATCH blocks, and keeps UNKNOWN whole. A six-task exposed
synthetic LCC pilot returned 36/36 correct local-selected answers at 8K/32K with
mean 92.5%/98.1% byte removal. This supports that literal workflow; it does not
validate arbitrary diagnosis or a general Laya/Jev replacement.

## Reproduce evidence

From a checkout, these receipt audits use the standard library, archived sources
and sanitized run-local ledgers. They make no model/API calls:

```sh
python research/replay-real-2026-10-03/verify_run.py
python research/verifier-calibration-2026-10-03/verify.py
python research/pdb-routing-2026-10-04/verify.py
python research/continuation-2026-10-03/verify_completion.py
python -m research.referenced_replay_audit
```

The optional `--reexecute-oracle` PDB check rebuilds the pinned Go reference for the
current platform. It needs Go and the referenced module dependencies. Default
receipt verification checks saved reference evidence and reports that the reference
was not reexecuted. Neither file hashes nor local timestamps certify preregistration.
The training-history audit recalculates metrics from saved logits and checks archived
metadata. Its optional `--verify-weights` additionally requires the separate local
checkpoint files; neither mode reruns training.
The referenced replay audit separates quarantined contracts from executor errors,
reconciles all 62 semantic calls and preserves the historical ledger-tag defect.
New head comparisons and paired-input controls are detailed in the validation report;
their negative results keep the native provider in shadow.

The new P1 raw-score audit uses the standard library; the typed frontier audit
also needs `tiktoken` to recount dossier sizes:

```sh
python -m research.audit_relevance research/goal-engine-2026-10-04/direct-relevance-v1
python -m research.audit_observation_frontier
python -m research.audit_observation_lcc_pilot
python -m research.audit_semantic_study --out research/goal-engine-2026-10-04/semantic-tool-cpu-v2
python -m research.audit_reranker_diagnostic
python -m research.audit_reranker_projection
python -m research.audit_compact_relation_study
python -m research.audit_report_prior
python -m research.audit_tool_role_data
```

Generated Python fixture checks require a bounded Docker worker:

```sh
docker pull python:3.13-slim
python -m replay.sandbox build
python -m unittest discover -s tests -v
```

The build records the immutable base digest and current worker source hash. The
worker has no network or host mounts, a read-only root, unprivileged UID, and CPU,
memory, process and time limits. Missing or stale worker images produce `UNKNOWN`.
These controls bound fixture execution; they are not a security certification or
production ground truth. Old sources and outcomes remain archived.

## Contribute

Start with [CONTRIBUTING.md](CONTRIBUTING.md). Particularly useful contributions are
independently referenced outcome fixtures, controls against lexical shortcuts,
matched model comparisons, and measurements of latency/memory/useful context.
Keep failure results: a negative experiment can close a design choice.

Code and project-authored research fixtures use MIT. Model weights and imported
reference material retain their respective licenses; see
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). This workspace is being prepared
for its own repository; no public repository URL or published release is claimed.
