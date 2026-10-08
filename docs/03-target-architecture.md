# 03 — Target Architecture (v0)

Status: Sprint 0. Conceptual target; nothing here is final before the Sprint 2 bake-off.

## 1. Family map

```mermaid
graph TD
    subgraph LookADev umbrella
        MSI["MSI — thesis + contracts<br/>(spec repo: Task Contract, Context IR,<br/>Inference Plan, Verification Result, Receipt)"]
        LCC["LCC — context compiler / runtime<br/>(deterministic-first: clean, dedupe, budget,<br/>graph, provenance, sufficiency, restoration)"]
        MODEL["[NEW] Specialist Decision Model<br/>learned estimates only<br/>(necessity, criticality, redundancy, …)"]
        POLICY["Policy Engine<br/>external, versioned, auditable<br/>estimates -> KEEP / TRIM / DROP / routes"]
        VERIFY["Verification Layer<br/>deterministic checks + tri-state verifier<br/>(AgentTrace-derived protocol)"]
        BENCH["Benchmarks<br/>cognitive-triage-benchmark (frozen)<br/>MSI-Bench (planned) + long-context probes"]
    end

    LCC -->|"Context IR (blocks + metadata + provenance)"| MODEL
    MODEL -->|"native result schema (typed scores)"| LCC
    LCC -->|"estimates + IR"| POLICY
    POLICY -->|"selection / Inference Plan"| VERIFY
    VERIFY -->|"result + restoration requests"| LCC
    LCC -->|"receipts + outcome events"| BENCH
    BENCH -->|"outcome-backed labels"| MODEL
    MSI -.->|"contracts constrain all schemas"| LCC
    MSI -.->|"contracts constrain all schemas"| MODEL
```

Roles stay separated: LCC owns the IR, provenance and restoration; the model owns
estimates; policy owns decisions; verification owns the tri-state; benchmarks own
evidence. The model **never** replaces LCC and never writes to the context.

## 2. Model internal architecture (investigation target: long-context + block-aware + multi-task)

```mermaid
graph TD
    TASK["Task / objective text"] --> TASKREP["Task representation<br/>(typed embedding + text encoding)"]
    RAW["Raw context"] --> BLOCKS["Structured blocks<br/>Context IR units + metadata"]
    BLOCKS --> LOC["Local / window encoder<br/>per-block content tokens<br/>(local attention, O(n·w))"]
    TASKREP --> LOC
    LOC --> BREP["Block representations<br/>content + metadata embedding"]
    BREP --> GLOB["Global block-set reasoner<br/>block-level attention + task conditioning"]
    BREP --> PAIR["Pairwise relation module<br/>(experimental, E3/E4)"]
    GLOB --> H1["context heads:<br/>necessity / criticality / redundancy / uncertainty"]
    GLOB --> H2["task heads:<br/>ambiguity / complexity / risk"]
    GLOB --> H3["inference heads:<br/>model / reasoning / verification requirement"]
    GLOB --> H4["outcome head:<br/>P(success | plan) (experimental)"]
    GLOB --> SET["set heads:<br/>sufficiency / missing-evidence types"]
```

Key structural bets (each behind an ablation gate):

1. **Local-then-global attention**: token-level window attention inside blocks, then
   attention across block representations. Avoids naive O(n²) full attention at 32K/64K
   while keeping cross-block reasoning.
2. **Structure is given, not learned**: block boundaries, source, tool, order,
   protected status and dependency edges come from LCC's IR. The model learns judgments
   over structure, not structure itself.
3. **Shared backbone, typed heads**: curriculum trains heads progressively (§6);
   heads can be swapped/ablated without retraining the backbone.
4. **Uncertainty everywhere**: every head emits calibrated confidence; the policy layer
   treats low confidence as KEEP/ESCALATE.

## 3. Decision flow at runtime (LCC consumer view)

```mermaid
sequenceDiagram
    participant C as LCC compiler
    participant A as LCC adapter
    participant M as Specialist model (local)
    participant P as Policy engine
    participant V as Verifier

    C->>A: Context IR + objective (blocks, metadata)
    A->>M: native request (task rep + blocks)
    M-->>A: native result (per-block scores, set scores, uncertainty)
    A-->>C: provider-neutral decision record
    C->>P: estimates + policy version
    P-->>C: selection (kept/trimmed/dropped + rationale)
    C->>V: candidate working set
    V-->>C: PASS / REVIEW / FAIL + restoration requests
    C->>C: bounded restore from original set (never invented)
    C-->>C: report + provenance + receipt
```

Failure semantics at every arrow: missing model → mechanical fallback with
`degraded: true` and `semantic_guarantee: none` (existing LCC contract, LAYA.md §5);
failed inference keeps content; the model can abstain and the policy preserves.

## 4. Provider contract (native result, v0 draft)

Provider-independent; LCC adapts it to `relevance-compaction-1.2` decisions:

```json
{
  "schema_version": "lookaspecialist-result/0.1",
  "model_version": "name-tier-ckpt",
  "config_version": "encoder-heads-...",
  "blocks": {
    "blk_0001_ab12cd": {
      "necessity": 0.94,
      "criticality": 0.77,
      "redundancy": 0.04,
      "uncertainty": 0.03
    }
  },
  "global": {
    "context_sufficiency": 0.91,
    "task_complexity": 0.65,
    "task_ambiguity": 0.30,
    "task_risk": 0.12
  },
  "abstained": ["blk_0007_..."]
}
```

Policy (external) turns this into KEEP/TRIM/DROP. Illustrative (thresholds are policy,
not truth): `necessity 0.20 / criticality 0.10 / uncertainty 0.05` may DROP on a low-risk
task, while `necessity 0.20 / criticality 0.80` must KEEP.

## 5. Training curriculum (staged; each stage gates the next)

| Stage | Learns | Supervision | Gate to proceed |
|---|---|---|---|
| 1 Domain representation | code, diffs, tests, logs, stack traces, tool traces, transcripts, JSON/YAML/MD, issues, PRs, config | self-supervised / continued pretraining | representation probes beat frozen generic encoder |
| 2 Task ↔ context | relevance, source relations, duplicates, dependencies, contradictions, supersession | teacher labels (curriculum only) + deterministic graph | B1/B4/B5 beat baselines |
| 3 Context necessity | necessity, criticality, redundancy | **outcome-backed ablation labels** | beats relevance-only training (H3 test) |
| 4 Set-level sufficiency | sufficiency, missing-evidence types, drop-induced gaps | paired set replay | S1 calibration usable (ECE gate) |
| 5 MSI decisions | complexity, risk, model/reasoning/verification requirement | multi-config replay + triage ground truth | false de-escalation under ceiling |
| 6 Outcome prediction | P(success \| candidate plan) | outcome receipts | only if 5 produced trustworthy data |

Overengineering gates (prompt §42): if the block-aware hierarchy does not beat a simple
pair scorer, simplify before adding more hierarchy; if 32K gives no measurable gain over
8K on the probes, diagnose before pursuing 64K.

## 6. Backbone tracks (decision deferred to Sprint 2)

| Track | What | When it wins |
|---|---|---|
| A — existing encoder baseline | ModernBERT-class / Laya / other encoders + heads | if frozen/fine-tuned encoders already reach effective 32K with good calibration |
| B — adapted long-context encoder | continued pretraining + position extension + block-aware input layer | likely sweet spot: proven representations + our structure |
| C — native model | small, long-context, block-aware, multi-task from scratch | only if A/B cannot use >8K effectively at 30–150M |

All three are compared on the same frozen benchmark (05). The current local evidence
(Laya fine-tune: memorization, 1024-token ceiling) argues against naive Track A and for
testing Track B first — but the bake-off decides, not the preference.

## 7. Where each piece lives (target repo boundaries)

```text
[NEW REPO] (name pending — see 06)     model weights, training pipeline, datasets,
                                       benchmark lifecycle, export pipeline
LCC                                    consumes model via provider/adapter only
minimum-sufficient-inference           schemas/contracts only (read-only upstream)
cognitive-triage-benchmark             frozen triage evaluation set (read-only)
agenttrace-studio                      verification protocol source (extract, no import)
```

No repository is created until the architecture decision (Sprint 1–2) — hypothesis:
`lucasmartins-ai/[chosen-name]`, separate from LCC because it owns weights, training
and dataset lifecycle.
