# Human label review v2 (Portuguese) — result 2026-10-08

Reviewer: project owner, the target LCC user, not the corpus author. Single reviewer,
one pass, 60 Portuguese authored items (30 supported, 30 UNKNOWN) via revisao.html.
Raw answers: `review-result.csv` (as downloaded), merged into `packet.csv`; score in
`score.json`. Exploratory point observation, not a measured population rate.

## Point counts

| Stratum | Agree | Disagree | Ambiguous | Unclear | Agreement | Rule |
|---|---:|---:|---:|---:|---:|---|
| pt / supported / authored | 11 | 18 | 1 | 0 | .367 | ≥ .90 |
| pt / unknown / authored | 14 | 15 | 1 | 0 | .467 | ≥ .90 |
| Overall | 25 | 33 | 2 | 0 | .417 | ≥ .95 |

Gate: FAIL. 22 of 33 disagreements carry no corrected label. Two corrections equal the
proposed label (HR-056, HR-057), i.e. internally inconsistent answers. 11 of 12 labels
have at least one non-agreement; `git_worktree_edits` and `retry_attempts` 4/4.

## Interpretation (limits first)

The reviewer said beforehand that the material is "too technical" for him, and v1 was
cancelled because the questions did not make sense (../human-review-v1/CANCELLED.md).
No item was marked `unclear`, yet the inconsistencies above show that difficulty. So this
result cannot separate wrong labels from questions the target user cannot judge. It
does not certify the labels, and it does not prove them wrong.

What it does show: the authored corpus is not something its target user can read and
confirm. Together with every learned candidate failing out-of-training (see
../../../docs/08-roadmap.md, Status 2026-10-08), this supports the
goal-family-corpus-v1 PLAN direction: stop expanding authored technical corpora and
build the next review on genuine LCC requests, where the reviewer judges his own intent.

## Decision

- Labels of the current authored corpus remain human-unreviewed for adoption purposes.
- No relabelling from this pass (single uncertain reviewer, 22 uncorrected disagreements).
- Next human review: genuine LCC requests from the opt-in request log, with an LLM
  proposing the label and the requester confirming intent.
