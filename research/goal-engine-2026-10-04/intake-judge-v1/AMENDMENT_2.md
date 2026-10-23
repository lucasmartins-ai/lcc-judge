# Intake judge v1, amendment 2 (2026-10-23): two owner passes

Written after the owner returned the gold labels and before any arm was scored on them. Nothing was evaluated
on the held-out prompts before this file was committed.

## What happened

The owner labelled the same 150 drawn prompts twice, at two different moments, without seeing any model
output either time. Both files are stored in `~/.lcc/intake-v1/gold/`; only their hashes are here.

| pass | sha256 | labelled | "unsure" |
|---|---|---:|---:|
| pass1 | `22519c29f130cf9556ab597ee77347faa0419a84e721b9524ef801a735ea7780` | 150 | 0 |
| pass2 | `8f9f4092f812a5a12395e638061be08cc2d6acee8d20c89fea60aeb3a9678e93` | 148 | 2 |

The two passes agree on **116 of 150** items (0.773). That is the owner's own consistency on this taxonomy
from prompt text alone, and a ceiling for any arm (MEDIDO).

## Rule (replaces "Held-out gold" for scoring; acceptance rules unchanged)

- **Primary gold:** the 116 items both passes label alike. An item the owner labelled two ways has no single
  answer, so it cannot score an arm as right or wrong.
- **Sensitivity views:** pass1 alone (150 items) and pass2 alone (148 items), scored with the same arms and
  the same three acceptance checks. They are reported next to the primary view, not instead of it.
- **No top-up.** The 120-item floor was written for items lost to "unsure". The primary set falls to 116
  because of disagreement, not "unsure", and a top-up would need two passes again. The CIs will be wider; the
  results say so.
- All views come from one run. Opus is called once per item over the union of ids (cached), so every view
  sees the same Opus answers.

## Code change after the freeze

Only `research/intake_v1.py` changed, and only its evaluation part: `evaluate` now takes one CSV per pass,
builds the three views and scores each with `_score` (the same metrics, bootstrap and acceptance as frozen).
New sha256 `06cf4291788523abbd3f57c2e899c9a9ad6c98f3adf491e2c5ae25cf89076da6`. The model, the inference code,
the keyword baseline and the teacher prompt still match their `FREEZE.json` hashes (checked before this
commit).
