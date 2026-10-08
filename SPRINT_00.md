# SPRINT_00 — Discovery complete (2026-10-02)

Scope: discovery only. **No model was trained.** Deliverables:

| Doc | Content |
|---|---|
| [docs/00-vision.md](docs/00-vision.md) | mission, hypothesis (H1–H4), family map, what exists today |
| [docs/01-decision-taxonomy.md](docs/01-decision-taxonomy.md) | task taxonomy + 30+ decisions across 5 levels + training-target taxonomy |
| [docs/02-model-requirements.md](docs/02-model-requirements.md) | MUST / SHOULD / EXPERIMENTAL requirements |
| [docs/03-target-architecture.md](docs/03-target-architecture.md) | Mermaid family map, model internals, runtime flow, provider contract, curriculum, backbone tracks |
| [docs/04-dataset-strategy.md](docs/04-dataset-strategy.md) | dataset families, outcome-backed supervision, record schema, leakage rules |
| [docs/05-benchmark-strategy.md](docs/05-benchmark-strategy.md) | 8 baselines, context/long-context/MSI metrics, protocol rules |
| [docs/06-naming-study.md](docs/06-naming-study.md) | 48 candidates, scoring, shortlists, collision research |
| [docs/07-risk-register.md](docs/07-risk-register.md) | 20 risks with signals and mitigations |
| [docs/08-roadmap.md](docs/08-roadmap.md) | Sprints 0–10 with gates |
| [docs/09-open-questions.md](docs/09-open-questions.md) | research, taxonomy, architecture, data and decision questions |

---

## WHAT WE KNOW (facts, measured or implemented)

1. **Relevance ≠ necessity** is already a working distinction in MSI/LCC: labels
   `NECESSARY … UNKNOWN` default UNKNOWN; theory.md scopes minimality to a recorded
   executor + policy + dataset version.
2. **The local fine-tune failed exactly where it matters**: `laya-lcc-relevance-v1`
   (frozen Laya encoder + trained head, 7,760 items) memorized the corpus factory —
   100% category recall in-domain, **6/6 false drops (critical recall 0.0)** on an
   independently worded ablation corpus. In-domain numbers must never be quoted
   without an OOD gate.
3. **Context window is the binding constraint today**: Laya's 512/1024-token state
   budget leaves 40/77 blocks of a real 66K-token session unjudgeable; real-session
   reduction is 0.0%. Jev (remote, 32K) reaches −52% reduction at 100% category recall
   but still makes real false drops (2/12 ablation blocks) and costs money.
4. **The safety net works**: LCC's deterministic + structural layers remove 3 real
   false-drop classes and cut judge-error false drops from 66% to 15% (measured
   2026-10-02, mechanism ablation). Any learned judge plugs in *behind* these layers.
5. **The contracts exist**: MSI spec v0.1 (Task Contract, Context IR, Inference Plan,
   Verification Result, Inference Receipt) and the deterministic planner
   (`plan.py`, ADR-0019) with the `(decision, conf, risk) → route` triage gate are
   already implemented; the specialist only has to estimate, never decide.
6. **MSI economics are proven at the triage level**: hybrid System-1-first routing
   eliminated 58.2% of frontier calls at no significant quality loss (1,200 frozen
   transactions, LOOKADEV-TR-2026-004) — the "specialized small judge wins" thesis has
   one confirmed instance already.
7. **Naming space is open**: `lookascope` and `lookagauge` are unclaimed across Google,
   GitHub, Hugging Face, PyPI and npm (checked 2026-10-02).

## WHAT WE ASSUME (unproven)

- A1: 32K+ *useful* context is achievable in a 30–150M model with block-aware
  attention on CPU-class hardware (M8 latency budget).
- A2: Outcome-backed remove-and-replay labels can be produced at acceptable cost and
  with acceptable label reliability (R19 is untested).
- A3: Necessity is learnable at all from static (task, context) pairs — some necessity
  may be executor-dependent and only exist at the (task, context, plan) level.
- A4: The block structure LCC already computes is the right inductive bias (vs flat
  sequences).
- A5: Sufficiency prediction (S1) is possible well enough to be useful, not perfect.
- A6: Demand exists beyond LCC (the model is worth its own repo/weights lifecycle).

## WHAT WE NEED TO TEST (experiments before any serious training investment)

1. **Replay pilot** (20 tasks): cost per reliable ablation label; repeat-ablation
   agreement (decides whether D6 is viable — biggest single risk after R2).
2. **Encoder bake-off** (Sprint 2): effective-context utilization curves 2K…32K for
   Laya-lineage / ModernBERT-class / long-context encoders on CPU.
3. **H3 experiment design**: outcome-backed vs relevance-only labels, same backbone.
4. **Long-context probe suite construction + baseline runs** (Jev included — it becomes
   the effective-context reference curve).
5. **Tokenizer study** (E1): custom vs existing on tokens/byte, tokens/code-line,
   effective-context gain.
6. **Batch/granularity semantics**: the batch-1-vs-batch-8 behavior change in Laya
   suggests decision heads are granularity-sensitive — verify on candidate encoders.

## NAME SHORTLIST (final 5; full study in docs/06) — DECISION DEFERRED

Founder decision (2026-10-02): no name is chosen until training gives the model its
real dimension. Working title in code/datasets: `specialist`. Shortlist stays open:

1. **LookaScope** (recommended) — instrument you look through to see what a task needs;
   family-perfect; CLEAR collision profile; `LookaScope-Tiny/Base/Large`.
2. **LookaGauge** — gauges how much context/intelligence a task needs; CLEAR.
3. **Suffice** — the MSI thesis in one word; MINOR (generic word).
4. **Modicum** — small but sufficient intelligence; MINOR.
5. **LookaLens** — focus metaphor; MINOR (camera-lens social brand).

No name is frozen: freeze requires the founder's decision + registry sweep (06 §5).

## ARCHITECTURE RECOMMENDATION (this moment)

- **Long-context + block-aware + multi-task** remains the investigation target
  (local window attention → block representations → global block-set reasoner → typed
  heads), but with a hard discipline: each structural piece must beat its simpler
  ablation or be cut (docs/03 §5, docs/07 R12).
- **Runtime**: model emits typed probabilities via a provider-independent native
  schema; LCC adapter + external policy make all KEEP/TRIM/DROP and routing decisions;
  ABSTAIN → preserve; all existing deterministic safety layers stay on.
- **Curriculum**: representation → task↔context → necessity → sufficiency → MSI →
  outcome (docs/03 §5), gated per stage.

## BUILD VS ADAPT (evidence-based)

**Adapt first (Track B).** Evidence:

- Naive Track A is already falsified in-house: frozen generic encoder + head memorized
  and failed OOD (fact 2 above).
- But the failures are attributable to (i) training data design and (ii) the 1024-token
  window — not to the encoder-representation approach itself. The vendor's own position
  is that Laya is "a fast base to specialise", and raising max_len is "a more promising
  lever than another training run" (LAYA.md §8).
- Nothing yet shows that a from-scratch model (Track C) is required; no measured gap
  currently points at architecture as the bottleneck.

Decision rule (pre-registered): **Track B (continued pretraining + position extension +
block-aware input layer) is the primary path through Sprint 3.** Track C is built only
if the Sprint-2 bake-off shows no existing encoder can use ≥16K effectively at the
parameter/latency budget. From-scratch is a conclusion, not a preference.

## NEXT SPRINT (Sprint 1 — max 8 tasks)

1. Freeze `lookaspecialist-result/0.1` + `looka-dataset-record/0.1` schemas and the
   LCC provider/adapter contract (against LCC `ir.py` + MSI Context IR).
2. Build the remove-and-replay pilot harness; run 20 tasks; measure cost/label and
   repeat-ablation agreement (R19 gate).
3. Freeze MSI-Bench v1 + long-context probe suite (frozen by content hash).
4. Run + archive baselines BL1–BL4 under the unified protocol (mechanical, Laya,
   laya-lcc-relevance-v1, Jev).
5. Build the BL5 harness (generic encoder + linear heads) and the bake-off protocol.
6. Corpus-factory v2 design: programmatic facts with noisy tails, paraphrase families
   (the anti-memorization redesign from docs/04 §1).
7. Experiment-log + `research/failures.md` skeleton in the target repo layout
   (docs/, research/, adr/ per prompt §37).
8. Founder decisions queued: compute ceiling for S2–S3, real-trace data policy
   (docs/09 §E). Name decision deferred to post-training.

---

## Final note (the honest frame)

The goal of this program is not to ship a model. It is to test whether a class of
small, long-context, decision-oriented specialist models can learn **how much context
and intelligence a task actually needs** — and to measure that, believe it, or discard
it with evidence. Sprint 0 produced no trained weights, only sharper questions,
working contracts, and two already-measured reasons (memorization; window ceiling) to
think the hypothesis is alive.
