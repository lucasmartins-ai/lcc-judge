# Probe eval v1: results (2026-10-17)

Pre-registered in `PROTOCOL.md` (amendments 1-3), harness frozen at d82a7d0, probes committed in e1aa8ed before any
model-based arm ran. Aggregates only; machine-readable copy: `results.json`. **Label: INFERIDO.** `gateClaim`
returned BLOCK on the headline (support 0.73 < 0.85, "single measurement, no independent source"). The numbers
below are measured, but they are one run on one owner's sessions.

## Bottom line

**H1 passes under the pre-registered rule.** On the artifact trail, the verbatim modes beat Claude Code's native
summary arm, and all three validity gates pass. The mechanical effect is small: about +0.06 path recall. The
judge's effect is large: +0.6 of 5 on artifact trail. The verbatim modes are not inferior to full context, and they
use about 9.6× the tokens of the summary. **This is not a matched-budget result.**

## Gates and H1 (D: 172 items, 75 session groups, 0 dropped)

| check | rule | result |
|---|---|---|
| V1 | `full` artifact recall ≥ 0.50 | 0.64: pass |
| V2 | ≤ 10% of items dropped | 0%: pass |
| V3 | Opus × Gemini quadratic-weighted kappa on artifact_trail ≥ 0.40 | 0.917 on 248 records (16 of 17 sampled items; 1 Gemini timeout): pass |
| **H1** | lower 97.5% bound > 0 for both contrasts | lossless − native **+0.057 [0.018, 0.093]**; recoverable − native **+0.068 [0.021, 0.115]**: **pass** |
| S2 | non-inferior to `full` (lower 95% bound > −0.03) | lossless +0.004 [−0.026, 0.036]; recoverable +0.015 [−0.010, 0.041]: pass, lossless near the margin |

## D per arm (mean per item, 95% cluster-bootstrap CI)

| metric | full | native | lcc_lossless | lcc_recoverable |
|---|---|---|---|---|
| context tokens (pooled, lcc counter) | 9.41 M | **0.98 M** | 9.38 M | 9.37 M |
| artifact path recall | 0.64 [0.58, 0.69] | 0.59 [0.53, 0.65] | 0.64 [0.59, 0.69] | 0.66 [0.60, 0.71] |
| artifact, all paths recalled (Wilson) | 0.42 [0.35, 0.50] | 0.37 [0.30, 0.45] | 0.41 [0.34, 0.49] | 0.45 [0.38, 0.52] |
| recall exact match | 0.98 [0.96, 1.00] | **0.73 [0.65, 0.80]** | 0.99 [0.97, 1.00] | 0.98 [0.96, 1.00] |
| continuation target match | 0.38 [0.29, 0.47] | 0.24 [0.17, 0.32] | 0.41 [0.32, 0.50] | 0.36 [0.26, 0.45] |
| items with ≥ 1 invented file path | 0.64 [0.55, 0.72] | 0.64 [0.55, 0.72] | 0.61 [0.51, 0.70] | 0.60 [0.50, 0.70] |
| judge: accuracy | 3.70 [3.62, 3.79] | 3.09 [2.94, 3.24] | 3.69 [3.61, 3.79] | 3.71 [3.63, 3.79] |
| judge: context awareness | 3.96 [3.88, 4.04] | 3.36 [3.22, 3.51] | 3.95 [3.88, 4.04] | 3.95 [3.87, 4.04] |
| judge: artifact trail | 3.72 [3.64, 3.81] | 3.12 [2.97, 3.29] | 3.73 [3.64, 3.83] | 3.73 [3.64, 3.82] |
| judge: completeness | 3.94 [3.86, 4.04] | 3.31 [3.15, 3.48] | 3.93 [3.85, 4.03] | 3.94 [3.85, 4.04] |
| judge: continuity | 3.80 [3.72, 3.89] | 3.17 [3.02, 3.33] | 3.80 [3.72, 3.90] | 3.81 [3.73, 3.90] |
| judge: instruction following | 4.24 [4.19, 4.30] | 3.83 [3.75, 3.92] | 4.19 [4.14, 4.24] | 4.25 [4.20, 4.30] |

**Judge overall (mean of 6 dimensions), by probe type:**

| probe type | full | native | lcc_lossless | lcc_recoverable |
|---|---|---|---|---|
| artifact | 2.98 | 2.78 | 3.00 | 3.00 |
| recall | 4.94 | **3.65** | 4.95 | 4.93 |
| continuation | 3.06 | 2.80 | 3.04 | 3.11 |
| decision | 4.78 | 4.22 | 4.77 | 4.77 |

**Contrasts on the judge (95%):**
- artifact_trail: lossless − native +0.61 [0.51, 0.72]; recoverable − native +0.61 [0.49, 0.72].
- overall: lossless − native +0.57 [0.47, 0.67]; recoverable − native +0.58 [0.48, 0.70].

## J: Jev stratum (43 items, 35 groups), descriptive, no verdict

| metric | full | native | lossless | recoverable | jev_block |
|---|---|---|---|---|---|
| context tokens | 1.96 M | 0.22 M | 1.96 M | 1.96 M | 1.90 M |
| artifact path recall (n = 27) | 0.69 [0.55, 0.82] | 0.51 [0.36, 0.65] | 0.61 [0.45, 0.76] | 0.65 [0.49, 0.79] | 0.63 [0.48, 0.77] |
| recall exact match | 1.00 | 0.81 [0.68, 0.92] | 1.00 | 1.00 | 1.00 |
| judge artifact trail | 4.09 | 3.39 | 4.01 | 4.06 | 4.01 |

Artifact recall contrasts on J:
- jev − native: +0.12 [−0.02, 0.28];
- lossless − full: −0.08 [−0.19, 0.01]. The two contexts differ by 0.45% of tokens, so this gap is the answerer's
  run-to-run noise on n = 27.

Opus × Gemini kappa on J: 0.947 (45 records).

## Reading (INFERIDO)

- **The native summary loses exact detail most of all.** Its recall exact-match rate is 0.73 against 0.98. Its
  judged recall is 3.65 against 4.94. On file lists the loss is smaller, about 0.06 of path recall.
- **Lossless and recoverable add nothing measurable over `full`.** That is expected: they cut 0.37-0.46% of
  tokens on D. The finding is that verbatim retention keeps what a summary loses. It is not that LCC's selection
  adds information.
- **No arm is good at predicting the next files.** Even with full context, every gold file is listed in only 42%
  of items, and 60-64% of items name at least one file path found nowhere in the context (often a file to be
  created). The artifact probe measures prediction plus memory, not memory alone.
- **The comparison is not budget-matched.** A summary at about 1/10 of the tokens is the native operating point. A
  verbatim arm at the same budget was not tested.

## Deviations and incidents (disclosed)

- **Order of steps.** The no-model arms were computed before the probe receipt was committed. The generator never
  reads `arms/` (see `probe-receipt.json`).
- **Duplicate runs (2026-10-17).** Background processes were invisible to `ps`. For about 1 hour, 2-3 D chains ran
  in parallel, which wasted about 48 duplicate Opus summary calls. The duplicates overwrote identical cache
  entries; no item was scored twice.
- **Logged-out CLI (2026-10-17, ~19:05).** The CLI got logged out, and 186 calls failed with "Not logged in"
  without reaching any model.
  - 92 such failures had been cached as item failures. They were deleted and re-run after the owner logged in
    again.
  - The rest of the run used `research/probe_eval_v1_run.py`. It is the frozen harness plus a guard that stops on
    "Not logged in" instead of caching. The harness file is unchanged.
- **Gemini.** On D, 1 of the 17 sampled items timed out twice and is a cached failure. V3 uses the other 16.
- **Calls.** 1,899 of the 3,000-call cap: 212 failed, of which 186 were auth errors, plus usage-limit stops and
  timeouts. $0 cash (subscription route).

## gateClaim

```
claim: D, 172 items / 75 groups: artifact path recall lossless 0.64, recoverable 0.66 vs native 0.59;
       97.5% CIs of the differences [0.018, 0.093] and [0.021, 0.115]
decision: BLOCK  claimSupported 0.73  evidenceStrength 2.34
requiredLabel: INFERIDO — nao medido (falta medicao repetida ou fonte independente)
```

To lift the label:
- replicate on the post-2026-10-12 held-out set, or on a second owner's sessions;
- add a budget-matched verbatim arm.
