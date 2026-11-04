# Intake judge v3, amendment 5 (2026-11-04): the owner gold follows v2 amendment 2

Written before the owner gold is drawn. The owner held-out is shared with v2, and its changes are in
[`intake-judge-v2/AMENDMENT_2.md`](../intake-judge-v2/AMENDMENT_2.md):
- built now at 66 qualifying sessions;
- one blind pass plus Claude, Codex (`xhigh`) and Gemini Argon ("Alto") votes, the design of the external gold.

For v3:
- **Acceptance 1** (v3 minus shipped accuracy, CI lower bound above −0.03) is computed on the owner `final`
  view and on the owner `blind` view. v3 ships only if both pass, with acceptance 2, 2b and 3 already passed
  in `external-test-results.json`.
- **`owner-test-results.json`** also reports the non-teacher majority and the all-three-agree views. These two
  views do not gate shipping.
- **Gold ids and votes** stay private in `~/.lcc/intake-v3/gold/`. The draw receipt is `owner-draw.json`.
