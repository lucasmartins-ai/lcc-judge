# Matched-budget v1: every arm ranks the same candidate blocks

## Limits (read first)

- 60 real items only; Wilson 95% intervals are wide (about +-12 pt at mid rates).
- Probes are proxies (latest assistant turn, last tool result, task state, named refs, ...): they reward keeping recent blocks and do not measure whether an answer would actually be correct.
- Jev scores are reused from the v0.1 run (no new calls); Jev saw the same blocks and goal.
- Token counts are LCC heuristic (approximate:heuristic), not a real tokenizer.
- Drop-only: no trimming, so arms differ only by ranking. Unscored blocks (specialist window 512, Laya single block over its window) are kept until only unscored candidates remain, as the arm would do live. Laya batches that overflow its 1024-token window are scored mechanically by LCC itself, so the laya arm is Laya as LCC runs it (laya_native = share Laya itself scored).
- Ties drop the older block first for every arm. Random = mean of 5 seeds (k is a mean). A random tie-break sensitivity is reported below because it changes the mechanical arm a lot.
- Latency is not like-for-like: Jev and specialist (CPU) come from their earlier saved runs; Laya ran now with LCC default device selection, which picks the Apple GPU (MPS) here, on a machine shared with other heavy jobs (browser GPU processes, load average shown below). Laya wall latency is not a clean CPU number; a CPU-only, idle-machine Laya timing is still missing.

## Bottom line

- Recency alone (keep the newest blocks) has the best curve (AUC 0.973 vs Jev 0.498); these probes mostly check recent material, so this says more about the probes than about relevance. No arm in this table beats recency.
- With ties broken fairly (random), the only local ranker level with Jev is stdlib BM25 (AUC 0.503 vs 0.490); Laya is 8.0 pt below, the LCC-judge specialist 27.8 pt below and under the random floor (0.293).
- Laya beats Jev only at the lightest budget (10%) and falls behind from 20% on.

## Setup

- Candidates: 23798 blocks (median 335.0 per item) = every block LCC block mode did not mark protected (protected = shorter than min_block_chars=40; block mode has no recent-turn protection). Same split (max_block_chars=6000) and same protected set in every saved run, checked per item.
- Share of candidates each arm actually scored: jev 1.00, specialist 0.90, laya 0.96, laya_native 0.83, mechanical 1.00, bm25 1.00.
- Laya warnings by kind: {'laya_context_limit_exceeded': 998, 'approximate_token_count': 60, 'laya_batch_N_failed': 484, 'low_reduction': 13, 'cache_epoch_risk': 13, 'sufficiency_restoration_budget_exceeded': 7, 'needs_review': 9, 'semantic_sufficiency_restoration': 17}; network guard trips during the Laya run: 0.
- Budget b: drop lowest-scored candidates until >= b% of candidate tokens are removed. Median share actually removed per arm (10..60%): jev 0.10/0.20/0.30/0.40/0.50/0.60; specialist 0.10/0.20/0.30/0.40/0.50/0.60; laya 0.10/0.20/0.30/0.40/0.50/0.60; mechanical 0.10/0.20/0.30/0.40/0.50/0.61; bm25 0.10/0.20/0.30/0.40/0.50/0.60; recency 0.10/0.20/0.30/0.41/0.50/0.60; random 0.10/0.20/0.30/0.40/0.50/0.60.

## Item retention k/n (rate, Wilson 95%) by budget

| arm | 10% | 20% | 30% | 40% | 50% | 60% | AUC |
|---|---|---|---|---|---|---|---|
| jev | 33/49 (0.67, 0.53-0.79) | 27/49 (0.55, 0.41-0.68) | 23/49 (0.47, 0.34-0.61) | 19/49 (0.39, 0.26-0.53) | 15/49 (0.31, 0.20-0.45) | 10/49 (0.20, 0.11-0.34) | 0.498 |
| specialist | 14/49 (0.29, 0.18-0.42) | 8/49 (0.16, 0.09-0.29) | 7/49 (0.14, 0.07-0.27) | 6/49 (0.12, 0.06-0.24) | 6/49 (0.12, 0.06-0.24) | 6/49 (0.12, 0.06-0.24) | 0.233 |
| laya | 40/49 (0.82, 0.69-0.90) | 25/49 (0.51, 0.37-0.64) | 16/49 (0.33, 0.21-0.47) | 9/49 (0.18, 0.10-0.31) | 7/49 (0.14, 0.07-0.27) | 5/49 (0.10, 0.04-0.22) | 0.422 |
| mechanical | 48/49 (0.98, 0.89-1.00) | 48/49 (0.98, 0.89-1.00) | 43/49 (0.88, 0.76-0.94) | 43/49 (0.88, 0.76-0.94) | 38/49 (0.78, 0.64-0.87) | 31/49 (0.63, 0.49-0.75) | 0.884 |
| bm25 | 46/49 (0.94, 0.83-0.98) | 42/49 (0.86, 0.73-0.93) | 39/49 (0.80, 0.66-0.89) | 35/49 (0.71, 0.58-0.82) | 30/49 (0.61, 0.47-0.74) | 26/49 (0.53, 0.39-0.66) | 0.781 |
| recency | 48/49 (0.98, 0.89-1.00) | 48/49 (0.98, 0.89-1.00) | 48/49 (0.98, 0.89-1.00) | 48/49 (0.98, 0.89-1.00) | 47/49 (0.96, 0.86-0.99) | 45/49 (0.92, 0.81-0.97) | 0.973 |
| random | 25.8/49 (0.53, 0.39-0.66) | 15/49 (0.31, 0.20-0.45) | 8.8/49 (0.18, 0.10-0.31) | 5.8/49 (0.12, 0.06-0.24) | 4.8/49 (0.10, 0.04-0.22) | 3.2/49 (0.07, 0.02-0.17) | 0.293 |

AUC = area under retention vs budget from 0% to 60% (0% = nothing dropped), normalised to 0-1.

## Tie sensitivity

Share of candidates whose score equals another candidate's in the same item: jev 0.97, specialist 0.05, laya 0.41, mechanical 1.00, bm25 0.69. Mechanical gives most blocks the same score (0.0), so its oldest-first tie-break makes it behave like recency. Same table, ties broken at random (mean of 5 seeds, rate):

| arm | 10% | 20% | 30% | 40% | 50% | 60% | AUC |
|---|---|---|---|---|---|---|---|
| jev | 0.67 | 0.54 | 0.46 | 0.39 | 0.27 | 0.20 | 0.490 |
| specialist | 0.29 | 0.16 | 0.13 | 0.09 | 0.08 | 0.06 | 0.212 |
| laya | 0.78 | 0.51 | 0.33 | 0.18 | 0.13 | 0.07 | 0.410 |
| mechanical | 0.64 | 0.42 | 0.31 | 0.26 | 0.21 | 0.16 | 0.404 |
| bm25 | 0.67 | 0.51 | 0.44 | 0.38 | 0.36 | 0.31 | 0.503 |

## Against Jev, in plain words

Main table (ties oldest-first):

- **specialist** is below Jev overall (AUC -26.5 pt): 10%: -38.8 pt; 20%: -38.8 pt; 30%: -32.6 pt; 40%: -26.5 pt; 50%: -18.4 pt; 60%: -8.2 pt.
- **laya** is below Jev overall (AUC -7.7 pt): 10%: +14.3 pt; 20%: -4.1 pt; 30%: -14.3 pt; 40%: -20.4 pt; 50%: -16.3 pt; 60%: -10.2 pt.
- **mechanical** is above Jev overall (AUC +38.6 pt): 10%: +30.6 pt; 20%: +42.9 pt; 30%: +40.8 pt; 40%: +49.0 pt; 50%: +46.9 pt; 60%: +42.9 pt.
- **bm25** is above Jev overall (AUC +28.2 pt): 10%: +26.5 pt; 20%: +30.6 pt; 30%: +32.7 pt; 40%: +32.7 pt; 50%: +30.6 pt; 60%: +32.6 pt.
- **recency** is above Jev overall (AUC +47.4 pt): 10%: +30.6 pt; 20%: +42.9 pt; 30%: +51.0 pt; 40%: +59.2 pt; 50%: +65.3 pt; 60%: +71.4 pt.
- **random** is below Jev overall (AUC -20.5 pt): 10%: -14.7 pt; 20%: -24.5 pt; 30%: -29.0 pt; 40%: -26.9 pt; 50%: -20.8 pt; 60%: -13.9 pt.

Ties broken at random (Jev also re-broken at random):

- **specialist** is below Jev overall (AUC -27.8 pt): 10%: -38.8 pt; 20%: -38.8 pt; 30%: -33.1 pt; 40%: -29.4 pt; 50%: -19.6 pt; 60%: -14.7 pt.
- **laya** is below Jev overall (AUC -8.0 pt): 10%: +11.0 pt; 20%: -3.3 pt; 30%: -13.5 pt; 40%: -21.2 pt; 50%: -14.7 pt; 60%: -13.1 pt.
- **mechanical** is below Jev overall (AUC -8.6 pt): 10%: -2.9 pt; 20%: -11.8 pt; 30%: -15.1 pt; 40%: -12.7 pt; 50%: -6.5 pt; 60%: -4.9 pt.
- **bm25** is above Jev overall (AUC +1.3 pt): 10%: -0.8 pt; 20%: -2.9 pt; 30%: -1.6 pt; 40%: -0.4 pt; 50%: +8.2 pt; 60%: +10.2 pt.

Paired items vs Jev per budget (+items only this arm keeps / -items only Jev keeps):

- specialist: 10% +2/-21; 20% +1/-20; 30% +1/-17; 40% +1/-14; 50% +1/-10; 60% +2/-6
- laya: 10% +12/-5; 20% +11/-13; 30% +6/-13; 40% +3/-13; 50% +4/-12; 60% +3/-8
- mechanical: 10% +15/-0; 20% +21/-0; 30% +23/-3; 40% +26/-2; 50% +24/-1; 60% +24/-3
- bm25: 10% +14/-1; 20% +17/-2; 30% +18/-2; 40% +19/-3; 50% +18/-3; 60% +19/-3
- recency: 10% +15/-0; 20% +21/-0; 30% +25/-0; 40% +29/-0; 50% +32/-0; 60% +35/-0

## Cost per item

| arm | latency median ms | latency p90 ms | peak RSS MB | model on disk MB | $ per item | note |
|---|---|---|---|---|---|---|
| jev | 14001.0 | 37030 | - | - | 0.5829 median / 0.7253 mean | remote API; saved v0.1 ledger, serial requests |
| specialist | 24554.0 | 89705 | 929.9 | 573.7 | 0 | RSS from one median item (338 candidates); CPU; model load 5663 ms |
| laya | 24122.5 | 53712 | 2641.9 | 646.8 | 0 | convaiinnovations/laya-multilingual; device auto = Apple GPU (MPS) on this Mac; machine shared with other jobs (10 cores); model load 25634 ms; process CPU time median 2041.0 ms / p90 8355 ms; 1-min load average median 16.9 |
| mechanical | 696.5 | 6582 | - | 0 | 0 | saved v0 latency (whole compact_context call) |
| bm25 | 13.7 | 33.9 | - | 0 | 0 | scoring only, stdlib |
| recency | - | - | - | 0 | 0 | no scoring |
| random | - | - | - | 0 | 0 | no scoring |

Latency is the whole compaction call per item from each arm's own run (Jev: serial HTTP, concurrency 1). Peak RSS is the process maximum (includes Python + the loaded model). Model size counts weights, tokenizer and config on disk. Jev $ is the API-reported usage from the saved ledger.
