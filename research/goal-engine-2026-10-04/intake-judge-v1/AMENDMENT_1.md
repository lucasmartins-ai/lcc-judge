# Intake judge v1, amendment 1 (2026-10-23)

Written after the split and the first teacher batch, before any model was fit and before any held-out text
was read. None of these changes touches the acceptance rules, the margins or the arms.

1. **Trainer.** No research venv on this machine has scikit-learn, and v2/v3 were trained with numpy. v1
   uses the same route: `research/intake_v1.py:fit`, multinomial logistic regression with class-balanced
   sample weights, L2 penalty `||W||^2 / (2 C n)` (scikit-learn's convention for the same C), full-batch
   Adam (lr 0.05, 400 steps), deterministic. Class weighting is fixed now, not tuned. The grid is unchanged.
2. **Model format.** 2^15 hashed buckets, binary features, L2-normalised per prompt; weights stored as
   base64 float16 in one JSON file (`lcc-intake-judge/1`). Dev scores are computed from that exported
   file, the same artifact LCC would vendor. Inference: `research/intake_judge.py`, stdlib only.
3. **Split as built** (`split-counts.json`): train 2,482 items / 551 sessions, dev 525 / 137, held-out
   1,158 / 147. The held-out is smaller than the 1,311 counted at writing because a session that started
   before the cutoff stays in train/dev with all its prompts, as the protocol says.
4. **Owner-judged items.** 64 of the 83 map onto the new import by source and timestamp (exact text when
   the timestamp is missing or shared). 19 do not: most Codex history before 2026-10 is no longer on disk.
   The teacher stop rule (agreement at least 0.75) is computed on the 64.
5. **Teacher.** 20 prompts per call, 4 calls in parallel, answers constrained to the 14 ids by a JSON schema.
   The exact system prompt is saved next to the labels and hashed in `FREEZE.json`.
