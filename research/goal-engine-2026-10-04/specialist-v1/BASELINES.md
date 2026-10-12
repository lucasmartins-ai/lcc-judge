# Matched-budget v2 baselines: next-action evidence labels (dev split)

## Limits (read first)

- Labels are rule-based next-action evidence (research.next_action_labels v1), not human judgement: a block is USED when the agent later reused a path, identifier, number, hash, line or quoted span from it without re-fetching. USED means relied on, not proven necessary.
- Labels still lean recent (USED rate 4.8% in the oldest tenth vs 16.3% in the newest, train+dev): recency is a strong baseline here by construction, not because it understands the goal.
- Dev only (326 eligible items); the test split was not opened. Excluded dev items: {'no_used_candidate': 27, 'no_agent_action': 8}.
- Model arms (specialist, Laya) ran on a seeded subset (36 of 36 planned items, 12 per source, seed 20261012); Laya CPU was too slow for all of it (~1-2 blocks/s under load), so Laya ran on a nested subset (18 of 18 planned: the first 6 of each source's seeded sample). Every arm is compared on the SAME items only.
- jev-overlap = the 43 frozen-60 items outside test with >= 1 USED candidate (excluded: {'test_split_or_unmatched': 11, 'no_used_candidate': 6}; the test-split items are never opened). Jev, specialist and Laya scores there are reused from saved v0/v1 runs (no new calls; that Laya run used the Apple GPU and a mechanical fallback that is NOT mixed in here: Laya-native scores only, the rest unscored).
- Drop-only at the block level: no trimming. Unscored blocks (specialist pair window 512 tokens, Laya oversized or failed batches) are kept until only unscored candidates remain, as the arm does live, so low coverage flatters an arm at light budgets.
- Ties drop the older block first; random tie-break AUCs are reported because mechanical and BM25 tie a lot.
- Token counts are the LCC heuristic (gpt-4.1 counter), not a real tokenizer.
- Latency was measured on a shared machine (1-min load average ~27.3 on 10 cores); treat it as an order of magnitude.

## Bottom line

- Dev (all items): best recall AUC is **recency** (0.785); recency 0.785, bm25 0.782, mechanical 0.777, random 0.685.
- Dev-model subset (36 items): best recall AUC is **recency** (0.795); recency 0.795, bm25 0.763, mechanical 0.777, specialist 0.779, specialist_inv 0.718, random 0.685.
- Laya subset (18 items): best recall AUC is **specialist** (0.833); recency 0.797, bm25 0.761, mechanical 0.762, specialist 0.833, specialist_inv 0.787, laya 0.760, random 0.696.
- jev-overlap: Jev recall AUC 0.814; recency 0.751, bm25 0.802, mechanical 0.760, specialist 0.778, specialist_inv 0.783, laya 0.756, random 0.700.
- Specialist orientation (recall AUC, own logits vs negated): dev_model 0.779 vs 0.718; jev_overlap 0.778 vs 0.783. No inversion: negating the logits is not >= 1 pt better on either subset.
- No local arm beats Jev on jev-overlap: closest is bm25 (-1.2 pt recall AUC). On the dev-model subset no arm beats recency; the specialist's lead on the 18-item Laya subset does not hold on the 36 items.
- A specialist that is "superior to Jev" must beat Jev here AND beat recency/BM25 on dev, and pass more edge cases than every arm below.

## Metrics

Cells: macro USED-token recall / items keeping every USED block (k/n) / macro evidence-feature coverage. AUC over 0..60% budget (0% = 1.0), normalised to 0-1.

## Dev, all eligible items (326 items, 133236 candidates, USED share of blocks 0.104)

| arm | 10% | 20% | 30% | 40% | 50% | 60% | AUC recall | AUC all-kept | AUC ev-cov |
|---|---|---|---|---|---|---|---|---|---|
| recency | 0.93 / 141/326 / 0.97 | 0.86 / 93/326 / 0.94 | 0.79 / 67/326 / 0.91 | 0.72 / 51/326 / 0.87 | 0.63 / 41/326 / 0.83 | 0.55 / 34/326 / 0.79 | 0.785 | 0.293 | 0.902 |
| bm25 | 0.94 / 119/326 / 0.96 | 0.87 / 78/326 / 0.93 | 0.79 / 47/326 / 0.89 | 0.71 / 37/326 / 0.84 | 0.62 / 31/326 / 0.79 | 0.52 / 20/326 / 0.72 | 0.782 | 0.248 | 0.877 |
| mechanical | 0.92 / 94/326 / 0.97 | 0.85 / 64/326 / 0.93 | 0.78 / 46/326 / 0.89 | 0.70 / 32/326 / 0.85 | 0.63 / 32/326 / 0.80 | 0.55 / 29/326 / 0.75 | 0.777 | 0.228 | 0.886 |
| random | 0.89 / 56.2/326 / 0.96 | 0.78 / 27.2/326 / 0.92 | 0.68 / 16.4/326 / 0.88 | 0.58 / 9.4/326 / 0.83 | 0.48 / 5.6/326 / 0.78 | 0.38 / 4.2/326 / 0.71 | 0.685 | 0.143 | 0.871 |

Random tie-break AUC (mean of 5 seeds): bm25 recall 0.736 / all-kept 0.155; mechanical recall 0.713 / all-kept 0.146.
Tied share of candidates: bm25 0.76, mechanical 1.00.

Recall AUC by source: recency: claude 0.795 (n=97), codex 0.820 (n=81), hermes 0.758 (n=148); bm25: claude 0.794 (n=97), codex 0.854 (n=81), hermes 0.735 (n=148); mechanical: claude 0.799 (n=97), codex 0.819 (n=81), hermes 0.739 (n=148).

## Dev-model subset (36 items, 17860 candidates, sources {'claude': 12, 'codex': 12, 'hermes': 12})

| arm | 10% | 20% | 30% | 40% | 50% | 60% | AUC recall | AUC all-kept | AUC ev-cov |
|---|---|---|---|---|---|---|---|---|---|
| recency | 0.93 / 14/36 / 0.97 | 0.88 / 10/36 / 0.92 | 0.81 / 6/36 / 0.90 | 0.74 / 6/36 / 0.88 | 0.64 / 5/36 / 0.81 | 0.54 / 2/36 / 0.76 | 0.795 | 0.278 | 0.892 |
| bm25 | 0.91 / 11/36 / 0.95 | 0.85 / 6/36 / 0.91 | 0.77 / 5/36 / 0.85 | 0.70 / 5/36 / 0.81 | 0.59 / 3/36 / 0.76 | 0.49 / 1/36 / 0.72 | 0.763 | 0.225 | 0.857 |
| mechanical | 0.91 / 9/36 / 0.95 | 0.86 / 7/36 / 0.92 | 0.80 / 5/36 / 0.88 | 0.70 / 3/36 / 0.81 | 0.61 / 3/36 / 0.76 | 0.56 / 3/36 / 0.70 | 0.777 | 0.215 | 0.862 |
| specialist | 0.94 / 4/36 / 0.99 | 0.84 / 3/36 / 0.91 | 0.78 / 3/36 / 0.84 | 0.71 / 2/36 / 0.78 | 0.64 / 2/36 / 0.68 | 0.52 / 0/36 / 0.60 | 0.779 | 0.148 | 0.832 |
| specialist_inv | 0.89 / 4/36 / 0.91 | 0.78 / 3/36 / 0.84 | 0.69 / 1/36 / 0.76 | 0.63 / 1/36 / 0.71 | 0.57 / 1/36 / 0.63 | 0.49 / 0/36 / 0.59 | 0.718 | 0.130 | 0.773 |
| random | 0.88 / 5.4/36 / 0.96 | 0.79 / 3.2/36 / 0.92 | 0.69 / 1.6/36 / 0.89 | 0.58 / 1/36 / 0.83 | 0.48 / 0.4/36 / 0.79 | 0.39 / 0.2/36 / 0.73 | 0.685 | 0.138 | 0.876 |

Share of candidates each arm scored: recency 1.00, bm25 1.00, mechanical 1.00, specialist 0.90, specialist_inv 0.90.
Random tie-break AUC: bm25 recall 0.700 / all-kept 0.147; mechanical recall 0.716 / all-kept 0.148; specialist recall 0.748 / all-kept 0.129; specialist_inv recall 0.687 / all-kept 0.110.
Recall AUC by source: recency: claude 0.767 (n=12), codex 0.819 (n=12), hermes 0.800 (n=12); bm25: claude 0.797 (n=12), codex 0.813 (n=12), hermes 0.678 (n=12); specialist: claude 0.768 (n=12), codex 0.848 (n=12), hermes 0.722 (n=12); specialist_inv: claude 0.740 (n=12), codex 0.701 (n=12), hermes 0.713 (n=12).

## Laya subset (nested in dev-model) (18 items, 7477 candidates, sources {'claude': 6, 'codex': 6, 'hermes': 6})

| arm | 10% | 20% | 30% | 40% | 50% | 60% | AUC recall | AUC all-kept | AUC ev-cov |
|---|---|---|---|---|---|---|---|---|---|
| recency | 0.94 / 8/18 / 0.99 | 0.87 / 6/18 / 0.92 | 0.81 / 4/18 / 0.90 | 0.72 / 4/18 / 0.87 | 0.66 / 4/18 / 0.85 | 0.56 / 1/18 / 0.76 | 0.797 | 0.329 | 0.900 |
| bm25 | 0.94 / 5/18 / 1.00 | 0.86 / 2/18 / 0.95 | 0.75 / 2/18 / 0.86 | 0.68 / 2/18 / 0.81 | 0.58 / 1/18 / 0.74 | 0.50 / 0/18 / 0.68 | 0.761 | 0.194 | 0.866 |
| mechanical | 0.89 / 4/18 / 0.95 | 0.84 / 3/18 / 0.90 | 0.79 / 2/18 / 0.87 | 0.70 / 1/18 / 0.82 | 0.59 / 1/18 / 0.76 | 0.53 / 1/18 / 0.67 | 0.762 | 0.190 | 0.857 |
| specialist | 0.95 / 2/18 / 0.99 | 0.88 / 2/18 / 0.93 | 0.84 / 2/18 / 0.82 | 0.78 / 1/18 / 0.79 | 0.74 / 1/18 / 0.74 | 0.63 / 0/18 / 0.67 | 0.833 | 0.157 | 0.852 |
| specialist_inv | 0.90 / 2/18 / 0.95 | 0.83 / 2/18 / 0.86 | 0.78 / 1/18 / 0.81 | 0.74 / 1/18 / 0.78 | 0.68 / 1/18 / 0.72 | 0.58 / 0/18 / 0.68 | 0.787 | 0.148 | 0.828 |
| laya | 0.91 / 2/18 / 0.98 | 0.81 / 2/18 / 0.90 | 0.75 / 1/18 / 0.82 | 0.69 / 1/18 / 0.76 | 0.63 / 1/18 / 0.74 | 0.52 / 0/18 / 0.67 | 0.760 | 0.148 | 0.839 |
| random | 0.90 / 3.4/18 / 0.96 | 0.80 / 2/18 / 0.92 | 0.69 / 0.6/18 / 0.89 | 0.59 / 0.4/18 / 0.85 | 0.50 / 0.2/18 / 0.79 | 0.39 / 0/18 / 0.73 | 0.696 | 0.144 | 0.879 |

Share of candidates each arm scored: recency 1.00, bm25 1.00, mechanical 1.00, specialist 0.90, laya 0.84, specialist_inv 0.90.
Random tie-break AUC: bm25 recall 0.713 / all-kept 0.113; mechanical recall 0.708 / all-kept 0.126; specialist recall 0.779 / all-kept 0.118; laya recall 0.719 / all-kept 0.139; specialist_inv recall 0.733 / all-kept 0.109.
Recall AUC by source: recency: claude 0.778 (n=6), codex 0.803 (n=6), hermes 0.810 (n=6); bm25: claude 0.804 (n=6), codex 0.768 (n=6), hermes 0.710 (n=6); specialist: claude 0.781 (n=6), codex 0.889 (n=6), hermes 0.828 (n=6); laya: claude 0.763 (n=6), codex 0.728 (n=6), hermes 0.789 (n=6); specialist_inv: claude 0.763 (n=6), codex 0.768 (n=6), hermes 0.831 (n=6).

Laya warnings by kind: {'laya_context_limit_exceeded': 356, 'laya_batch_N_failed': 16}.

## jev-overlap (43 items, 16500 candidates; excluded {'test_split_or_unmatched': 11, 'no_used_candidate': 6})

| arm | 10% | 20% | 30% | 40% | 50% | 60% | AUC recall | AUC all-kept | AUC ev-cov |
|---|---|---|---|---|---|---|---|---|---|
| recency | 0.89 / 15/43 / 0.95 | 0.84 / 14/43 / 0.93 | 0.73 / 9/43 / 0.87 | 0.66 / 8/43 / 0.85 | 0.61 / 5/43 / 0.80 | 0.54 / 5/43 / 0.76 | 0.751 | 0.291 | 0.880 |
| bm25 | 0.94 / 17/43 / 0.98 | 0.89 / 10/43 / 0.93 | 0.81 / 8/43 / 0.87 | 0.74 / 5/43 / 0.85 | 0.67 / 4/43 / 0.81 | 0.54 / 4/43 / 0.73 | 0.802 | 0.262 | 0.883 |
| mechanical | 0.89 / 9/43 / 0.95 | 0.79 / 6/43 / 0.89 | 0.75 / 6/43 / 0.86 | 0.70 / 4/43 / 0.80 | 0.64 / 3/43 / 0.77 | 0.57 / 3/43 / 0.69 | 0.760 | 0.198 | 0.852 |
| specialist | 0.93 / 10/43 / 0.95 | 0.88 / 8/43 / 0.92 | 0.80 / 4/43 / 0.86 | 0.69 / 3/43 / 0.74 | 0.61 / 3/43 / 0.67 | 0.53 / 3/43 / 0.62 | 0.778 | 0.198 | 0.825 |
| specialist_inv | 0.92 / 9/43 / 0.93 | 0.84 / 5/43 / 0.85 | 0.81 / 5/43 / 0.83 | 0.72 / 4/43 / 0.75 | 0.64 / 4/43 / 0.68 | 0.54 / 3/43 / 0.62 | 0.783 | 0.194 | 0.807 |
| laya | 0.92 / 9/43 / 0.93 | 0.85 / 6/43 / 0.88 | 0.74 / 2/43 / 0.77 | 0.68 / 1/43 / 0.73 | 0.59 / 1/43 / 0.67 | 0.50 / 1/43 / 0.62 | 0.756 | 0.159 | 0.797 |
| jev | 0.93 / 17/43 / 0.97 | 0.90 / 14/43 / 0.96 | 0.84 / 11/43 / 0.93 | 0.77 / 8/43 / 0.90 | 0.67 / 6/43 / 0.85 | 0.56 / 4/43 / 0.80 | 0.814 | 0.308 | 0.917 |
| random | 0.89 / 9.4/43 / 0.95 | 0.79 / 6/43 / 0.91 | 0.70 / 4.4/43 / 0.86 | 0.61 / 3.8/43 / 0.83 | 0.50 / 2.2/43 / 0.76 | 0.41 / 1.4/43 / 0.70 | 0.700 | 0.186 | 0.860 |

Share of candidates each arm scored: jev 1.00, specialist 0.90, specialist_inv 0.90, laya 0.84, recency 1.00, bm25 1.00, mechanical 1.00.
Random tie-break AUC: jev recall 0.812 / all-kept 0.299; specialist recall 0.767 / all-kept 0.182; specialist_inv recall 0.772 / all-kept 0.178; laya recall 0.746 / all-kept 0.155; bm25 recall 0.794 / all-kept 0.223; mechanical recall 0.728 / all-kept 0.167.

Paired items vs Jev (USED recall higher / lower than Jev on the same item):

- specialist: 10% +19/-17; 20% +17/-20; 30% +18/-22; 40% +18/-22; 50% +21/-17; 60% +23/-17
- specialist_inv: 10% +17/-18; 20% +16/-21; 30% +19/-18; 40% +20/-18; 50% +23/-14; 60% +24/-15
- laya: 10% +15/-19; 20% +19/-19; 30% +13/-27; 40% +17/-24; 50% +20/-18; 60% +18/-21
- recency: 10% +11/-21; 20% +11/-23; 30% +10/-26; 40% +10/-27; 50% +16/-20; 60% +15/-23
- bm25: 10% +13/-18; 20% +12/-23; 30% +12/-22; 40% +17/-21; 50% +18/-18; 60% +14/-22
- mechanical: 10% +11/-24; 20% +9/-28; 30% +12/-26; 40% +12/-27; 50% +16/-21; 60% +18/-21

## Edge-case suite (35 synthetic cases, pass k/35)

| arm | 30% | 50% | 70% | scored share |
|---|---|---|---|---|
| oracle | 35 | 35 | 35 | - |
| recency | 7 | 7 | 4 | - |
| bm25 | 21 | 20 | 18 | - |
| mechanical | 22 | 21 | 18 | - |
| specialist | 0 | 0 | 0 | 0.56 |
| specialist_inv | 2 | 0 | 0 | - |
| laya | 16 | 11 | 8 | 0.78 |
| random | 15.8 | 13.4 | 9.4 | - |

Jev: not run on the edge suite (no saved scores; no remote calls allowed). Oracle = gold upper bound. Random = mean of 5 seeds. Scored share < 1: blocks over the arm's window are unscored and, by the shared rule, dropped last, so the arm drops only the short scored blocks, which is where most must-keep evidence sits. The 512-token specialist fails the suite mostly for this structural reason, not only for ranking.

## Cost per item

| arm | score ms median | p90 | blocks/s | model load ms | peak RSS MB | threads | note |
|---|---|---|---|---|---|---|---|
| bm25 | 18.0 | 39.8 | - | - | - | - | stdlib, 40 dev items |
| mechanical | 50.5 | 241.7 | - | - | - | - | LCC _score_mechanically in-process, 40 dev items |
| specialist | 31268.5 | 169992 | 8.35 | 5375 | 1664.1 | 4 | CPU; dev-model subset (specialist) / Laya subset (laya) |
| laya | 165941.5 | 706785 | 1.76 | 8598 | 4126.4 | 8 | CPU; dev-model subset (specialist) / Laya subset (laya) |

Recency and random need no scoring. Jev: see matched-budget-v1 (remote, ~$0.58 median per item).
