# 00 — Vision: the LookADev Specialist Decision Engine (working title)

Status: Sprint 0 (discovery). No training has started. This document states what the
component is, what it is not, and how it relates to MSI and LCC.

## 1. The question MSI asks

> What is the minimum amount of context, model capacity, reasoning, tooling and
> verification required to preserve a desired task outcome?

Formal sketch (cost minimization under outcome constraints):

```text
min Cost(C, M, R, T, V)

subject to:
  P(success | task, C, M, R, T, V) >= quality_threshold
  P(error_or_unsafe | task, C, M, R, T, V) <= risk_threshold
```

To solve this optimization at runtime, someone must *estimate* the terms: how much
context a task needs, how hard it is, how risky it is, and what execution plan will
succeed. That estimation problem is the new component's job.

## 2. What the new component is

A small, local, long-context, block-aware, decision-oriented model that produces
**calibrated estimates**, not prose. Its verb set is:

```text
OBSERVE  ESTIMATE  RANK  CLASSIFY  ALLOCATE  ABSTAIN
```

It does **not** generate long natural language, does **not** execute tasks, and does
**not** make policy decisions. It estimates probabilities; an external, configurable,
auditable policy turns estimates into KEEP/TRIM/DROP or routing choices.

Core principle:

> The model does not perform general intelligence. It helps the system decide where
> intelligence is actually necessary.

## 3. The hypothesis under test

> A small model specialized for context-compilation and inference-allocation
> decisions, with native access to much more *useful* context, can beat much larger
> general-purpose models on this narrow decision problem.

Specifically, whether this combination wins:

```text
specialization + long useful context + block-aware architecture
+ task-conditioned reasoning + outcome-backed supervision
```

over:

```text
general-purpose model + shorter effective context + generic relevance training
```

Sub-hypotheses (each falsifiable independently):

- H1: context relevance and context necessity are distinct learning problems.
- H2: agent context is naturally block structured; architectures exploiting this
  structure process substantially longer useful contexts at lower cost.
- H3: outcome-backed labels (remove-and-replay) beat relevance-only labels for
  training necessity judgments.
- H4: specialized decision models can allocate context and inference more
  efficiently than general-purpose models because the decision problem is
  narrower than the execution problem.

If the evidence does not support these, we document that and stop. The goal is not
"ship a model"; it is "discover whether a new class of specialist model exists".

## 4. What already exists (repository relationships, verified 2026-10-02)

| Project | What it gives us | Status |
|---|---|---|
| `LCC` (`~/LCC`) | deterministic-first compiler/runtime: blocks, provenance, typed graph (`relationships-1.0`), sufficiency + bounded restoration, decisions cache, report schema `relevance-compaction-1.2`, deterministic inference planner (`plan.py`, ADR-0019), provider abstraction (mechanical/laya/jev) | implemented, 283+ tests |
| `minimum-sufficient-inference` (`~/msi-repos/`) | MSI spec: Task Contract, Context IR, Inference Plan, Verification Result, Inference Receipt schemas; theory (necessity ≠ relevance, fail-closed); research agenda + methodology | spec-only, v0.1 |
| `LCC/docs/msi/` | capability map, sprint history (1–4 done), MSI spec draft, risk register | living docs |
| `cognitive-triage-benchmark` | frozen 1,200-transaction triage set, break-even escalation theorem, asymmetric loss framing, `(decision, conf, risk) -> route` gate used by the planner's jev-adapter | benchmark + paper (LOOKADEV-TR-2026-004) |
| `agenttrace-studio` | CI quality gate protocol: 9 checks, citation auditor, PASS/REVIEW/FAIL tri-state | extraction source for verification protocol |
| `agentic-prompt-intake` | intake/readiness spec (3 states) | merge-as-spec candidate with LCC `intake/` |
| `lcc-act2-router` | strict subset of LCC pipeline | archive candidate |
| `~/Models/laya-lcc-relevance-v1` | the local fine-tune of Laya (encoder frozen + decision head, 7,760 items, 4 epochs MPS) | measured, failed OOD (see below) |

**Critical empirical findings already in hand** (from `LCC/docs/LAYA.md` §8, measured
2026-09-23 with real weights):

1. A frozen general encoder + trained decision head **memorizes** the corpus factory
   (100% category recall in-domain) and **fails out-of-distribution** (6/6 false drops
   on an independently worded judge-ablation corpus, critical recall 0.0).
2. Context window is the binding constraint: Laya's 512/1024-token state window means
   40/77 blocks of a real 66K-token session are unjudgeable and kept whole; real-session
   reduction is 0.0%.
3. Jev (remote, 32K) is a strong judge but makes real false drops on the 12-block
   ablation corpus — individual drops are not safe by construction — and costs money
   and network availability.
4. Batching changes semantics: batch>1 makes keep-everything behavior; batch 1
   separates evidence from noise.

These four facts are the strongest existing evidence for the new component: we need
(a) long *useful* context, (b) training that generalizes past the data factory,
(c) local/cheap inference, (d) necessity labels, not just relevance labels.

## 5. What the component is not

- Not a generative LLM and not a summarizer (LCC never rewrites bytes).
- Not a replacement for LCC. LCC stays the compiler/runtime, IR owner, provenance
  owner, restoration owner. The model is one advisory source behind a provider
  adapter.
- Not a policy engine. Thresholds (`0.5 = DROP`) live in the policy layer, never in
  the weights. Same estimate can mean DROP or KEEP depending on risk class.
- Not a "judge of answers". Its unit of judgment is the *context unit / task / plan*,
  not prose quality.

## 6. Fail-safe doctrine (non-negotiable)

```text
uncertain              -> preserve (ABSTAIN -> KEEP)
insufficient           -> restore
verification failure   -> retry or escalate
```

Never `uncertain -> drop`. Abstention is a first-class typed output, not an error.

## 7. Relationship to LCC/MSI/Jev/Laya

```text
LookADev                       umbrella brand
  ├── MSI                      thesis + contracts (spec repo)
  ├── LCC                      context compiler/runtime (deterministic-first)
  ├── [NEW]                    learned decision engine (estimates only)
  ├── Jev (TypeSafe)           remote typed judge — teacher/baseline, not ground truth
  ├── Laya (Convai)            local encoder baseline — bake-off track A
  └── benchmarks               cognitive-triage-benchmark, MSI-Bench (planned)
```

Integration path: model emits its **native result schema** → LCC adapter → LCC
decision policy → (optional) Inference Receipt. Core schemas never name providers
(MSI ADR discipline). Jev/Laya remain swappable behind the same provider interface.

## 8. Long-term horizon (staged, not promised)

```text
Context Necessity Model
      -> Sufficiency Model
      -> Inference Requirement Model
      -> Outcome Predictor: P(success | task, context, candidate plan)
```

Only the first rung is in scope for sprints 3–4. Each next rung requires measured
justification from the previous one.

## 9. Success definition

Not "maximum compression". The principal metric is:

> minimum resource usage **at matched outcome quality**.

An interesting (not promised) result would be a ~75M specialist with 32K/64K useful
context beating a 150–350M general model with 8K context on critical recall, context
reduction, OOD generalization, latency and memory. Numbers will come from experiments,
not from marketing.
