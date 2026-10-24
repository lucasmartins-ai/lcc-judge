# Intake judge v3, amendment 1 (2026-10-24): the public Claude Code set is one person

Written after counting rows and metadata of the downloaded files, before any prompt text was read, labelled or
used to train. The owner chose this change on 2026-10-24.

## What the counts showed (MEDIDO)

- `armand0e/claude-fable-5-claude-code`:
  - 63 sessions, 553 user messages, of which 318 are human prompts of 1–1,000 characters;
  - every session was sent within 5 days;
  - the card asks others to contribute, and the file holds no sign of more than one contributor.
  - Read as one developer (INFERIDO). A held-out of about 13 of these sessions would measure one extra
    person, not generalisation.
- WildChat-4.8M shards 0–3, after the protocol's filter (English or Portuguese, not toxic, an assistant
  turn with a fenced code block):
  - English: 9,698 conversations, 27,274 prompts, 3,593 distinct hashed IPs;
  - Portuguese: 131 conversations, 441 prompts, 64 hashed IPs.
- No other public set with a usable licence and many people using coding agents was found (search of
  2026-10-24, recorded in the session).

## Changes

1. **WildChat is split by person.** 20% of hashed IPs go to an external held-out pool,
   `random.Random(20261025)` over sorted hashes. Train and dev use the other IPs only; dev is 20% of those
   IPs.
2. **Training sample:** all Portuguese prompts from train/dev IPs, then English prompts up to 3,000 in all,
   seeded. Half and half is impossible with 441 Portuguese prompts.
3. **Claude Code public:** the split stays by session (20% held-out). Every train/dev prompt is
   teacher-labelled; there are far fewer than 4,000.
4. **External gold (owner, one pass):** 100 items in all.
   - Stratum "another agent user": up to 30 Claude Code held-out prompts, at most 2 per session.
   - Stratum "other people asking for code": the rest from the WildChat held-out pool, at most 1 per IP.
     Portuguese is taken first, up to 20, then English.
   - Order is shuffled. The page shows no source.
5. **Acceptance 2** (external superiority) is computed on the pooled external gold, and also reported per
   stratum. Acceptance 1 and 3 are unchanged.
6. **Teacher cap:** unchanged at 600 calls (about 165 needed).
