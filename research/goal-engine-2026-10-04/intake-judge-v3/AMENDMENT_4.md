# Intake judge v3, amendment 4 (2026-10-24): one one-shot evaluation per held-out

Written after the external gold page was built, before the owner returned any external label, and before the
owner-future gold exists.

The protocol scores v3 on two held-outs, and they become available about ten days apart. The evaluation as
frozen wrote one results file, needed both golds in the same run, and refused a second run. Running it on the
external gold alone would have spent the owner gold unread.

## Change

`research/intake_v3.py:evaluate` now writes one file per held-out, and each run happens once:
- `external-test-results.json`: acceptance 2 (on `final`), the `blind` check from amendment 2, and
  acceptance 3 (cost);
- `owner-test-results.json`: acceptance 1, plus each owner pass as a sensitivity view.

The metrics, bootstrap, views and margins are unchanged, and so are the model, the pick and the gold
files. v3 ships only when all of acceptance 1, 2 (and 2b) and 3 pass across the two files.
