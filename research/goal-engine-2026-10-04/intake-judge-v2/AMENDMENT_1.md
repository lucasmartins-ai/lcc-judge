# Intake judge v2, amendment 1 (2026-10-24): export format defect, found after the dev run

Written after the dev results of all 9 configs were seen, and before any held-out prompt exists or is read
(the held-out period started at 2026-10-24T00:00Z and has not been built). The owner chose this fix on
2026-10-24, knowing it comes after seeing dev numbers.

## The defect

`research/intake_judge_v2.py:export` stored the model's row indices as an explicit JSON list (49,152
integers for family B, about 330 KB). The rows are always contiguous ranges by construction
(`family_rows`). Because of that list, every B config measured 2.17 MB, over the 2 MB A/B budget, and B was
ineligible. The weights themselves were inside budget (1.38 MB raw float16, 1.83 MB as base64).

## The fix and what it does not change

- The format now stores the ranges (`[[start, end], ...]`) instead of the list. `Judge` expands them on load.
- The 9 exported model files are converted in place. The float16 weights and the bias are copied byte for
  byte; nothing is refit. A check asserts that every converted file holds the same weights as before.
- Every grid row is then re-measured with the same code as the original run: dev predictions, owner-dev
  accuracy, latency, RSS and file size. The selection rule, the grid, the budgets, the teacher labels and
  the split are unchanged.
- The pre-fix table stays in this folder as `FREEZE-prefix.json`. It is not committed as a freeze.

## Disclosed risk

This changes which config is eligible after its dev score was known. The expected effect is that B (text
plus previous turn) becomes eligible, and it has the highest dev macro-F1 among eligible configs. The
held-out test is untouched by this, and it remains the only evidence: the pick must still beat v1 there,
with a CI lower bound above 0.
