# Intake judge v2, amendment 2 (2026-11-04): build the owner held-out now; one blind pass plus three model votes

Written before the owner gold is drawn and before any held-out prompt, model output or label is seen. Known at
writing: counts only. 70 held-out sessions, 66 qualifying, 667 prompts; the gold pool would hold 132 items from
70 sessions (2 dropped as text seen in train/dev), 116 with a previous turn. The owner asked for this on
2026-11-04 so the result comes sooner. It covers the owner gold shared by v2 and v3 (v3 amendment 5).

## Changes

1. **Trigger.** The held-out is built now, at 66 qualifying sessions. The protocol already accepts 60 as its
   floor (on 2026-11-30). Only the date moves.
   - The gold keeps its size rule: at most 150 items, at most 2 per session. Today that is 132 items; at 100
     sessions it would be 150.
   - A smaller gold widens the confidence intervals. That makes every acceptance test harder to pass, not
     easier.
   - The drawn ids are frozen at the draw: their sha256 goes in `intake-judge-v3/owner-draw.json`, and
     sessions that start later are not used.
2. **Gold design.** The two blind passes at least 24 hours apart become one pass with three model votes, the
   design of the v3 external gold (v3 amendment 2).
   - The page shows the prompt and the agent's previous turn. The owner picks a category or "unsure" with no
     vote visible (`blind`), then sees the votes and confirms or changes (`final`).
   - Voters, all on the v2 teacher system prompt and the same `{previous_agent_turn, request}` input, in
     batches of up to 20:
     - Claude Opus 5.5: the v2 teacher command, unchanged.
     - Codex `gpt-6.1-sol` at reasoning effort `xhigh`, schema-limited to the 14 ids, in an empty directory.
       The external gold ran at the CLI default, `max`.
     - Gemini "Argon" at reasoning level "Alto", through the owner's Chrome bridge, in a temporary chat.
3. **Gold views.**
   - Primary: `final`, with "unsure" excluded.
   - Sensitivity: `blind`; the majority of Codex + Gemini + owner-blind, which leaves out the teacher-family
     vote; and the items where all three models agree.
4. **Opus arm.** The Opus arm of the test is the Claude vote. It is the same command the protocol names for
   that arm, so no second Opus call is made.
5. **Acceptance.** The rules and margins are unchanged, and the model ships only if they pass on both `final`
   and `blind`.
   - For v2, that means acceptance 1–3 on both views.
   - If a model passes on `final` but not on `blind`, the results say so, and the model does not ship on that
     evidence.

## Privacy

Before this amendment, only Claude saw owner text. Codex (OpenAI) and Gemini (Google) now also receive the
drawn owner prompts and previous turns, at most 132 items. The owner approved this on 2026-11-04.

- The text has already passed LCC's `redact` at import.
- Gemini runs in a temporary chat, which does not join the owner's history.
- Codex runs `--ephemeral` and read-only.
- The repo still gets ids, counts and hashes only.

## Disclosed risks

- Seeing the votes can pull `final` toward the teacher. The `blind` gate and the non-teacher majority view
  exist to show this.
- One pass gives no test-retest check. v1's two passes agreed on 116 of 150 items, so single-pass labels carry
  that much noise; the noise is the same for every arm.
- The draw happens after the owner chose to stop waiting, but before any held-out label or prediction is
  known.
