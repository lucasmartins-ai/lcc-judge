# Specialist v3: final test on the post-cutoff held-out set

Generated once by `python -m research.v3_final_test final` under V3_FINAL_TEST_PROTOCOL.md (sha256 fb6bdd2ec55311a4...). Counts and aggregates only; no session text. No tuning after the build.

## Limits (read first)

- INFERIDO: labels are rule-based next-action evidence (what the agent reused next), which favours v3's training target. The generalists judge generic relevance. This measures fit to the owner's sessions, not general reading skill.
- Small sample: 193 primary items in 36 session groups; the LLM subset has 36 items (one per group). CIs are wide.
- Latency and RSS measured on a shared machine (load average 99.6).
- Session groups are the resampling unit of the paired bootstrap (2000 resamples, seed 20261016).

## Verdicts (MEDIDO on this set; interpretation INFERIDO)

1. Local baselines (CI lower bound > 0, both metrics, each baseline): **PASS** — recency:recall PASS; recency:all_kept PASS; bm25:recall PASS; bm25:all_kept PASS; mechanical:recall PASS; mechanical:all_kept PASS.
2. v3 vs opus (36 items): recall **inferior**, all-kept **inferior**; headline "superior": **no** (recall -0.0085 [-0.0551, +0.0310], all-kept +0.0694 [-0.0278, +0.1667]).
2. v3 vs gemini-flash (36 items): recall **not inferior**, all-kept **superior**; headline "superior": **no** (recall +0.0382 [-0.0072, +0.0828], all-kept +0.1181 [+0.0255, +0.2199]).
3. Cost: **PASS** — ms_median 177.9 (limit 250.0) PASS; ms_p90 566.7 (limit 1000.0) PASS; peak_rss_mb 97.5 (limit 300.0) PASS.

## Population

- Build receipt: 208 items, 36 groups, per source {"claude": 195, "codex": 3, "hermes": 10}, manifest sha256 bb32679d69de2155....
- Excluded {"no_used_candidate": 13, "no_agent_action": 2}; eligible 193; content-linked to train/dev 0; primary 193 in 36 groups, per source {"claude": 182, "codex": 3, "hermes": 8}; 65161 candidate blocks, 7663 USED.

## Primary (193 items): all local arms

| arm | recall AUC | all-kept AUC | recall @30% | all-kept @30% | recall @60% | all-kept @60% |
|---|---:|---:|---:|---:|---:|---:|
| specialist_v3 | 0.8994 | 0.4344 | 0.9244 | 0.3731 | 0.7126 | 0.1192 |
| recency | 0.8181 | 0.3057 | 0.8285 | 0.1969 | 0.6017 | 0.1399 |
| bm25 | 0.8029 | 0.2703 | 0.8173 | 0.1710 | 0.5421 | 0.0777 |
| mechanical | 0.8292 | 0.2379 | 0.8417 | 0.1451 | 0.6087 | 0.0829 |
| random | 0.6891 | 0.1380 | 0.6891 | 0.0466 | 0.3901 | 0.0052 |

Paired bootstrap mean(v3 − arm) per-item AUC [95% CI]: recency: recall +0.0813 [+0.0666, +0.0974], all-kept +0.1287 [+0.0686, +0.2014]; bm25: recall +0.0965 [+0.0657, +0.1363], all-kept +0.1641 [+0.0994, +0.2477]; mechanical: recall +0.0702 [+0.0437, +0.1015], all-kept +0.1965 [+0.1336, +0.2829].

| source | n | specialist_v3 recall / all-kept | recency recall / all-kept | bm25 recall / all-kept | mechanical recall / all-kept |
|---|---|---|---|---|---|
| claude | 182 | 0.906 / 0.438 | 0.823 / 0.311 | 0.809 / 0.276 | 0.835 / 0.240 |
| codex | 3 | 0.823 / 0.361 | 0.809 / 0.194 | 0.758 / 0.083 | 0.778 / 0.139 |
| hermes | 8 | 0.771 / 0.375 | 0.714 / 0.219 | 0.683 / 0.219 | 0.727 / 0.219 |

| category | n | specialist_v3 recall / all-kept | recency recall / all-kept | bm25 recall / all-kept | mechanical recall / all-kept |
|---|---|---|---|---|---|
| UNKNOWN | 1 | 1.000 / 0.917 | 1.000 / 1.000 | 1.000 / 1.000 | 1.000 / 1.000 |
| approve_or_pick | 12 | 0.913 / 0.285 | 0.848 / 0.160 | 0.834 / 0.160 | 0.836 / 0.160 |
| unlabelled | 180 | 0.898 / 0.442 | 0.815 / 0.312 | 0.800 / 0.274 | 0.828 / 0.239 |

## All eligible (193 items; secondary)

| arm | recall AUC | all-kept AUC | recall @30% | all-kept @30% | recall @60% | all-kept @60% |
|---|---:|---:|---:|---:|---:|---:|
| specialist_v3 | 0.8994 | 0.4344 | 0.9244 | 0.3731 | 0.7126 | 0.1192 |
| recency | 0.8181 | 0.3057 | 0.8285 | 0.1969 | 0.6017 | 0.1399 |
| bm25 | 0.8029 | 0.2703 | 0.8173 | 0.1710 | 0.5421 | 0.0777 |
| mechanical | 0.8292 | 0.2379 | 0.8417 | 0.1451 | 0.6087 | 0.0829 |
| random | 0.6891 | 0.1380 | 0.6891 | 0.0466 | 0.3901 | 0.0052 |

Bootstrap v3 − arm: recency: recall +0.0813 [+0.0666, +0.0974], all-kept +0.1287 [+0.0686, +0.2014]; bm25: recall +0.0965 [+0.0657, +0.1363], all-kept +0.1641 [+0.0994, +0.2477]; mechanical: recall +0.0702 [+0.0437, +0.1015], all-kept +0.1965 [+0.1336, +0.2829].

## LLM subset (36 items, 36 groups)

- Finished: {"opus": 36, "gemini-flash": 36}; compared on 36 items finished by both arms. Batches cached (= successful CLI calls): {"opus": 1463, "gemini-flash": 1463}; CLI calls made: {"opus": 1480, "gemini-flash": 1465} (cap 2500 per arm); usage-limit waits: {"opus": "1 usage-limit stop (429 at 14:08 BST 2026-10-17; resumed 19:05 after reset); CLI then logged out 19:05-19:47 (12 failed calls + 1 diagnostic, counted)", "gemini-flash": "none"}.
- Unscored blocks (no valid answer): {"opus": 0, "gemini-flash": 7}.

| arm | recall AUC | all-kept AUC | recall @30% | all-kept @30% | recall @60% | all-kept @60% |
|---|---:|---:|---:|---:|---:|---:|
| specialist_v3 | 0.8759 | 0.4167 | 0.8818 | 0.3611 | 0.6787 | 0.1667 |
| opus | 0.8844 | 0.3472 | 0.8995 | 0.3056 | 0.7139 | 0.1111 |
| gemini-flash | 0.8378 | 0.2986 | 0.8473 | 0.2222 | 0.6332 | 0.0833 |
| recency | 0.8124 | 0.2847 | 0.8173 | 0.1667 | 0.5932 | 0.1389 |
| bm25 | 0.7926 | 0.2500 | 0.8064 | 0.1389 | 0.5351 | 0.0556 |
| mechanical | 0.7870 | 0.2269 | 0.7859 | 0.1111 | 0.5546 | 0.1111 |
| random | 0.6876 | 0.1431 | 0.6802 | 0.0389 | 0.3885 | 0.0056 |

Paired bootstrap mean(v3 − arm) [95% CI]: opus: recall -0.0085 [-0.0551, +0.0310], all-kept +0.0694 [-0.0278, +0.1667]; gemini-flash: recall +0.0382 [-0.0072, +0.0828], all-kept +0.1181 [+0.0255, +0.2199]; recency: recall +0.0635 [+0.0275, +0.1003], all-kept +0.1319 [+0.0255, +0.2431]; bm25: recall +0.0833 [+0.0340, +0.1309], all-kept +0.1667 [+0.0671, +0.2616]; mechanical: recall +0.0890 [+0.0386, +0.1504], all-kept +0.1898 [+0.0903, +0.2940].

| source | n | specialist_v3 recall / all-kept | opus recall / all-kept | gemini-flash recall / all-kept |
|---|---|---|---|---|
| claude | 32 | 0.894 / 0.422 | 0.899 / 0.341 | 0.853 / 0.305 |
| codex | 2 | 0.798 / 0.500 | 0.699 / 0.250 | 0.678 / 0.250 |
| hermes | 2 | 0.659 / 0.250 | 0.835 / 0.542 | 0.760 / 0.250 |

| category | n | specialist_v3 recall / all-kept | opus recall / all-kept | gemini-flash recall / all-kept |
|---|---|---|---|---|
| approve_or_pick | 1 | 0.797 / 0.083 | 0.810 / 0.083 | 0.742 / 0.083 |
| unlabelled | 35 | 0.878 / 0.426 | 0.886 / 0.355 | 0.841 / 0.305 |

## Edge suite (stated in the protocol; not a gate, not re-run)

| arm | 30% | 50% | 70% |
|---|---|---|---|
| specialist_v3 | 28 | 23 | 20 |
| opus | 35 | 35 | 35 |
| gemini_flash | 35 | 35 | 34 |

## Cost (fresh process, 1 thread, primary items)

- 193 items (median 296 blocks, max 1149): median 177.9 ms, p90 566.7 ms, max 1251.2 ms, 3 over 1 s; peak RSS 97.5 MB; load 134 ms; model 183 KB.

## Code hashes

- `research/v3_final_test.py` 38760b7c8293085a4d39d3ed2e9813826d73d2fb556e087e88ba1d5679636f3b
- `research/llm_judge_arm.py` c130adcb2ea32a4d43f4e24811f01bc68b432597df6854f4e5e192359fdcc798
- frozen: `model.json` 219cd798d47f, `specialist_v3.py` fff2c2012256, `specialist_v2.py` 6638809ed9b5, `heldout_v3.py` ac6efb45755a; `llm_judge_arm.py` pre-change e203ec94c405.

## Reading and disclosures (added after the run; no number above changed)

- **v3 vs Opus "inferior" means inconclusive, not worse.** The label only says the CI lower bound fell below
  −0.02 on 36 items (one per group). The point estimates are recall −0.0085 (about even) and all-kept +0.0694
  (in v3's favour). The protocol predicted *not inferior* as the likely result; the CIs came out wider than that.
  INFERIDO: on this set v3 and Opus are about level on recall, with no significant gap either way.
- **v3 vs Gemini:** recall *not inferior*, all-kept *superior*. The headline "superior to a generalist" needs
  *superior* on recall, so it does not hold for either generalist.
- **Per source:** 182 of 193 primary items are claude. The codex (3) and hermes (8) rows, and the 2 + 2 items
  on the LLM subset, are anecdotal. On hermes, v3 recall (0.771) is above recency (0.714) on primary, but below
  Opus on the 2 subset items.
- **all_eligible equals primary,** because 0 items were content-linked to train/dev.
- **Subset rule as implemented:** "session" = the builder's lineage `group` (the bootstrap unit). There is one
  `Random(20261016).choice` over each group's sorted item ids, with groups taken in sorted order. There were 36
  groups, below the cap of 40, so the cap and the even split never applied.
- **Unscored blocks** (7 for Gemini, 0 for Opus) follow the same path as earlier runs (`matched_budget.drop_order`):
  a block with no valid answer is kept until only unscored blocks remain.
- **CLI calls vs cached batches.** Opus made 1,480 calls for 1,463 cached batches. The other 17 were:
  - 4 calls that hit the usage limit (HTTP 429, 2026-10-17 14:08 BST). The run stopped and resumed from cache
    after the reset.
  - 12 calls that failed at 19:05 because the Claude CLI was logged out ("Not logged in"). Each shard stopped
    after 3 consecutive failures. The owner logged back in at 19:47, and the run resumed from cache.
  - 1 diagnostic call to read that error.

  Gemini made 1,465 calls for 1,463 batches: 2 failed calls (exit 3), which were retried once on the next chunk
  (`llm_judge_arm`'s rerun-retries-once design). These failed calls were not usage limits. They are disclosed
  as a minor deviation from "no other retries". All are counted against the 2,500 cap.
- **Not verified independently:** `matched_budget.auc` (trapezoid, normalisation) is the same function used by
  every earlier v2/v3 result.

## Independent review

Reviewer: separate read-only agent (Sonnet), 2026-10-18. Verdict: **PASS WITH NOTES**. It found no protocol
violation that changes a verdict. Hashes match the protocol, and the eval code hashes equal the pre-build commit
a2b35ad. The verdict labels are correct for the printed CIs, and 16 unit tests pass. Its notes are folded into
the section above:
- the Opus "inferior" caveat (MED);
- the subset ambiguity, unscored-block handling, the extra CLI calls and the per-source sample sizes (LOW);
- it did not read `mb.auc` itself.
