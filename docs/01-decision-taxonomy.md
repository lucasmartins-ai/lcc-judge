# 01 — Decision Taxonomy (v0)

Status: Sprint 0. Purpose: fix *which decisions exist* before deciding which to learn.
Each decision records: input, output, ground-truth source, training feasibility,
evaluation feasibility, and the risk of getting it wrong.

Conventions inherited from MSI spec v0.1 (see `~/msi-repos/minimum-sufficient-inference`):
- Necessity labels: `NECESSARY UNNECESSARY CONDITIONALLY_NECESSARY REDUNDANT PROTECTED UNKNOWN` (default `UNKNOWN`).
- Relationship enum: `SUPPORTS QUALIFIES CONTRADICTS SUPERSEDES DEPENDS_ON DUPLICATES DERIVED_FROM`.
- Verification: `PASS | REVIEW | FAIL` tri-state, fail-closed.
- Relevance ≠ necessity: relevance ranks; necessity states whether removal changes the outcome.

Risk scale for incorrect predictions: **CATASTROPHIC** (silent wrong answer / unsafe),
**HIGH** (task failure or wasted frontier call), **MEDIUM** (efficiency loss),
**LOW** (cosmetic).

## 0. Task taxonomy (what tasks the decisions serve)

Drawn from MSI Task Contract `task_type` plus observed LCC workloads:

| Task class | Example | Signature signals |
|---|---|---|
| coding | fix bug, add feature, refactor | files, diffs, tests, stack traces |
| debugging | reproduce + diagnose | logs, failing tests, hypotheses |
| investigation | why did X happen | evidence chains, timestamps, contradictions |
| research | gather + synthesize | sources, citations, long documents |
| multi_tool | agent session with tool traces | tool calls, tool outputs, transcripts |
| structured_decision | triage, routing, review | candidate options, criteria, risk |
| long_running | deploy, migration, monitoring | logs over time, state checkpoints |
| other | mixed/unclear | high ambiguity signal |

## 1. Block-level decisions (per context unit)

Unit = one verbatim Context IR block with id, source, provenance.

| ID | Decision | Input | Output | Ground truth source | Train feas. | Eval feas. | Risk if wrong |
|---|---|---|---|---|---|---|---|
| B1 | relevance to objective | objective + block | score 0–1 | existing LCC/Jev/Laya labels (weak); teacher labels | HIGH (7,760+ items exist) | HIGH | LOW (rank only) |
| B2 | **necessity** | objective + block + set | P(necessity) + label incl. UNKNOWN | remove-and-replay ablation (outcome delta) | MEDIUM (needs replay infra) | HIGH (paired before/after) | **CATASTROPHIC** if false drop |
| B3 | criticality | objective + block + set | P(critical) | ablation: outcome *degrades to failure* when removed | MEDIUM | HIGH | CATASTROPHIC |
| B4 | redundancy | block + set (candidates) | P(redundant), dup target | DUPLICATES edges + ablation (removal changes nothing) | MEDIUM | HIGH | LOW–MEDIUM (over-drop risk if misused) |
| B5 | dependency | block pair/set | typed edge (enum above) | LCC `graph.py` deterministic links (DISTINCTIVE_TERM, quoted, path); curator labels | MEDIUM | MEDIUM | HIGH (severed dependency = wrong answer) |
| B6 | contradiction | block pair | P(CONTRADICTS) | curated contradiction fixtures; receipts of failed tasks | LOW–MEDIUM (scarce) | MEDIUM | HIGH |
| B7 | supersession | block pair + order | P(SUPERSEDES) | version/history metadata (git, timestamps) + curator | MEDIUM | MEDIUM | MEDIUM |
| B8 | protection requirement | block + policy | P(protected) | LCC deterministic protection rules (quoted speech, cross-language, high-risk) — labels already exist | HIGH | HIGH | HIGH |
| B9 | per-block uncertainty | block + set | calibrated uncertainty / abstain | calibration set (temperature fit as in `laya-lcc-relevance-v1`) | HIGH | HIGH (ECE, reliability curves) | MEDIUM (abstention is safe) |
| B10 | out-of-window judgeability | block length + budget | P(usable) / flag | deterministic (tokens vs window) — **should stay deterministic** | n/a | n/a | LOW |

Notes:
- B10 is listed to keep it *out* of the model: token-count vs window is exact math and
  belongs to LCC (already implemented: `laya_context_limit_exceeded`).
- B2/B3 are the crown jewels: only outcome-backed replay gives ground truth. Teacher
  labels (Jev/Laya) may bootstrap (curriculum) but never serve as evaluation truth.
- B8 already has trustworthy deterministic labels — useful as cheap auxiliary supervision.

## 2. Set-level decisions (over the whole working set)

| ID | Decision | Input | Output | Ground truth source | Train feas. | Eval feas. | Risk if wrong |
|---|---|---|---|---|---|---|---|
| S1 | **context sufficiency** | objective + candidate set | sufficient bool + missing-evidence list + confidence | replay: does the set reproduce baseline outcome? + LCC `verify_sufficiency` structural signals | MEDIUM | HIGH (paired) | CATASTROPHIC (silent gap) |
| S2 | which drops created insufficiency | selection record + failure | ranked restored candidates | restoration events in reports (`blocks_restored` ledger) | MEDIUM | HIGH | HIGH |
| S3 | set-level redundancy | full set | collapse candidates | ablation on groups (remove dup cluster) | MEDIUM | MEDIUM | LOW |
| S4 | information coverage gaps | objective + set | missing-evidence types | curator annotation + failure postmortems | LOW–MEDIUM | MEDIUM | HIGH |
| S5 | context budget fit | set + target budget | feasibility / trim plan | deterministic token counts | n/a (deterministic) | n/a | LOW |

## 3. Task-level decisions

| ID | Decision | Input | Output | Ground truth source | Train feas. | Eval feas. | Risk if wrong |
|---|---|---|---|---|---|---|---|
| T1 | task ambiguity | objective text (+ intake state) | score 0–1 | intake readiness states (agentic-prompt-intake + LCC `ReadinessState`), curator labels | MEDIUM | MEDIUM | MEDIUM |
| T2 | task complexity | objective + context profile | score 0–1 / class | proxy: baseline agent cost (tokens, steps, retries) on replayed tasks | MEDIUM | MEDIUM | MEDIUM |
| T3 | task risk class | objective + policy | low/medium/high/unknown | MSI Task Contract `risk_level`; triage-benchmark ground truth (1,200 frozen) | MEDIUM | HIGH | **CATASTROPHIC** (under-classified risk) |
| T4 | required capabilities/tools | objective | capability set | Task Contract `required_capabilities` / `allowed_tools` | MEDIUM | HIGH | HIGH |
| T5 | external knowledge need | objective + set | bool + topic | curated tasks (LCC `requires_external_knowledge` markers exist) | HIGH | HIGH | MEDIUM |

## 4. Inference-level (MSI) decisions

| ID | Decision | Input | Output | Ground truth source | Train feas. | Eval feas. | Risk if wrong |
|---|---|---|---|---|---|---|---|
| I1 | model requirement (local_tiny→frontier) | task + context profile | class + confidence | replay: cheapest config that passes verification per task | LOW–MEDIUM (needs multi-config replay) | HIGH | HIGH (**false de-escalation** = wrong answer; over-escalation = cost) |
| I2 | reasoning budget | same | none/low/medium/high | replay across reasoning budgets | LOW | HIGH | MEDIUM |
| I3 | tool requirement | same | tool set | replay with/without tools | LOW | MEDIUM | MEDIUM |
| I4 | verification requirement + type | task + plan | strict/standard/light + checks | replay: which verification caught real failures | LOW | HIGH | HIGH |
| I5 | restoration requirement | sufficiency result | budget estimate | restoration ledgers in existing reports | MEDIUM | HIGH | MEDIUM |
| I6 | retry/escalation requirement | task + risk | P(retry), P(escalate) | cognitive-triage-benchmark escalation ground truth | MEDIUM | HIGH | HIGH (escalation miss ceiling ≤2% precedent) |
| I7 | P(success \| candidate plan) | task + set + plan | calibrated probability | outcome receipts from multi-config replay (Stage 6 only) | LOW (data expensive) | HIGH | HIGH |

I1–I7 are deliberately last in the curriculum: no reliable multi-config outcome data
exists yet. Sprint 8 gate: "only if there are trustworthy datasets".

## 5. Outcome-level decisions

| ID | Decision | Input | Output | Ground truth source | Train feas. | Eval feas. | Risk if wrong |
|---|---|---|---|---|---|---|---|
| O1 | outcome degradation on unit removal | baseline outcome + ablation outcome | delta + label (NECESSARY/UNNECESSARY/CONDITIONAL/REDUNDANT/CRITICAL/UNKNOWN) | the remove-and-replay harness itself — this is the *source* of B2/B3 labels, not a head | n/a (harness) | n/a | n/a |
| O2 | verification-result prediction | plan + task | P(PASS/REVIEW/FAIL) | verification results ledger | LOW | HIGH | MEDIUM |
| O3 | final task success | receipt | bool/graded | receipts: tests pass, verifier PASS, human review | MEDIUM | HIGH | CATASTROPHIC if gamed |

## 6. Training-target taxonomy (what supervision each level uses)

| Supervision | Source | Serves | Trust tier |
|---|---|---|---|
| deterministic structure | LCC graph/protection/token counts | B5, B8, S5 | T1 (exact) |
| outcome-backed ablation | remove-and-replay harness | B2, B3, S1, O1 | T1 (primary truth) |
| behavioral replay cost | multi-config task execution | T2, I1–I7 | T2 (noisy but real) |
| teacher soft labels | Jev / larger LLM judgments | B1, B4, S3 curriculum only | T3 (never eval) |
| curated human labels | practitioner annotation | B6, T1, T3, S4 | T2 |
| derived event labels | restoration ledgers, receipts | S2, I5, O2 | T2 |

Rule (MSI methodology): training signal and evaluation ground truth never come from the
same generator. Teacher imitation is never the evaluation.

## 7. Sequencing recommendation

1. **Learn first**: B2, B3, B4 (necessity/criticality/redundancy) — highest value for LCC,
   outcome-backed labels feasible now, risk mitigated by fail-closed policy.
2. **Then**: S1 (sufficiency) — needs paired set-level replay.
3. **Then**: T1–T3 and I1–I6 behind dataset gates.
4. **Last**: I7 / O2 (plan-level success prediction) — the research frontier, not a promise.

## 8. Open taxonomy questions (tracked in 09)

- Is CONDITIONALLY_NECESSARY predictable from the (block, set) pair, or does it require
  task-state features?
- Does B3 (criticality) differ enough from B2 (necessity) to justify separate heads, or
  is it the tail of one distribution? (Ablation: shared vs separate heads.)
- Should S1 output *typed* missing-evidence categories (from a closed enum) instead of
  free text? (Typed keeps the model non-generative — likely yes.)
