# Intake judge v3, amendment 2 (2026-10-24): three model votes on the external gold, owner decides

Written before the external gold was drawn and before any held-out text was read. The owner proposed this on
2026-10-24 and chose where it applies and when the votes are shown.

## Scope

Only the **external gold** (100 items, amendment 1) changes. The owner-future gold keeps the v2 design:
two blind passes and no model output on screen.

## Voters

All three see the same input: the taxonomy-v2 system prompt from the v2 teacher, and each request as
`{"previous_agent_turn", "request"}`, in batches of up to 20.

| voter | how | why it is there |
|---|---|---|
| Claude Opus 5.5 | `claude -p --model opus`, the v2 teacher command, unchanged | the teacher family (see risk below) |
| Codex `gpt-6.1-sol` | `codex exec -s read-only --ephemeral --output-schema`, answers limited to the 14 ids by the schema, run in an empty directory | a non-Anthropic family |
| Gemini "Argon" | gemini.google.com through the owner's browser bridge, in a temporary chat ("Chat momentâneo") so nothing joins his history | a non-Anthropic family |

All external prompts come from public datasets (MIT, ODC-BY). No owner text is sent to Codex or Gemini.

## The page and what is stored

1. The owner sees the prompt and its previous turn, and picks a category or "unsure". No vote is visible.
2. After that pick, the page shows the three votes. The owner confirms or changes.
3. Both picks are stored: `blind` and `final`.

## Gold and views (acceptance unchanged)

- **Primary external gold:** `final`. Items marked "unsure" are excluded.
- **Sensitivity views,** reported next to it:
  - `blind`;
  - majority of Codex + Gemini + owner-blind, which leaves out the teacher-family vote;
  - the items where all three models agree.
- **Also reported:**
  - how often `final` differs from `blind`;
  - when it changed, which voter it moved toward;
  - pairwise agreement between voters.

## Risk stated now

The Claude vote is the teacher's own family. v3 is trained on Opus labels, and Opus is also an arm. If the
owner leans on that vote, `final` drifts toward the teacher and inflates both the v3 and the Opus arms. The
`blind` view and the Codex + Gemini + owner-blind view exist to show whether that happened. If v3 passes
acceptance 2 on `final` but not on the `blind` view, the results say so, and v3 does not ship on that
evidence alone.
