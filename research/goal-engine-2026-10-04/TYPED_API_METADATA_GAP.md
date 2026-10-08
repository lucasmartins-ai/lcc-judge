# Typed API metadata gap

Scope: explains the PLAN.md sentence "A API tipada ainda exige metadados ausentes
nos registros atuais". Offline inspection only. No inference, no relabeling, and
no code or receipt changes.

## Which API

`lcc_engine/observations.py`: `ObservationRequest` + `ObservationEngine.rank_observations`
(schema `lcc-observation-ranking/0.1`). Source: finding 5 in
[semantic-goal-review-v1/REVIEW.md](semantic-goal-review-v1/REVIEW.md) and REPORT.md
("The existing typed API requires source/time metadata that the pilot records lack").

## Required fields

| Side | Field | Constraint |
| --- | --- | --- |
| Request | `entity` | `[A-Za-z0-9][A-Za-z0-9_.:/-]{0,127}` |
| Request | `field` | `[A-Za-z][A-Za-z0-9_]{0,127}` |
| Request | `start`, `end` | UTC `YYYY-MM-DDTHH:MM:SSZ`, start <= end |
| Record (JSON) | exactly `time, level, entity, field, value, unit` | `time` UTC as above; `level` in INFO/WARN/ERROR/DEBUG/TRACE; finite number; unit regex |
| Record (text) | three line grammars | each carries the same six slots |

A block that fails the grammar stays `UNKNOWN` / `KEEP`.

## What current records carry

Records come from `wording-development-pilot-v1/{train,validation}.jsonl.gz`: 16,704 rows
(8,448 JSON and 8,256 prose). Their measurements come from `tool-relation-states-v2`
captures.

| Required | Pilot record (`text`) | Derivable deterministically? |
| --- | --- | --- |
| `entity` | present (`tool-<12 hex>`) | yes, as-is |
| `level` | present (INFO/WARN/ERROR) | yes, as-is |
| `value` | present (int) | yes, as-is |
| `field` | absent; record has prose `measurement` caption | Technically yes. The 144 captions map one-to-one to 18 fields through `research/tool_relation_contracts.py` (0 ambiguous captions across all 16,704 rows). But that table is the benchmark generator's caption registry, and REVIEW.md forbids copying canonical bindings from dataset or generator labels into prose. The field also sits in the row's `binding`, which is supervision-only. Using either would be relabeling. |
| `unit` | absent | Same source as `field` (the contract table or `binding.unit`), with the same objection. |
| `time` | absent | **No.** The raw captures (`tool-relation-states-v2/*/raw.json`) record only monotonic `perf_counter_ns` values and tenacity `start_time` (monotonic seconds). The only wall-clock values are run-level receipt timestamps (`finished_at_utc`), not per-observation times. CONTRACT.md says "No UTC is inferred from monotonic clocks". |
| Request `start`/`end` | absent; goals carry only question + entity | **No.** No observed UTC window exists. |

Current behavior is already safe: `compatibility-probe.json` (PASS) passes all 5,568
validation rows through one literal request with a synthetic UTC range. All rows stay
UNKNOWN and none are dropped. An "explicit UNKNOWN adapter" would therefore add nothing.

## Verdict

The gap cannot be closed from existing data without fabricating timestamps (`time`,
`start`/`end`). Deriving `field`/`unit` from the caption registry is mechanically possible.
It is out of contract because it amounts to label leakage, and it is useless anyway
while `time` is missing. No code was changed.

## Concrete next step (needs new data or a design decision, not a patch)

Pick one, decided by a human before any new run:

1. **Producer-side metadata:** have the trusted capture worker emit, per observation, a
   wall-clock UTC timestamp read from the system clock at capture time (not converted from
   monotonic), plus canonical `field`/`unit` from the collector's own schema. Then re-capture
   on a new frozen cohort. Existing receipts stay untouched.
2. **Scoped request variant:** add a separate, explicitly versioned request type keyed by a
   declared capture/instance scope instead of a UTC window, as REVIEW.md proposes.
   `ObservationRequest` stays unchanged. It still needs canonical `field`/`unit` from a
   genuine collector schema, not from prose captions.

Out of scope here: the separate deferred "start/load" metadata gap in the support pilot
(`research/audit_goal_pilot_metadata.py`, `audit-metadata-v2.json`). It is unrelated to
this API.
