# Specialist v4: selection rule (pre-declared)

Written and committed on 2026-10-13, before any v4 candidate was scored on dev or on the edge suite.
Code: `research/specialist_v4.py` (`select` phase implements this rule verbatim).

## Candidates (10 configs, fixed grid)

Score = mean(base members' logits) + beta x teacher logit - 0.5 x log(chars) + 3.0 x floor(k_goal 1, k_err 2).
The size penalty and floor are v3's and do not change.

- **base** in {`v3`, `v3n`}
  - `v3`: the frozen v2 LR + frozen v2 GBDT (v3's members, 50 features).
  - `v3n`: the frozen v2 GBDT + a new LR (`lrg4`) on the 50 v2 features + 14 new features (EXTRA in
    `specialist_v4.py`), with v2's target (USED or goal-shared), train rows only, v2's fit_lr defaults. No
    dev tuning.
- **beta** in {0, 0.25, 0.5, 1, 2}
  - teacher = LR on the same 64 features, fitted to Claude Opus 5.5 keep-probabilities (soft labels) for the
    targeted train blocks (`llm_judge_arm --set train`). Every item has the same total weight. fit_lr defaults.
- `v3` with beta 0 is v3 itself (the control). `v3n` with beta 0 measures the new features without Opus.

## Rule

1. **Eligible** iff, on all eligible dev items (next-action v2 labels, strict USED):
   - recall AUC >= v3, and
   - all-kept AUC >= v3, and
   - edge-suite passes >= v3 at each of the 30, 50 and 70% cuts.
2. **Pick** the eligible config with the most edge passes summed over the three cuts. Break ties by max dev
   recall AUC + 0.25 x all-kept AUC.
3. **Adopt** v4 only if the pick's edge total is strictly above v3's (28 + 23 + 20 = 71). Otherwise v4 is not
   adopted, and v3 stays the shipped specialist.
4. **Report** for the pick vs v3:
   - paired group-bootstrap CIs on dev (2000 resamples over session groups, seed 20261013);
   - edge counts per cut and per category;
   - RSS and latency on dev, with v3's method.
5. **Budgets** (hard; failing any one means v4 is not adopted):
   - peak RSS < 250 MB on dev;
   - median latency < 300 ms;
   - model file < 1 MB.

## Disclosure

- The edge suite takes part in this rule (steps 1 and 2), so v4's edge counts are not held-out evidence.
- The 14 new features were designed after reading the fixtures of the 12 edge cases v3 fails at 50%, so the
  features also looked at the edge suite.
- Dev decides eligibility only. No hyperparameter is tuned on dev.
- Honest evidence needs the post-2026-10-12 held-out set (`research/heldout_v3.py`).
