# Intake judge v3: pre-registered protocol

Written on 2026-10-24, while the public files were downloading and before any public row was read. Only the
dataset cards, licences, column names and the first preview row of the Claude Code set were seen. Owner
decisions taken on 2026-10-24: use both public sets below; the owner labels the external gold (100 items,
one pass).

## Why v3

v1 and v2 learn from one person: the owner's prompts (78% Portuguese, Claude Code and Hermes). The
taxonomy and the gold labels are his too. Nothing so far measures whether the category works for other
developers, and LCC is a public tool. v3 adds public data from other people. It is tested on two held-outs:
the owner's future prompts and prompts from people the model never saw.

## Data

| source | what | licence | use |
|---|---|---|---|
| owner | `~/.lcc/intake-v2` records and teacher labels, v2 split (cutoff 2026-10-24) | private | train/dev |
| public Claude Code | `armand0e/claude-fable-5-claude-code`, 1 parquet, real Claude Code sessions donated and anonymised by their authors | MIT | train/dev and **external held-out** |
| WildChat | `allenai/WildChat-4.8M`, shards 0–3 | ODC-BY | train/dev only |

Files: `~/.lcc/public/`. Their sha256 values go in the build receipt. Nothing from them is committed. Text
from both public sets passes LCC's `redact` before storage, the same as the owner's records.

**Prompt extraction (both public sets)**
- A prompt is a user message with string text, not a tool result, and not starting with `<`.
- Only `harness == claude_code` sessions are used from the Claude Code set.
- Prompts of 1–1,000 characters only, as for the owner.
- The previous turn is the last 600 characters of the assistant's text before the prompt.

**WildChat filter**
- Language Portuguese or English. Rows flagged toxic are excluded.
- A conversation counts as coding if any assistant turn contains a fenced code block.
- Up to 3,000 prompts, seeded with `random.Random(20261025)`, aiming at half Portuguese and half English when
  both are available.

**Claude Code split, by session**
- 20% of sessions go to the external held-out, `random.Random(20261025)` over sorted session ids.
- Of the rest, 20% of sessions go to dev.
- At most 4,000 prompts are teacher-labelled, seeded sample over train and dev.

## Teacher

- The v2 teacher, unchanged: Opus 5.5 with the previous turn, the v2 system prompt (sha256 in the v2
  freeze), and the same CLI safety rules.
- Cap: 600 CLI calls for v3 labelling, plus the final Opus arm.

## Candidates (fixed grid, 6 configs)

- **Family:** B from v2 (prompt and previous turn n-grams, `research/intake_judge_v2.py`, range export).
- **Training data:**
  - (ii) owner train + public Claude Code train;
  - (iii) as (ii), plus WildChat.
- **C:** 3, 10 or 30.

## Selection (dev only)

- **Score:** mean of owner-dev macro-F1 and public-dev macro-F1, both against teacher labels.
- **Eligible** if all three hold:
  - the B budget from v2 (median at most 5 ms, p90 at most 20 ms, at most 2 MB, RSS at most 100 MB);
  - owner-dev macro-F1 at least 0.480 (the v2 pick's 0.490 minus 0.01);
  - accuracy on the owner's 116 v1 gold items at least 0.509.
- **Pick:** the highest score; ties go to fewer training items.
- **Threshold:** display threshold chosen on the pooled dev, by the v2 rule.
- **Freeze:** `FREEZE.json` is pushed before either held-out gold is drawn.

## Held-out gold

1. **Owner future:** the v2 held-out (sessions from 2026-10-24) and the same owner gold, two passes.
   - v3 must be frozen and pushed before that gold is drawn.
   - The v2 and v3 evaluations then read the same gold. Each one runs once.
   - If the v2 gold is drawn before v3 is frozen, v3 skips this held-out and an amendment says so.
2. **External:** 100 prompts from the Claude Code held-out sessions.
   - Sampling: at most 2 per session, seeded.
   - The page shows the previous turn and nothing from any model.
   - The owner labels them in one pass; "unsure" items are excluded.

## Arms

- v3 pick.
- The model shipped in LCC when the test runs (v1, or v2 if it has replaced v1).
- The v2 pick.
- Keyword rules.
- Majority class.
- Opus 5.5 with the previous turn.

## Acceptance (paired session-group bootstrap, 2000 resamples, seed 20261025, 95% CI)

1. **Owner, non-inferior:** v3 minus shipped accuracy on the owner gold has a CI lower bound above −0.03.
2. **External, superior:** v3 minus shipped accuracy on the external gold has a CI lower bound above 0.
3. **Cost:** the B budget, re-measured on the gold prompts.

v3 replaces the shipped model if 1–3 pass. Reported but not gating:
- macro-F1;
- v3 against Opus, against keyword rules and against the v2 pick;
- per category, per language, and with/without a previous turn.

## Stated before the run

- The external gold is labelled by the owner, so it still carries his reading of the taxonomy. It measures
  other people's prompts, not other people's judgement.
- The public Claude Code set is donated by people who chose to share. They are probably heavy users, so it is
  not a random sample of LCC users.
- The taxonomy came from the owner's prompts. If many external prompts land in UNKNOWN or get forced into
  a wrong category, the results report it, and the taxonomy is the next fix, not the model.
- Results are INFERIDO; counts are MEDIDO.
