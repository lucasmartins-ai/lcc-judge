# Specialist v2: frozen test results (next-action labels)

Generated once by `python -m research.specialist_v2_test run` under the pre-registered TEST_PROTOCOL.md / test_protocol.json (sha256 9f39a0bb8e2fed7d...). Counts and metrics only, no session text. No retraining or tuning after this run.

## Limits (read first)

- INFERIDO: the labels are rule-based next-action evidence (the v2 extractor, applied to test for the first time in this run), not human judgement. They lean recent and drop evidence the goal itself names; a high score means "keeps what the agent reused next", not "keeps what a person would keep".
- Model choices (target, size penalty, LR over GBDT) were made on dev and looked at the edge suite; the edge suite is synthetic, single-author gold, 35 cases, so criterion ii is not held-out evidence.
- Jev did not run on test (paid remote calls). The Jev comparison stays on jev-overlap dev; beating Jev on test needs an owner-approved paid run. The jev_test_overlap row below (if any) uses saved v0.1 scores.
- Latency and RSS were measured on a shared, loaded machine (load average 63.8 on 10 cores); treat them as an upper bound.
- Session groups, not items, are the independent unit: the bootstrap resamples groups.

## Verdict

- Overall: **FAIL** (i PASS, ii FAIL, iii FAIL).
- (i) v2 vs baselines on primary (AUC above and CI lower bound > 0): recency:recall PASS; recency:all_kept PASS; bm25:recall PASS; bm25:all_kept PASS; mechanical:recall PASS; mechanical:all_kept PASS.
- (ii) edge: 30% v2 24 vs best other 22 PASS; 50% v2 20 vs best other 21 FAIL; 70% v2 13 vs best other 18 FAIL.
- (iii) cost: ms_median 196.0 (limit 250.0) PASS; ms_p90 484.3 (limit 1000.0) PASS; peak_rss_mb 307.7 (limit 300.0) FAIL.

## Counts

- Test items 675; excluded {"no_used_candidate": 51, "no_agent_action": 21}; eligible 603; content-linked to train/dev 142 {"train": 127, "dev": 76}.
- Primary: 461 items in 71 session groups, per source {"claude": 181, "codex": 82, "hermes": 198}; 207654 candidate blocks, 21028 USED.

## primary (461 items)

| arm | 10% | 20% | 30% | 40% | 50% | 60% | AUC recall | AUC all-kept | AUC ev-cov |
|---|---|---|---|---|---|---|---|---|---|
| specialist_v2 | 0.98 / 323/461 / 0.99 | 0.95 / 197/461 / 0.98 | 0.91 / 120/461 / 0.96 | 0.84 / 78/461 / 0.94 | 0.77 / 54/461 / 0.91 | 0.67 / 34/461 / 0.87 | 0.879 | 0.369 | 0.952 |
| recency | 0.92 / 185/461 / 0.97 | 0.84 / 121/461 / 0.94 | 0.75 / 83/461 / 0.90 | 0.68 / 65/461 / 0.88 | 0.60 / 53/461 / 0.84 | 0.53 / 47/461 / 0.79 | 0.759 | 0.275 | 0.903 |
| bm25 | 0.94 / 156/461 / 0.96 | 0.87 / 94/461 / 0.93 | 0.79 / 64/461 / 0.89 | 0.71 / 55/461 / 0.84 | 0.62 / 43/461 / 0.79 | 0.51 / 30/461 / 0.72 | 0.779 | 0.238 | 0.877 |
| mechanical | 0.93 / 123/461 / 0.97 | 0.87 / 80/461 / 0.94 | 0.80 / 63/461 / 0.91 | 0.73 / 51/461 / 0.87 | 0.65 / 42/461 / 0.82 | 0.57 / 33/461 / 0.77 | 0.792 | 0.219 | 0.898 |
| random | 0.89 / 70.4/461 / 0.96 | 0.79 / 35.4/461 / 0.93 | 0.69 / 23.6/461 / 0.89 | 0.59 / 16/461 / 0.84 | 0.49 / 12/461 / 0.78 | 0.39 / 7.8/461 / 0.71 | 0.693 | 0.142 | 0.875 |

Paired bootstrap, mean(v2 - baseline) per-item AUC [95% CI], groups resampled: recency: recall +0.1193 [+0.0998, +0.1435], all-kept +0.0935 [+0.0526, +0.1538]; bm25: recall +0.0992 [+0.0783, +0.1143], all-kept +0.1309 [+0.0910, +0.1737]; mechanical: recall +0.0863 [+0.0678, +0.1107], all-kept +0.1495 [+0.1112, +0.1816].

| source | n | specialist_v2 recall / all-kept | recency recall / all-kept | bm25 recall / all-kept | mechanical recall / all-kept |
|---|---|---|---|---|---|
| claude | 181 | 0.888 / 0.341 | 0.780 / 0.271 | 0.794 / 0.237 | 0.795 / 0.202 |
| codex | 82 | 0.907 / 0.515 | 0.743 / 0.270 | 0.797 / 0.297 | 0.788 / 0.283 |
| hermes | 198 | 0.859 / 0.333 | 0.747 / 0.281 | 0.759 / 0.213 | 0.792 / 0.208 |

| category | n | specialist_v2 recall / all-kept | recency recall / all-kept | bm25 recall / all-kept | mechanical recall / all-kept |
|---|---|---|---|---|---|
| UNKNOWN | 22 | 0.896 / 0.375 | 0.675 / 0.220 | 0.791 / 0.204 | 0.774 / 0.129 |
| approve_or_pick | 61 | 0.917 / 0.415 | 0.805 / 0.348 | 0.815 / 0.325 | 0.807 / 0.251 |
| correct_approach_or_rule | 15 | 0.833 / 0.294 | 0.747 / 0.267 | 0.769 / 0.228 | 0.761 / 0.222 |
| environment_and_infra | 9 | 0.901 / 0.269 | 0.770 / 0.241 | 0.767 / 0.176 | 0.751 / 0.102 |
| external_accounts_and_comms | 10 | 0.888 / 0.275 | 0.822 / 0.175 | 0.818 / 0.192 | 0.855 / 0.175 |
| failure_report | 13 | 0.888 / 0.314 | 0.769 / 0.160 | 0.810 / 0.237 | 0.823 / 0.135 |
| general_question | 4 | 0.757 / 0.292 | 0.669 / 0.479 | 0.893 / 0.438 | 0.844 / 0.396 |
| git_ship | 21 | 0.872 / 0.329 | 0.814 / 0.349 | 0.811 / 0.262 | 0.823 / 0.309 |
| handoff_prompt | 7 | 0.849 / 0.250 | 0.787 / 0.131 | 0.708 / 0.083 | 0.745 / 0.083 |
| project_audit_or_direction | 1 | 0.689 / 0.083 | 0.648 / 0.417 | 0.774 / 0.083 | 0.752 / 0.083 |
| revise_recent_output | 20 | 0.895 / 0.388 | 0.820 / 0.342 | 0.794 / 0.254 | 0.816 / 0.217 |
| specified_task | 14 | 0.879 / 0.280 | 0.732 / 0.202 | 0.783 / 0.191 | 0.712 / 0.095 |
| supply_fact_or_step_done | 48 | 0.866 / 0.370 | 0.770 / 0.246 | 0.818 / 0.243 | 0.800 / 0.186 |
| task_status_or_control | 33 | 0.843 / 0.293 | 0.734 / 0.227 | 0.780 / 0.265 | 0.768 / 0.222 |
| unlabelled | 183 | 0.879 / 0.403 | 0.743 / 0.280 | 0.748 / 0.214 | 0.792 / 0.243 |

## all_eligible (603 items)

| arm | 10% | 20% | 30% | 40% | 50% | 60% | AUC recall | AUC all-kept | AUC ev-cov |
|---|---|---|---|---|---|---|---|---|---|
| specialist_v2 | 0.98 / 436/603 / 0.99 | 0.95 / 284/603 / 0.98 | 0.91 / 185/603 / 0.96 | 0.85 / 130/603 / 0.94 | 0.78 / 94/603 / 0.91 | 0.69 / 64/603 / 0.87 | 0.886 | 0.404 | 0.953 |
| recency | 0.92 / 249/603 / 0.96 | 0.84 / 165/603 / 0.93 | 0.76 / 113/603 / 0.90 | 0.70 / 91/603 / 0.88 | 0.62 / 75/603 / 0.85 | 0.54 / 64/603 / 0.80 | 0.770 | 0.284 | 0.903 |
| bm25 | 0.94 / 228/603 / 0.96 | 0.87 / 137/603 / 0.93 | 0.80 / 92/603 / 0.89 | 0.72 / 78/603 / 0.84 | 0.64 / 60/603 / 0.79 | 0.54 / 44/603 / 0.73 | 0.791 | 0.254 | 0.880 |
| mechanical | 0.93 / 172/603 / 0.96 | 0.86 / 113/603 / 0.93 | 0.80 / 86/603 / 0.90 | 0.73 / 70/603 / 0.86 | 0.66 / 58/603 / 0.82 | 0.57 / 44/603 / 0.77 | 0.793 | 0.227 | 0.894 |
| random | 0.89 / 99.4/603 / 0.96 | 0.79 / 49.2/603 / 0.93 | 0.69 / 32.8/603 / 0.88 | 0.59 / 22.8/603 / 0.84 | 0.49 / 17.8/603 / 0.78 | 0.39 / 12.4/603 / 0.71 | 0.692 | 0.146 | 0.874 |

Paired bootstrap, mean(v2 - baseline) per-item AUC [95% CI], groups resampled: recency: recall +0.1157 [+0.0990, +0.1376], all-kept +0.1205 [+0.0885, +0.1724]; bm25: recall +0.0948 [+0.0779, +0.1101], all-kept +0.1504 [+0.1150, +0.1854]; mechanical: recall +0.0925 [+0.0742, +0.1185], all-kept +0.1769 [+0.1403, +0.2035].

| source | n | specialist_v2 recall / all-kept | recency recall / all-kept | bm25 recall / all-kept | mechanical recall / all-kept |
|---|---|---|---|---|---|
| claude | 181 | 0.888 / 0.341 | 0.780 / 0.271 | 0.794 / 0.237 | 0.795 / 0.202 |
| codex | 166 | 0.915 / 0.538 | 0.776 / 0.302 | 0.815 / 0.315 | 0.783 / 0.287 |
| hermes | 256 | 0.865 / 0.362 | 0.758 / 0.281 | 0.773 / 0.226 | 0.798 / 0.206 |

| category | n | specialist_v2 recall / all-kept | recency recall / all-kept | bm25 recall / all-kept | mechanical recall / all-kept |
|---|---|---|---|---|---|
| UNKNOWN | 33 | 0.892 / 0.429 | 0.666 / 0.230 | 0.802 / 0.260 | 0.762 / 0.169 |
| approve_or_pick | 71 | 0.912 / 0.433 | 0.807 / 0.354 | 0.815 / 0.330 | 0.809 / 0.257 |
| correct_approach_or_rule | 18 | 0.846 / 0.329 | 0.746 / 0.264 | 0.777 / 0.213 | 0.759 / 0.218 |
| environment_and_infra | 13 | 0.920 / 0.404 | 0.810 / 0.282 | 0.781 / 0.218 | 0.774 / 0.160 |
| external_accounts_and_comms | 16 | 0.851 / 0.276 | 0.811 / 0.193 | 0.788 / 0.234 | 0.855 / 0.151 |
| failure_report | 18 | 0.906 / 0.394 | 0.796 / 0.227 | 0.839 / 0.269 | 0.831 / 0.213 |
| general_question | 4 | 0.757 / 0.292 | 0.669 / 0.479 | 0.893 / 0.438 | 0.844 / 0.396 |
| git_ship | 28 | 0.895 / 0.420 | 0.811 / 0.339 | 0.827 / 0.277 | 0.828 / 0.309 |
| handoff_prompt | 21 | 0.889 / 0.329 | 0.795 / 0.123 | 0.792 / 0.155 | 0.741 / 0.099 |
| project_audit_or_direction | 3 | 0.879 / 0.500 | 0.797 / 0.306 | 0.840 / 0.250 | 0.781 / 0.083 |
| revise_recent_output | 29 | 0.913 / 0.451 | 0.789 / 0.322 | 0.826 / 0.279 | 0.804 / 0.236 |
| specified_task | 18 | 0.884 / 0.375 | 0.754 / 0.282 | 0.786 / 0.273 | 0.680 / 0.130 |
| supply_fact_or_step_done | 54 | 0.877 / 0.421 | 0.781 / 0.281 | 0.824 / 0.289 | 0.803 / 0.204 |
| task_status_or_control | 37 | 0.846 / 0.302 | 0.737 / 0.216 | 0.778 / 0.245 | 0.764 / 0.207 |
| unlabelled | 240 | 0.884 / 0.421 | 0.764 / 0.293 | 0.764 / 0.228 | 0.798 / 0.252 |

## Old specialist (v1) subset (36 primary items, seeded 12 per source)

| arm | 10% | 20% | 30% | 40% | 50% | 60% | AUC recall | AUC all-kept | AUC ev-cov |
|---|---|---|---|---|---|---|---|---|---|
| specialist_v2 | 0.99 / 25/36 / 1.00 | 0.97 / 16/36 / 0.99 | 0.93 / 12/36 / 0.99 | 0.84 / 8/36 / 0.96 | 0.77 / 4/36 / 0.93 | 0.67 / 3/36 / 0.88 | 0.890 | 0.391 | 0.968 |
| recency | 0.92 / 14/36 / 0.95 | 0.85 / 9/36 / 0.94 | 0.77 / 9/36 / 0.91 | 0.71 / 7/36 / 0.89 | 0.63 / 7/36 / 0.87 | 0.53 / 5/36 / 0.81 | 0.774 | 0.308 | 0.911 |
| bm25 | 0.96 / 14/36 / 0.97 | 0.88 / 9/36 / 0.92 | 0.80 / 7/36 / 0.88 | 0.71 / 6/36 / 0.84 | 0.59 / 4/36 / 0.76 | 0.49 / 3/36 / 0.68 | 0.779 | 0.276 | 0.869 |
| mechanical | 0.95 / 14/36 / 0.97 | 0.89 / 10/36 / 0.95 | 0.83 / 9/36 / 0.91 | 0.76 / 6/36 / 0.88 | 0.68 / 6/36 / 0.84 | 0.56 / 4/36 / 0.75 | 0.815 | 0.301 | 0.905 |
| random | 0.89 / 5.2/36 / 0.96 | 0.80 / 3.4/36 / 0.92 | 0.70 / 2.4/36 / 0.88 | 0.58 / 1.4/36 / 0.80 | 0.49 / 1.2/36 / 0.75 | 0.38 / 0.6/36 / 0.67 | 0.691 | 0.148 | 0.857 |
| specialist_v1 | 0.94 / 8/36 / 0.93 | 0.85 / 4/36 / 0.83 | 0.79 / 3/36 / 0.77 | 0.72 / 2/36 / 0.72 | 0.61 / 1/36 / 0.65 | 0.52 / 1/36 / 0.62 | 0.781 | 0.169 | 0.786 |

Paired bootstrap v2 - v1: recall +0.1083 [+0.0627, +0.1569], all_kept +0.2222 [+0.1282, +0.2879].

## Jev, saved v0.1 scores on frozen-60 dossiers in test (11 items; descriptive)

| arm | 10% | 20% | 30% | 40% | 50% | 60% | AUC recall | AUC all-kept | AUC ev-cov |
|---|---|---|---|---|---|---|---|---|---|
| specialist_v2 | 0.99 / 6/11 / 0.99 | 0.98 / 4/11 / 0.99 | 0.86 / 1/11 / 0.89 | 0.81 / 0/11 / 0.83 | 0.71 / 0/11 / 0.81 | 0.62 / 0/11 / 0.78 | 0.861 | 0.250 | 0.899 |
| recency | 0.91 / 2/11 / 0.98 | 0.85 / 1/11 / 0.96 | 0.68 / 0/11 / 0.84 | 0.62 / 0/11 / 0.83 | 0.56 / 0/11 / 0.82 | 0.49 / 0/11 / 0.75 | 0.729 | 0.129 | 0.883 |
| bm25 | 0.93 / 3/11 / 0.97 | 0.88 / 2/11 / 0.96 | 0.80 / 1/11 / 0.91 | 0.73 / 1/11 / 0.85 | 0.64 / 1/11 / 0.79 | 0.50 / 0/11 / 0.65 | 0.789 | 0.204 | 0.883 |
| mechanical | 0.92 / 1/11 / 0.96 | 0.87 / 1/11 / 0.94 | 0.83 / 1/11 / 0.92 | 0.77 / 1/11 / 0.91 | 0.62 / 0/11 / 0.78 | 0.53 / 0/11 / 0.71 | 0.794 | 0.144 | 0.895 |
| random | 0.87 / 0.6/11 / 0.94 | 0.78 / 0.6/11 / 0.92 | 0.69 / 0.6/11 / 0.90 | 0.59 / 0.6/11 / 0.87 | 0.50 / 0.6/11 / 0.83 | 0.41 / 0.6/11 / 0.76 | 0.687 | 0.133 | 0.889 |
| jev | 0.94 / 3/11 / 0.98 | 0.87 / 1/11 / 0.96 | 0.80 / 1/11 / 0.94 | 0.70 / 1/11 / 0.93 | 0.62 / 1/11 / 0.89 | 0.55 / 1/11 / 0.87 | 0.784 | 0.197 | 0.941 |

## Edge suite (35 synthetic cases)

| arm | 30% | 50% | 70% |
|---|---|---|---|
| oracle | 35 | 35 | 35 |
| recency | 7 | 7 | 4 |
| bm25 | 21 | 20 | 18 |
| drop_largest | 17 | 17 | 17 |
| drop_smallest | 14 | 11 | 11 |
| mechanical | 22 | 21 | 18 |
| specialist | 16 | 8 | 5 |
| specialist_inv | 22 | 13 | 10 |
| laya | 21 | 14 | 11 |
| random | 18.4 | 11.8 | 5.2 |
| specialist_v2 | 24 | 20 | 13 |

v2 fails @50%: coreference_cause, general_question_drop_all, git_state_commit_own_work, handoff_prompt, huge_log_middle_error, long_session_over_32k, negation_rule, outreach_history, project_audit_wide_view, pt_en_mixed, qualifier_exception, retry_failed_action, source_authority, structured_config_block, unrecoverable_read.

## Cost (fresh process, numpy + LCC mechanical pass, 1 thread)

- 461 items (median 431 blocks, max 2177): median 196.0 ms, p90 484.3 ms, max 2632.9 ms, 4 items over 1 s; 184.7 ms median on the 212 items with 250-600 blocks; peak RSS 307.7 MB; load 109 ms; model 4 KB.

## Post-run notes (2026-10-13)

- The secondary `all_eligible` view (603 items) includes the 142 items content-linked to
  train/dev forks, so it is optimistic; quote the primary population (461 items) only.
- Production requirement before integrating into LCC: block metadata (message index, role,
  kind, tool) must come structured from LCC's splitter, not be parsed from block text.
  The offset-0 header rule (065f60f) is a research-time mitigation; a block that starts
  inside a large tool output can still begin with a header-shaped line.
- After the run, the latency-bench temp file in specialist_v2.py and specialist_v2_test.py
  moved to `tempfile.mkstemp` (fresh 0600 name, no truncation of a stale file, no symlink
  follow). Scoring code is unchanged; the frozen hashes in test_protocol.json refer to the
  pre-change files used for this run.
