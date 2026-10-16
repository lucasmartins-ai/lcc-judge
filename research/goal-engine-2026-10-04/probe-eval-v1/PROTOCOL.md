# Probe eval v1: task-outcome probes, verbatim LCC modes vs Claude Code native compaction (frozen 2026-10-16)

Pre-registration only. Written and committed **before any probe is generated, any arm is run or any answer is
scored**. Counts only in the repo; every probe, answer and verdict stays under the private root
`~/.lcc/bench/probe-eval-v1/`. Results are tagged INFERIDO until `gateClaim` returns PASS on them.

## Why

`STATUS.md` lists outcome-based evaluation as the main open gap: every retention number so far is a mechanical
probe or an LLM-judge audit. The market scan of 2026-10-16 (`.scratch/market-gap-2026-10/research.md`,
`evidence/market.md`) found no published task-outcome eval of verbatim compaction. The only rigorous method is
Factory's probe eval (https://factory.com/news/evaluating-compression): after compression, ask recall, artifact,
continuation and decision questions and grade the answers on six 0-5 dimensions. There, every vendor scored worst
on **artifact trail** (2.19-2.45 of 5). Verbatim selection should keep file paths and identifiers by
construction. This protocol tests that, with probes taken from what the agent really did next.

**Stated up front.** LCC lossless and recoverable cut about 1% of tokens on real sessions (`recoverable-v0.8`:
.0093 / .0123 pooled); Jev block cuts 3.5% (`real-context-bench-v0.1`). So the verbatim arms are close to full
context, and the native arm is a summary that is far smaller. H1 is a comparison at each arm's own operating
point, **not a matched-budget claim**. Context tokens per arm are reported next to every score.

## Population (frozen; counted 2026-10-16, counts only, no text read)

Source: the next-action-v1 split (`specialist-v1/labels-receipt.json`, seed 20261012, session-lineage groups, per
source 70/15/15), with v2 labels (`labels-v2-receipt.json`). Item = one real human prompt `P` with its prior
context `C` (rebuilt by the bench adapters, as in `research/next_action_labels.py`) and the agent's window `W`
(what it did after `P`, until the next human prompt, an interrupt, a compaction or the end).

**Primary set D: next-action DEV.** Eligible items:
1. `evidence == 'actions'`;
2. `C` ≤ 150,000 heuristic tokens, so the full arm fits in the answerer's window with room for the probes;
3. at least one **artifact gold path** (definition below).

Count on 2026-10-16: **201 items, 77 session-lineage groups** (hermes 104, claude 61, codex 36), 11.04 M heuristic
tokens of `C` in all (mean 54.9 k). 353 DEV items have agent actions, 340 of them fit, and 201 of those carry an
artifact gold path.

**Jev stratum J.** `matched_budget_v2.jev_overlap()`: the 43 Claude frozen-60 items outside test whose candidate
blocks match a next-action item, for which v0.1 saved real Jev block decisions (40 train, 3 dev, 35 sessions; 30
artifact-eligible). J is analysed on its own and never pooled with D. The 3 dev items that are in both are listed
in the results.

**Not opened, not used.** These are not opened or used in any phase:
- the next-action TEST split (675 items, spent by `specialist-v2-test`);
- the post-2026-10-12 held-out set (`research/heldout_v3.py`, reserved for `V3_FINAL_TEST_PROTOCOL.md`);
- the Hermes v0.6 / v0.7 TEST sets.

The builder refuses to run if any of these holds:
- an item has `split == 'test'`;
- an item's text store is outside the DEV texts manifest (or, for J, outside the frozen-60 dossiers);
- an item's session appears in a `heldout_v3` receipt.

**Disclosure: DEV is not virgin.**
- DEV was read to select the specialist v3 floor and by the 2026-10-13 LLM arms.
- No arm in this eval was trained or tuned on next-action DEV: the native arm has no parameters, and the LCC
  rules contain no learned weights.
- The LCC recoverable rules were adjusted after DEV verdicts on the **recoverable-dev** sets (v0.7 `653eeae`,
  v0.8 `4c39161`), which may share sessions with D.
- Results are therefore also reported on the subset of D whose sessions appear in none of: `lossless-dedup-v1`,
  `recoverable-dev-v1`/`v2`/`v3`, and the `recoverable-v0.8` sets. This is a sensitivity analysis, not the primary.

## What is frozen (sha256)

| frozen file | sha256 |
|---|---|
| private `next-action-v1/splits.json` | `2e808d79e73891e7f25bf911680637c8528fa03ad104b5e6def8308403778aeb` |
| private `next-action-v1/manifest-dev.txt` (= receipt `dev.items_manifest`) | `a18c43023ac6c7d394aac17e1469a61fd741afc9c86fb0604e53ce1ab8324cf7` |
| private `next-action-v1/manifest-dev-texts.txt` | `7f0aa25594a60530e4f26d173016020d78497d594637d2e77c199747d8a173fa` |
| `research/next_action_labels.py` (evidence extractor, path keys) | `26d39fcc54fc116e3256861feabf9839ee85d0028ac727d4941219041bbb185a` |
| `research/real_context_bench.py` (render) | `1d462543b39382113b1f03854d80f6850897f7591787c41c57c936f15604ec5e` |
| `research/codex_context.py` | `60c296094bb37d059195dc9c5354a27d3a1e673122971a518a713f2851b4ed8e` |
| `research/hermes_context.py` | `68793d14f76da188844e1158a08e066a731fd054f92636f15cd4d0b13d764006` |
| `research/matched_budget.py` / `research/matched_budget_v2.py` (J mapping, saved Jev decisions) | `0f05b774dbc4f566ba20a1d130295b9f5cb08c8ac96d629f5f0b07cfd80de4e6` / `58859458a30cf72e76d46ffc4c945893c041a9071b4c1d4c6e03da822ae3843c` |
| `research/recoverable_v08.py` (how the rules arms are driven) | `d5b19fa8f07a95cc512d75f26f8fd77c30fef52d376376783f214fe65fbd7690` |
| `research/recoverable_check_v4.py` / `research/lossless_dedup_measure.py` (independent checks) | `1b25ba3a34ff7fc7521318816168de0bcfb62fc0c85a3ea2050250292b199994` / `8d904ef78bffa83dfd76e42ef1c530e60277a51f138bb5b8fdf7547bdd5d6105` |

**LCC pin:** `origin/main` at `af412b6fdbce78630fa56c3da2bde8dead006383` (2026-10-12), run from a detached
worktree with a clean tree, never from `~/lcc` (other branches are in progress there).

The prompt texts below are frozen by their sha256 (UTF-8, the fenced block body without the fences, trailing
newline included). Each run phase refuses to start if any frozen hash differs.

### Harness freeze (amendment, before any DEV probe)

The harness does not exist yet: `research/probe_eval_v1.py` plus `tests/test_probe_eval_v1.py`. It is written,
then debugged on the pilot (below). It is committed **before** the DEV/J probe build, with its sha256 appended here
as a dated amendment table. After that commit, no code, prompt or criterion changes. A change found necessary
later voids the run, and that run's results are still published.

The pilot may change **code only**, never the prompt texts, gold rules or pass criteria in this file. If a text
must change, a dated amendment section is committed before the DEV build. It states why the text changed and that
no DEV or J output was seen.

## Probes (four types, from what the agent did next)

Gold comes from `W` through the v2 evidence sets of `next_action_labels.py`. A gold feature counts only if it is
`refetched == false` (the agent used it without re-reading it in `W`) and `generic == false`, it is held by at
least one block of `C`, and it is not goal-shared (the extractor already drops features found in `P`). So every
gold answer is in `C` verbatim and was used from memory.

| type | question | gold | primary score |
|---|---|---|---|
| **artifact** | fixed text A (below) | every path feature with rule `path_op` or `edit_anchor` | mechanical path recall |
| **recall** | written by the generator for one target | one feature of kind hex > num > ident > quoted > line, rule `call_value` or `text_ref`; ties broken by `random.Random(20261016)` over sorted feature values | mechanical exact match |
| **continuation** | fixed text K (below) | the first agent tool call in `W` (tool name plus its path or command head) | judge; mechanical target match as sub-score |
| **decision** | written by the generator | a decision, constraint or rejected approach in `C` that `W` followed, with a verbatim support quote from `C` | judge only |

- **Artifact recall (per item).** This is the fraction of gold paths recalled. A gold path is recalled if the
  answer contains the full path, its last-two-component suffix (≥ 12 chars) or its basename (≥ 12 chars). These
  are the same keys and minimums as the extractor. **Hallucinated paths** are paths the extractor finds in the
  answer that occur nowhere in `C` or `P`; they are counted per item.
- **Recall exact match.** The answer contains the target after whitespace collapse. Matching is case-sensitive,
  and numbers must match digit for digit.
- **Generator checks (mechanical, before freezing the probes).**
  - The recall question must not contain the target. It also must not contain any extracted feature that equals,
    contains or is contained by a gold feature of the same item.
  - The decision quote must be a verbatim substring of `C` of 24-300 chars, and it must not occur in `P`.
  - A failed check gets one regeneration with the next-ranked feature, then the probe is dropped and counted.
- **The generator never sees any arm output.** It reads `W` plus these clipped parts of `C`, never the arms:
  - recall: the ±600 chars around each block holding the target;
  - decision: the user and assistant text turns of `C` and the last 3 tool calls, clipped to 30 k tokens from the
    end.

  All probes for D and J are generated once, before any arm runs. They are written to private
  `probes.jsonl`, whose sha256 and counts per type go into a repo receipt (`probe-receipt.json`) committed before
  the arms run.

## Arms

Each arm turns `C` into a context `C'`. The answerer gets `C'`, then `P`, then the item's probes in one numbered
call. No arm sees `W`.

| arm | `C'` |
|---|---|
| `full` | `C` unchanged (rendered as in the bench) |
| `native` | clean-room reimplementation of Claude Code 2.1.296 auto-compact as observed in `.scratch/market-gap-2026-10/evidence/rea-claude-code.md` (below) |
| `lcc_lossless` | LCC `rules_mode=lossless` at the pin, defaults |
| `lcc_recoverable` | LCC `rules_mode=recoverable` at the pin, transcript proxy (no `workspace_root`: no disk snapshots), command pointers off, as in `recoverable-v0.8` |
| `jev_block` (J only) | the saved v0.1 Jev block keep/drop decisions applied to the matched blocks, rendered with LCC's elision marker. No new Jev call is made: **$0 Jev spend** |

**Native arm, step by step.** When the REA notes allow a choice, it is made in the native arm's favour.
1. **Summary.** Claude Opus 5.5 writes the summary from the full `C` with text S (below). This is our own wording
   of the observed 9-section structure; no vendor text is copied. Opus is the strongest model used in the sessions,
   which favours native. The `<analysis>` part is stripped before use. No tool-result clearing is applied first
   (also native-favourable).
2. **Re-attach recent files.** Up to the 5 most recently read files are re-attached after the summary, ≤ 5,000
   tokens each and ≤ 50,000 in all. Offline, the last file-read tool result for each path in `C` stands in for
   the disk re-read.
3. **Preserved messages.** No preserved messages beyond `P`.
4. **Other sources.** The same procedure applies to Codex and Hermes items. The arm is "Claude Code's compaction
   applied here", not each agent's own.

The LCC and Jev outputs are re-checked as in v0.8: lcc's verifier at the pin, plus the independent checks. A
verification violation voids that item for that arm and is reported.

## Models, calls and budget

| role | model | route | effort |
|---|---|---|---|
| probe generator | Claude Opus 5.5 | see budget | high |
| native summarizer | Claude Opus 5.5 | see budget | high |
| answerer (every arm) | Claude Sonnet 5.5 | see budget | medium |
| judge (6 dimensions) | Claude Opus 5.5, blind | see budget | high |
| second judge (agreement only) | Gemini 3.8 Flash (High) via `agy`, on a 10% random sample (seed 20261016) of judged records | subscription | — |

- **Route.** The route is the owner's choice and is fixed before the build, not after. Either:
  - **subscription CLI** (`claude -p`, ANTHROPIC_* stripped, no tools, no settings / CLAUDE.md, as in
    `llm_judge_arm.py`): $0 cash, hard cap **3,000 calls** over all roles;
  - **paid API**: hard cap **$400**. Spend is checked after every call from the returned `usage`, and the run stops
    before a call that could cross the cap.
  - **Approved 2026-10-16 by the owner: subscription CLI, $0 cash, hard cap 3,000 calls over all roles (the pilot
    included).** The paid-API route is not used.
- **Usage-limit stop.** Wait for the reset and resume from cache. Transport errors get 1 retry, nothing else.
- **Failures.** If an answerer or summarizer call still fails, that item is dropped from **every** arm's paired
  comparison and counted. Refusals are counted the same way.
- **Judge blinding.** The judge sees the probe, the gold, the support quote and the answer. It does not see the
  arm name or `C'`. Each item's arm answers are shuffled with `random.Random(20261016)`, and strings that name an
  arm or its markers are masked (the elision and pointer markers, "[Old tool result content cleared]",
  "summary").

### Estimate for the owner to approve (API-equivalent; heuristic tokens × 1.2 for the Claude tokenizer)

Prices: Opus 5.5 $4 / $20, Sonnet 5.5 $2 / $10 per M tokens (input / output). Caching is not counted, so this is
an upper bound.

| phase | calls | input M tok | output M tok | API $ |
|---|---:|---:|---:|---:|
| D: probe generation (Opus) | 201 | 4.6 | 0.4 | 27 |
| D: native summaries (Opus, full `C`) | 201 | 13.2 | 1.2 | 77 |
| D: answers, full + lossless + recoverable (Sonnet) | 603 | 39.6 | 1.8 | 97 |
| D: answers, native (Sonnet, ≤ 55 k tokens each) | 201 | 6.0 | 0.6 | 18 |
| D: judge (Opus) | 804 | 3.2 | 1.2 | 37 |
| J: all phases, 5 arms, 43 items | ~430 | ~15 | ~1.3 | ~61 |
| pilot (≤ 10 train items) | ~60 | ~2 | ~0.2 | ~13 |
| **total** | **~2,500** | **~84** | **~6.7** | **~330** |

Plus about 100 Gemini agreement calls on the subscription. Wall time is about 1-2 days on the subscription,
because of usage-limit resets (v4 hit 3 of them in 1,459 calls).

## Metrics and analysis

- **Unit.** Per-item scores. Paired differences are taken within each item.
- **Primary CIs.** Paired cluster bootstrap over session-lineage groups: 2000 resamples, seed 20261016.
- **Wilson 95% intervals** for per-arm rates:
  - artifact all-recalled (every gold path recalled);
  - recall exact match;
  - items with ≥ 1 hallucinated path.
- **Judge scores.** Mean of each dimension per arm, with the bootstrap CI. The overall score is the mean of the
  six dimensions, as Factory reports it.
- **Tokens.** Context tokens of `C'` per arm (lcc tokenizer), pooled and as the median ratio to `full`.
- **Breakdowns (descriptive).** By source, request category and probe type. Also by **gold position**: whether the
  gold's latest block is in the last 10% of `C`, or in a file the native arm re-attached. This shows recency and
  re-attach effects.

## Hypotheses and pass criteria (declared before scoring)

**Validity gates.** If any gate fails, the run is reported as *invalid*, and no H1 verdict is given.
- V1: `full` mean artifact recall ≥ 0.50 on D. Below that, the probes are not answerable from context.
- V2: ≤ 10% of D items dropped for failures, refusals or verification voids.
- V3: judge agreement between Opus and Gemini, as quadratic-weighted kappa on the artifact_trail dimension,
  ≥ 0.40. Below that, the judge-scored secondaries are marked *unreliable*; the mechanical primary still stands.

**H1 (primary).** Verbatim modes beat the native summary on the artifact trail.
- Test: on D, the mean per-item artifact recall of `lcc_lossless − native`, and separately of
  `lcc_recoverable − native`.
- Bonferroni over the two comparisons: two-sided **97.5%** cluster-bootstrap CIs.
- **H1 PASS iff both lower bounds are > 0.**
- The effect size and the token ratio are reported together.

**Power (INFERIDO).** With n = 201 in 77 groups, an assumed per-item SD of differences of 0.4 and a design effect
of about 2, the minimum detectable difference is about 0.11. Factory's artifact gap between summary methods was
about 0.25 of 5 on a judge scale, which is not comparable. So a null result at n = 201 means "smaller than about
0.1", not "no effect".

**Secondaries.** These are reported with 95% CIs and carry no pass claim of their own.
- S1: the same two contrasts on the judge's artifact_trail dimension.
- S2: non-inferiority to `full` on artifact recall. The lower 95% bound of `lcc_* − full` must be > −0.03.
- S3: the recall exact-match rate, the continuation and decision judge scores, and the six-dimension overall,
  for every arm pair.
- S4: hallucinated paths per item, by arm.
- S5: stratum J, all five arms, descriptive. With 30 artifact-eligible items, no verdict is given.
- S6: H1 recomputed on the rules-clean sensitivity subset of D.

## Leakage controls

V4 (`specialist-v1/V4_DEV_RESULTS.md`) showed two ways a score can measure the method instead of the task:
1. labels that reward what a teacher or rule favours (next-action labels lean recent; Opus labels generic
   relevance);
2. tuning on the very cases being scored (edge-suite fixtures read before the features were designed).

This protocol blocks both, and the related leaks below:

| leak | control |
|---|---|
| Answer inside the question | Mechanical check: the recall question shares no gold feature with the item (above). Artifact and continuation questions are fixed text. |
| Answer inside `P` or trivially kept by every arm | Goal-shared features are already dropped from gold. Gold position (tail / re-attached) is reported, so effects carried only by the tail are visible. |
| Gold derived from an arm | Gold comes only from `W` and `C`, through the frozen extractor. Probes are hashed and committed before any arm runs. |
| Generator or judge seeing arm outputs | The generator never reads `C'`. The judge is blind to the arm and to `C'`, with shuffled order and masked markers. |
| Judge self-preference (Opus summarizer, Opus judge) | The primary is mechanical. A cross-family second judge checks agreement (V3). |
| Lean-recent next-action labels | Only `refetched == false` evidence counts. The gold-position breakdown is reported. Recall and artifact gold are what the agent used from memory, not what it re-read. |
| Tuning on the scored set | Prompts are frozen here. The pilot runs on ≤ 10 TRAIN items that are: not in J, not quarantined as content-linked to DEV (`labels-v2-receipt.json`), and drawn with `random.Random(20261016)`. Pilot outputs are never used to choose gold rules or thresholds. |
| Sessions shared between sets | D and J are analysed separately. The bootstrap resamples whole lineage groups. The 3 shared items are listed. |

## Frozen texts

### A — artifact question (sha256 `627757be019d5f12987c0d47ae50eefa459b1eeed237c9c1b838fbb1c76ef831`)

```
Before you act on this request, list every file you expect to read or change for it. Give the full paths exactly as they appear in this session, one per line.
```

### K — continuation question (sha256 `caeb0cc9c00c5f2f89c89777d48948ef237f01d2766dc92af208a9a634c2bbff`)

```
What is the first concrete action you would take for this request? Name the tool or command and its exact target (path, command or identifier).
```

### Q — answerer instructions (sha256 `794b78435fdeac124751562a1a43356983699452c44cbb7b13dae98c8373d9a5`)

```
You are continuing a coding-agent session. The context above is everything you have from the session so far; parts of it may have been compressed. You have no tools. Answer each numbered question from that context only. Be specific: give exact paths, names, values and commands as they appear. If the context does not tell you, write "unknown" instead of guessing.
```

### S — native summary instructions, clean-room (sha256 `ea72d62fb0091811dce1ffcc8f2decbb08a028e8790cbbc6f6250399275550e6`)

```
Write a summary of this conversation that will replace it. Work will continue from your summary alone. First reason inside <analysis> tags (this part is removed), then write <summary> with these sections:
1. Primary request and intent.
2. Key technical concepts.
3. Files and code sections: each file read, edited or created, why it matters, and short code snippets where needed.
4. Errors met and how each was fixed.
5. Problem solving done and still open.
6. Every user message that is not a tool result. Keep security-relevant constraints word for word.
7. Pending tasks.
8. Current work, just before this summary.
9. Optional next step, quoting the latest task word for word.
```

### G — probe generator instructions (sha256 `9b48e06117261ec5424255ce6f68216b5afc872393c2809e2df0fa0c91d7379e`)

```
You write probe questions for a memory test of a coding agent. You get excerpts of a session's earlier context, the user's next request, and what the agent did next.
RECALL: you are given one target string that the agent later used. Write one question whose correct answer is exactly that string and that a reader of the full earlier context could answer. Do not write the string, or any identifier, path or number that contains it or is part of it.
DECISION: find one decision, constraint or rejected approach stated in the earlier context that the agent's next actions followed. Write one question about it, a reference answer of 1-2 sentences, and a quote of 24-300 characters copied exactly from the earlier context that supports the answer. If there is none, return null for decision.
Output JSON only: {"recall": {"question": "..."}, "decision": {"question": "...", "answer": "...", "quote": "..."} or null}.
```

### R — judge instructions (sha256 `17ea9fee061cdb4bdcbd6a4f6845fa77b34456d8c16a585468f735a26fd5c7e3`)

```
Blind grader for answers from a coding agent whose earlier context may have been compressed. Each record has a question, a reference answer taken from what the agent really did next, a supporting quote, and the agent's answer. Score the answer from 0 to 5 on each dimension: accuracy (technical details such as paths, names, errors and values are right), context_awareness (reflects the current state of the task), artifact_trail (knows which files were read or changed), completeness (addresses every part of the question), continuity (work could go on without re-fetching anything), instruction_following (answers in the format asked). 0 = fails completely, 3 = adequate with minor issues, 5 = excellent with no issues. Do not reward length. A confident wrong detail is worse than "unknown". Give a specific reason of 5-15 words per record, unique, with no quotes from the data. Output JSON only.
```

## Run order

1. This file, committed (protocol only).
2. The owner approves the route and the cap, recorded as a dated line in this file.
3. Pilot on ≤ 10 train items. Code fixes only.
4. Harness freeze amendment: hashes of `research/probe_eval_v1.py` and its tests, plus the green test log.
5. Build D and J items. The builder asserts the exclusions. Then generate the probes and commit
   `probe-receipt.json` (counts and sha256).
6. Run the arms (summaries and answers), then the verification re-checks.
7. Judge, including the Gemini agreement sample.
8. Score: `RESULTS.md` and `results.json` (counts and aggregates only), `gateClaim` on the headline numbers.

```
PYTHONPATH=<lcc worktree @af412b6>/src:/Users/Master/Downloads/LCC-judge \
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 /Users/Master/LCC/.venv/bin/python \
    -m research.probe_eval_v1 {pilot|build|probes|run --arm <arm>|verify|judge|agree|score}
```
