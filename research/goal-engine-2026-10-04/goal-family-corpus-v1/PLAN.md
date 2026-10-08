# Goal family corpus v1 — design and contract (no data, no fit yet)

Status 2026-10-08: design only. No row was authored, no encoder forward, fit or
API call was made for this file. It records decisions that must be fixed before
any of those happen, including the stop criterion. Inputs read:
goal-interpreter-probe-v1 (zero-shot router, 197/240 correct direct bindings,
808/896 unsupported accepted), goal-support-pilot-v1 (no feasible train policy),
goal-embedding-pilot-v1 + INDEPENDENT_REVIEW (train PASS, validation 9/70),
varied-relation-confirm-v1 (three seeds rejected; immutable scalar shadow pooled
.874211 / within-goal .899835, retention 1.0, zero UNKNOWN DROPs) and
observation-lcc-pilot (explicit `rank_observations` route 36/36, 92.50%/98.10%
mean byte removal at 8K/32K on six exposed authored tasks).

## 1. Objective and targets (unchanged)

Map a complete natural goal question to one registered field/unit, or UNKNOWN.
Registry: the eight fields in goal-interpreter-probe-v1/CONTRACT.md and
registry.json plus its four unsupported kinds, unchanged. Gates, aggregate AND
separately for EN and PT, on the same definitions as the predecessor pilots:

- accepted precision >= .99 (wrong-field and unsupported acceptances are errors);
- correct supported coverage >= .80;
- UNKNOWN recognition >= .95 (semantic and out-of-registry UNKNOWN combined,
  both also reported separately).

No gate, threshold, label or definition of any rejected experiment changes.
Point gates decide; a rule-of-three upper error bound is reported beside every
precision (zero errors in n accepted gives roughly 3/n), so a pass on fewer than
300 accepted items per language is labelled "point pass, bound not reached".
At the planned confirmation size this label is expected; reaching the bound
needs a larger confirmation population, not a looser gate.

## 2. Population contract

- Unit of independence is the **family**: one underlying goal (field+unit, or one
  UNKNOWN kind) with every rendering of it. Family IDs are opaque, assigned
  before text is written, and never derived from text.
- Each family holds EN and PT renderings, >= 2 paraphrases per language, all in
  the same split. Translations never cross splits.
- Shared surface frames: every supported family has a sibling unsupported
  family built on the same frame (e.g. "how many X did the retry loop ..." with a
  derived/diagnostic/broad/out-of-registry X). Sibling pairs share a split.
- Field/unit contrast families target the known confusions: scheduled vs actual
  sleep, attempts vs failures, datagrams vs payload bytes, index vs worktree.
- Ambiguous, negated or underspecified requests are labelled UNKNOWN, never
  resolved to the likelier field.
- Minimum size: 400 families (160 supported = 20 per field, 160 sibling
  unsupported = 40 per kind, 80 contrast/ambiguity). About 8 queries per family.
- Split by family with a seeded hash, stratified by field/kind and provenance:
  train 50% / calibration 15% / validation 15% / future confirmation 20%.
  Split manifest (family IDs, query SHA-256s, seed) is hashed and frozen
  **before any fit**. Confirmation text stays sealed (hash-only receipt) until
  candidate weights and thresholds are locked.
- Zero literal overlap with all exposed populations (wording pilot 1,172/1,136,
  varied-relation finals). Exposed data stays diagnostic only.
- Fixed control: the original zero-shot router's 197/240 correct direct
  decisions on exposed validation is a frozen reference; on the new families the
  same frozen router (no refit, no definition change) is scored once as the
  in-population control. Support improvement is measured against it, never by
  trading away correct bindings.

## 3. Provenance

Every query carries `provenance`: `authored` (author, date, template/frame ID)
or `genuine_lcc` (collection receipt ID). Metrics are reported per provenance;
authored-only results can at most support shadow mode (see section 5).

Genuine LCC request collection (parallel track, prerequisite for adoption):

- Source: the opt-in LCC observation consumer. Log only the caller's natural
  goal string, detected language, LCC version, timestamp (date granularity),
  session hash and the field the caller ultimately used (or "none").
- Never log dossier/context content, file paths, hostnames, emails, tokens or
  record values. A local redaction pass replaces such spans with typed
  placeholders; redaction is applied before write and its rule set is hashed.
- Consent: off by default, enabled per workspace by explicit flag; each logged
  item can be deleted by its owner before the corpus freeze.
- Minimum before an adoption decision: 200 genuine requests, >= 80 per language,
  from >= 20 distinct sessions; labelled by the section 4 protocol and assigned to
  families/splits like authored data. If the owner is the only requester, report
  "single-requester genuine data" as a limit.

## 4. Human review packet (required before any adoption)

Reviewer receives, blind to model outputs and to split:

- Sample: 240 queries from >= 120 families, stratified language (EN/PT) x kind
  group (supported field, unsupported/UNKNOWN, field/unit contrast, ambiguity)
  x provenance (authored, genuine_lcc) = 16 strata x 15 items; a stratum with
  fewer items is taken in full and its shortfall reported. Per-field and
  per-UNKNOWN-kind counts are reported inside each stratum, not gated. All
  genuine_lcc confirmation items are included in full.
- Fields per item: query ID, family ID, language, text, sibling-frame text,
  proposed label (field+unit or UNKNOWN+kind), the public registry definition,
  and blank columns verdict (agree / disagree / ambiguous), corrected label, note.
- Reviewer is not the corpus author when possible; otherwise single-author status
  is stated in every result.
- Pass: agreement >= .95 overall and >= .90 in every stratum. Fail: the corpus
  version is revised and re-frozen before any fit; items disagreeing in a split
  already frozen are excluded with their family, never relabelled after scoring.
- Post-confirmation: a second blind packet of 100 accepted predictions (or all
  if fewer) is reviewed; the precision gate must also hold on reviewer labels.

## 5. Stop criterion (decided now)

One candidate fit per corpus version; thresholds fitted on train+calibration
only; validation checked once. Fresh confirmation is run once, no retry.
The learned route is **closed to shadow-only** if any of these holds:

1. The candidate fails any section 1 gate (aggregate, EN or PT) on fresh
   confirmation families.
2. Its correct supported coverage on confirmation is not strictly above the
   frozen router's on the same families, or is below the 197/240 = .820833 rate.
3. Any relation/ordering component it carries does not strictly exceed the
   immutable scalar shadow on the same fresh rows (pooled AUC > scalar,
   within-goal AUC > scalar) while keeping positive retention >= .95 and zero
   UNKNOWN DROPs. A candidate without such a component cannot claim to replace
   the scalar ordering; the scalar stays the ordering reference.
4. Validation fails on two consecutive corpus versions (two strikes), so no
   confirmation is ever spent.
5. Human review (section 4) fails twice, or the genuine-request minimum is not
   met by 2026-12-31.

On a stop: the learned goal interpreter runs only in shadow (logged, never
routing), and the deterministic explicit `rank_observations` route
(ObservationRequest naming the field) becomes the product path. That route does
not interpret free text; free-text goals then return UNKNOWN and ask the caller
to name a field. Receipts of the failed candidate are preserved unchanged.

None of 1-5 holding, with sections 3 and 4 satisfied, permits only the next frozen
LCC outcome pilot, not default/P2/publication promotion.

## 6. Cost budget per step

| Step | Inference / compute cap | Wall/memory cap | API calls |
| --- | --- | --- | --- |
| Corpus authoring + offline audit | 0 forwards; tokenizer count only | 1 h CPU | 0 |
| Genuine request logging | 0 forwards; local redaction | negligible | 0 |
| Human review packet 1 (+2) | 0 | ~6 reviewer hours each | 0 |
| Router control on new families | <= 30,000 encoder inputs, once | 10 min, 2 GB RSS | 0 |
| Candidate fit (frozen encoder + heads) | <= 30,000 forwards, <= 200 head steps | 15 min, 2 GB RSS | 0 |
| Fresh confirmation (candidate + router + scalar) | <= 30,000 forwards total, one shot | 30 min, 4 GB RSS | 0 |
| Claim gate per result | 0 local | — | 1 Jev call, no retry |

Exceeding a cap stops the step; a partial run is a failure receipt, not a retry.

## Out of scope

Encoder fine-tuning, backbone/pooling/seed search, more epochs on rejected
recipes, new fields beyond the eight-field registry, eighteen-field selection,
native 32K, quantization, LCC 8K/32K outcome benchmarks, external provider
comparisons, default/P2/publication changes, editing any existing receipt, and
reuse of exposed populations as confirmation.
