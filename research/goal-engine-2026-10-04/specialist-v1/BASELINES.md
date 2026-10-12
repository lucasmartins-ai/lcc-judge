# Matched-budget v2 baselines: next-action evidence labels (dev split)

## Limits (read first)

- Labels are rule-based next-action evidence (research.next_action_labels v2: the v1 split relabelled after the 2026-10-12 label review removed short file names, project roots, cd lines, round numbers, plain quoted words and unicode-escape fragments as evidence), not human judgement: a block is USED when the agent later reused a path, identifier, number, hash, line or quoted span from it without re-fetching. USED means relied on, not proven necessary.
- Labels still lean recent (dev USED rate 5.5% in the oldest tenth vs 19.4% in the newest): recency is a strong baseline here by construction, not because it understands the goal.
- Dev only (325 eligible items); the test split was not opened. Excluded dev items: {'no_used_candidate': 28, 'no_agent_action': 8}.
- Model arms (specialist, Laya) ran on a seeded subset (36 of 36 planned items, 12 per source, seed 20261012); Laya CPU was too slow for all of it (~1-2 blocks/s under load), so Laya ran on a nested subset (18 of 18 planned: the first 6 of each source's seeded sample). Every arm is compared on the SAME items only.
- jev-overlap = the 43 frozen-60 items outside test with >= 1 USED candidate (excluded: {'test_split_or_unmatched': 11, 'no_used_candidate': 6}; the test-split items are never opened). Jev, specialist and Laya scores there are reused from saved v0/v1 runs (no new calls; that Laya run used the Apple GPU and a mechanical fallback that is NOT mixed in here: Laya-native scores only, the rest unscored).
- Drop-only at the block level: no trimming. Unscored blocks (specialist pair window 512 tokens, Laya oversized or failed batches) are kept until only unscored candidates remain, as the arm does live, so low coverage flatters an arm at light budgets.
- Ties drop the older block first; random tie-break AUCs are reported because mechanical and BM25 tie a lot.
- Token counts are the LCC heuristic (gpt-4.1 counter), not a real tokenizer.
- Latency was measured on a shared machine (1-min load average ~27.3 on 10 cores); treat it as an order of magnitude.

## Bottom line

- Dev (all items): best recall AUC is **recency** (0.789); recency 0.789, bm25 0.787, mechanical 0.784, random 0.685.
- Dev-model subset (36 items): best recall AUC is **recency** (0.811); recency 0.811, bm25 0.789, mechanical 0.793, specialist 0.758, specialist_inv 0.729, random 0.686.
- Laya subset (18 items): best recall AUC is **specialist** (0.813); recency 0.804, bm25 0.792, mechanical 0.786, specialist 0.813, specialist_inv 0.780, laya 0.748, random 0.694.
- jev-overlap: Jev recall AUC 0.818; recency 0.752, bm25 0.809, mechanical 0.749, specialist 0.784, specialist_inv 0.787, laya 0.758, random 0.703.
- Specialist orientation (recall AUC, own logits vs negated): dev_model 0.758 vs 0.729; jev_overlap 0.784 vs 0.787. No inversion: negating the logits is not >= 1 pt better on either subset.
- No local arm beats Jev on jev-overlap: closest is bm25 (-0.9 pt recall AUC). On the dev-model subset no arm beats recency; the specialist's lead on the 18-item Laya subset does not hold on the 36 items.
- A specialist that is "superior to Jev" must beat Jev here AND beat recency/BM25 on dev, and pass more edge cases than every arm below.

## Metrics

Cells: macro USED-token recall / items keeping every USED block (k/n) / macro evidence-feature coverage. AUC over 0..60% budget (0% = 1.0), normalised to 0-1.

## Dev, all eligible items (325 items, 132925 candidates, USED share of blocks 0.099)

| arm | 10% | 20% | 30% | 40% | 50% | 60% | AUC recall | AUC all-kept | AUC ev-cov |
|---|---|---|---|---|---|---|---|---|---|
| recency | 0.93 / 149/325 / 0.97 | 0.86 / 99/325 / 0.94 | 0.80 / 73/325 / 0.91 | 0.72 / 54/325 / 0.87 | 0.64 / 44/325 / 0.83 | 0.56 / 38/325 / 0.79 | 0.789 | 0.308 | 0.903 |
| bm25 | 0.94 / 127/325 / 0.96 | 0.88 / 84/325 / 0.93 | 0.80 / 54/325 / 0.89 | 0.71 / 42/325 / 0.84 | 0.63 / 34/325 / 0.79 | 0.53 / 23/325 / 0.72 | 0.787 | 0.264 | 0.876 |
| mechanical | 0.92 / 101/325 / 0.97 | 0.85 / 71/325 / 0.93 | 0.79 / 52/325 / 0.89 | 0.72 / 37/325 / 0.85 | 0.64 / 35/325 / 0.81 | 0.56 / 30/325 / 0.75 | 0.784 | 0.243 | 0.887 |
| random | 0.89 / 60.2/325 / 0.96 | 0.78 / 30/325 / 0.92 | 0.68 / 17.8/325 / 0.88 | 0.58 / 10.8/325 / 0.83 | 0.48 / 6.8/325 / 0.77 | 0.38 / 5.2/325 / 0.70 | 0.685 | 0.149 | 0.866 |

Random tie-break AUC (mean of 5 seeds): bm25 recall 0.737 / all-kept 0.159; mechanical recall 0.717 / all-kept 0.154.
Tied share of candidates: bm25 0.76, mechanical 1.00.

Recall AUC by source: recency: claude 0.799 (n=97), codex 0.833 (n=80), hermes 0.759 (n=148); bm25: claude 0.805 (n=97), codex 0.862 (n=80), hermes 0.734 (n=148); mechanical: claude 0.814 (n=97), codex 0.828 (n=80), hermes 0.742 (n=148).

## Dev-model subset (36 items, 17850 candidates, sources {'claude': 12, 'codex': 12, 'hermes': 12})

| arm | 10% | 20% | 30% | 40% | 50% | 60% | AUC recall | AUC all-kept | AUC ev-cov |
|---|---|---|---|---|---|---|---|---|---|
| recency | 0.94 / 16/36 / 0.97 | 0.88 / 12/36 / 0.92 | 0.82 / 8/36 / 0.90 | 0.76 / 8/36 / 0.87 | 0.68 / 7/36 / 0.82 | 0.59 / 4/36 / 0.77 | 0.811 | 0.329 | 0.896 |
| bm25 | 0.93 / 13/36 / 0.95 | 0.87 / 8/36 / 0.91 | 0.79 / 7/36 / 0.85 | 0.74 / 7/36 / 0.80 | 0.64 / 6/36 / 0.76 | 0.53 / 4/36 / 0.72 | 0.789 | 0.282 | 0.855 |
| mechanical | 0.91 / 11/36 / 0.95 | 0.87 / 9/36 / 0.91 | 0.81 / 7/36 / 0.88 | 0.72 / 5/36 / 0.81 | 0.64 / 5/36 / 0.76 | 0.59 / 5/36 / 0.70 | 0.793 | 0.266 | 0.860 |
| specialist | 0.91 / 5/36 / 0.96 | 0.81 / 3/36 / 0.89 | 0.76 / 3/36 / 0.81 | 0.69 / 2/36 / 0.75 | 0.62 / 2/36 / 0.66 | 0.51 / 0/36 / 0.59 | 0.758 | 0.153 | 0.809 |
| specialist_inv | 0.89 / 6/36 / 0.90 | 0.80 / 5/36 / 0.83 | 0.72 / 2/36 / 0.75 | 0.65 / 2/36 / 0.71 | 0.58 / 1/36 / 0.65 | 0.48 / 0/36 / 0.59 | 0.729 | 0.157 | 0.771 |
| random | 0.89 / 6.2/36 / 0.96 | 0.79 / 3.8/36 / 0.92 | 0.69 / 1.8/36 / 0.88 | 0.58 / 1/36 / 0.82 | 0.48 / 0.4/36 / 0.78 | 0.38 / 0.2/36 / 0.72 | 0.686 | 0.145 | 0.869 |

Share of candidates each arm scored: recency 1.00, bm25 1.00, mechanical 1.00, specialist 0.91, specialist_inv 0.91.
Random tie-break AUC: bm25 recall 0.723 / all-kept 0.159; mechanical recall 0.715 / all-kept 0.153; specialist recall 0.734 / all-kept 0.134; specialist_inv recall 0.705 / all-kept 0.139.
Recall AUC by source: recency: claude 0.752 (n=12), codex 0.882 (n=12), hermes 0.800 (n=12); bm25: claude 0.814 (n=12), codex 0.865 (n=12), hermes 0.688 (n=12); specialist: claude 0.748 (n=12), codex 0.813 (n=12), hermes 0.713 (n=12); specialist_inv: claude 0.724 (n=12), codex 0.759 (n=12), hermes 0.704 (n=12).

## Laya subset (nested in dev-model) (18 items, 7477 candidates, sources {'claude': 6, 'codex': 6, 'hermes': 6})

| arm | 10% | 20% | 30% | 40% | 50% | 60% | AUC recall | AUC all-kept | AUC ev-cov |
|---|---|---|---|---|---|---|---|---|---|
| recency | 0.94 / 9/18 / 0.99 | 0.86 / 7/18 / 0.92 | 0.81 / 5/18 / 0.90 | 0.73 / 5/18 / 0.87 | 0.69 / 5/18 / 0.86 | 0.58 / 2/18 / 0.77 | 0.804 | 0.380 | 0.904 |
| bm25 | 0.96 / 7/18 / 1.00 | 0.88 / 4/18 / 0.95 | 0.78 / 4/18 / 0.86 | 0.73 / 4/18 / 0.82 | 0.62 / 3/18 / 0.75 | 0.54 / 2/18 / 0.69 | 0.792 | 0.296 | 0.870 |
| mechanical | 0.91 / 5/18 / 0.95 | 0.86 / 4/18 / 0.90 | 0.81 / 3/18 / 0.87 | 0.73 / 2/18 / 0.83 | 0.63 / 2/18 / 0.77 | 0.57 / 2/18 / 0.68 | 0.786 | 0.241 | 0.861 |
| specialist | 0.94 / 3/18 / 0.99 | 0.86 / 2/18 / 0.93 | 0.82 / 2/18 / 0.81 | 0.75 / 1/18 / 0.78 | 0.70 / 1/18 / 0.73 | 0.60 / 0/18 / 0.66 | 0.813 | 0.167 | 0.845 |
| specialist_inv | 0.91 / 3/18 / 0.95 | 0.83 / 3/18 / 0.85 | 0.78 / 1/18 / 0.80 | 0.72 / 1/18 / 0.76 | 0.67 / 1/18 / 0.71 | 0.57 / 0/18 / 0.66 | 0.780 | 0.167 | 0.815 |
| laya | 0.91 / 2/18 / 0.98 | 0.81 / 2/18 / 0.90 | 0.74 / 1/18 / 0.81 | 0.67 / 1/18 / 0.74 | 0.61 / 1/18 / 0.73 | 0.50 / 0/18 / 0.65 | 0.748 | 0.148 | 0.832 |
| random | 0.90 / 3.4/18 / 0.96 | 0.80 / 2/18 / 0.92 | 0.69 / 0.6/18 / 0.89 | 0.59 / 0.4/18 / 0.85 | 0.49 / 0.2/18 / 0.80 | 0.39 / 0/18 / 0.72 | 0.694 | 0.144 | 0.878 |

Share of candidates each arm scored: recency 1.00, bm25 1.00, mechanical 1.00, specialist 0.90, laya 0.84, specialist_inv 0.90.
Random tie-break AUC: bm25 recall 0.733 / all-kept 0.122; mechanical recall 0.722 / all-kept 0.126; specialist recall 0.771 / all-kept 0.130; laya recall 0.717 / all-kept 0.139; specialist_inv recall 0.738 / all-kept 0.130.
Recall AUC by source: recency: claude 0.758 (n=6), codex 0.851 (n=6), hermes 0.803 (n=6); bm25: claude 0.827 (n=6), codex 0.825 (n=6), hermes 0.724 (n=6); specialist: claude 0.742 (n=6), codex 0.876 (n=6), hermes 0.820 (n=6); laya: claude 0.734 (n=6), codex 0.725 (n=6), hermes 0.786 (n=6); specialist_inv: claude 0.724 (n=6), codex 0.793 (n=6), hermes 0.823 (n=6).

Laya warnings by kind: {'laya_context_limit_exceeded': 356, 'laya_batch_N_failed': 16}.

## jev-overlap (43 items, 16500 candidates; excluded {'test_split_or_unmatched': 11, 'no_used_candidate': 6})

| arm | 10% | 20% | 30% | 40% | 50% | 60% | AUC recall | AUC all-kept | AUC ev-cov |
|---|---|---|---|---|---|---|---|---|---|
| recency | 0.89 / 15/43 / 0.95 | 0.84 / 14/43 / 0.94 | 0.73 / 10/43 / 0.87 | 0.66 / 9/43 / 0.86 | 0.61 / 7/43 / 0.81 | 0.54 / 6/43 / 0.77 | 0.752 | 0.308 | 0.885 |
| bm25 | 0.93 / 17/43 / 0.98 | 0.89 / 12/43 / 0.93 | 0.81 / 10/43 / 0.87 | 0.76 / 7/43 / 0.85 | 0.68 / 5/43 / 0.82 | 0.56 / 5/43 / 0.73 | 0.809 | 0.291 | 0.884 |
| mechanical | 0.89 / 9/43 / 0.95 | 0.78 / 6/43 / 0.88 | 0.74 / 6/43 / 0.86 | 0.68 / 5/43 / 0.80 | 0.63 / 4/43 / 0.76 | 0.56 / 4/43 / 0.69 | 0.749 | 0.207 | 0.847 |
| specialist | 0.93 / 10/43 / 0.95 | 0.88 / 8/43 / 0.93 | 0.81 / 5/43 / 0.88 | 0.70 / 4/43 / 0.76 | 0.62 / 4/43 / 0.69 | 0.54 / 4/43 / 0.63 | 0.784 | 0.211 | 0.837 |
| specialist_inv | 0.92 / 10/43 / 0.94 | 0.85 / 6/43 / 0.85 | 0.81 / 6/43 / 0.83 | 0.73 / 5/43 / 0.76 | 0.64 / 5/43 / 0.68 | 0.55 / 4/43 / 0.63 | 0.787 | 0.215 | 0.813 |
| laya | 0.92 / 9/43 / 0.92 | 0.85 / 6/43 / 0.87 | 0.74 / 2/43 / 0.77 | 0.68 / 2/43 / 0.74 | 0.60 / 2/43 / 0.68 | 0.51 / 2/43 / 0.62 | 0.758 | 0.169 | 0.798 |
| jev | 0.94 / 19/43 / 0.97 | 0.90 / 16/43 / 0.96 | 0.84 / 12/43 / 0.93 | 0.78 / 9/43 / 0.90 | 0.67 / 7/43 / 0.86 | 0.56 / 5/43 / 0.81 | 0.818 | 0.337 | 0.922 |
| random | 0.89 / 10/43 / 0.95 | 0.80 / 6.4/43 / 0.91 | 0.70 / 4.8/43 / 0.86 | 0.61 / 4.2/43 / 0.82 | 0.51 / 2.6/43 / 0.76 | 0.42 / 2.2/43 / 0.70 | 0.703 | 0.196 | 0.860 |

Share of candidates each arm scored: jev 1.00, specialist 0.90, specialist_inv 0.90, laya 0.84, recency 1.00, bm25 1.00, mechanical 1.00.
Random tie-break AUC: jev recall 0.815 / all-kept 0.327; specialist recall 0.773 / all-kept 0.195; specialist_inv recall 0.776 / all-kept 0.199; laya recall 0.747 / all-kept 0.163; bm25 recall 0.804 / all-kept 0.258; mechanical recall 0.720 / all-kept 0.181.

Paired items vs Jev (USED recall higher / lower than Jev on the same item):

- specialist: 10% +17/-18; 20% +16/-21; 30% +18/-21; 40% +18/-21; 50% +21/-17; 60% +24/-16
- specialist_inv: 10% +15/-18; 20% +15/-21; 30% +19/-17; 40% +20/-17; 50% +23/-14; 60% +25/-14
- laya: 10% +13/-21; 20% +18/-20; 30% +14/-26; 40% +16/-24; 50% +19/-19; 60% +19/-20
- recency: 10% +8/-22; 20% +10/-22; 30% +11/-25; 40% +10/-26; 50% +17/-19; 60% +16/-22
- bm25: 10% +11/-18; 20% +11/-22; 30% +12/-21; 40% +16/-20; 50% +18/-18; 60% +15/-21
- mechanical: 10% +10/-25; 20% +8/-29; 30% +12/-26; 40% +11/-27; 50% +16/-21; 60% +19/-20

## Edge-case suite (35 synthetic cases, pass k/35)

| arm | 30% | 50% | 70% | scored share |
|---|---|---|---|---|
| oracle | 35 | 35 | 35 | - |
| recency | 7 | 7 | 4 | - |
| bm25 | 21 | 20 | 18 | - |
| drop_largest | 17 | 17 | 17 | - |
| drop_smallest | 14 | 11 | 11 | - |
| mechanical | 22 | 21 | 18 | - |
| specialist | 16 | 8 | 5 | 1.00 |
| specialist_inv | 22 | 13 | 10 | - |
| laya | 21 | 14 | 11 | 1.00 |
| random | 18.4 | 11.8 | 5.2 | - |

Jev: not run on the edge suite (no saved scores; no remote calls allowed). Oracle = gold upper bound. Random = mean of 5 seeds. Scored share < 1: blocks over the arm's window are unscored and, by the shared rule, dropped last, so the arm drops only the short scored blocks, which is where most must-keep evidence sits. Since the 2026-10-12 size balancing the edge blocks are short enough that every model arm scores all of them (scored share 1.00), so edge failures are ranking failures. drop_largest / drop_smallest are content-blind size controls.

## Cost per item

| arm | score ms median | p90 | blocks/s | model load ms | peak RSS MB | threads | note |
|---|---|---|---|---|---|---|---|
| bm25 | 17.0 | 33.7 | - | - | - | - | stdlib, 40 dev items |
| mechanical | 51.2 | 207.4 | - | - | - | - | LCC _score_mechanically in-process, 40 dev items |
| specialist | 31268.5 | 164478 | 8.74 | 8019 | 2152.7 | 4 | CPU; dev-model subset (specialist) / Laya subset (laya) |
| laya | 165941.5 | 706785 | 1.76 | 14978 | 3144.0 | 4 | CPU; dev-model subset (specialist) / Laya subset (laya) |

Recency and random need no scoring. Jev: see matched-budget-v1 (remote, ~$0.58 median per item).
