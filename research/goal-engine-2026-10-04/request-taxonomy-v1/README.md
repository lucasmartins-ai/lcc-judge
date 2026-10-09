# Genuine-request taxonomy v1 — 2026-10-09

Replaces the authored retry/UDP/git field catalog as the target for what LCC must
decide. Built from the owner's real agent prompts (genuine-requests-v1), keyed on
**what context the agent needs**, not topic.

Method: seeded stratified sample of 619 of 3,782 redacted prompts (source x language,
seed 20261009) split into 6 disjoint chunks; 6 independent LLM coders open-coded one
chunk each; one LLM synthesized 13 categories + UNKNOWN (`taxonomy.json`); 3 LLM
labelers labeled all 619 (`label-counts.json`: 368 high / 212 medium / 39 low confidence).

All labels are LLM proposals. Owner confirmation: 56 items (4 per label, lowest
confidence first) via `python3 -m research.request_taxonomy_review page`, scored with
`... score <result.csv>`. Prompt texts, labels per id and the review page live only in
`~/.lcc/request-log/taxonomy-v1/`; this folder holds definitions and counts only.

Status: exploratory, single LLM labeling pass, not human-confirmed yet.
