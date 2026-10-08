# Actual varied-state development data, bilingual connected supervision

The capture/data phase is complete and audited. It repairs coverage gaps in the
previous authored development population. It produces **no new model quality or
LCC outcome result**; previous candidates remain rejected and the full goal active.

## Measured captures

| Population | Seed | Fixtures | Independently recounted fields | Capture seconds |
|---|---:|---:|---:|---:|
| Excluded exposed calibration |442600|16|288|1.024674|
| Development train |442601|64|1,152|1.934019|
| Development validation |442602|32|576|1.242572|

Each original request was executed once, without selective retries or host tool
fallback. All captures are MEASURED with zero infrastructure errors. Retry has
first-call success, retried success and expected operation exhaustion. UDP has
full, prefix and zero read budgets, including empty payloads; unread messages are
unobserved, not proven lost. All received-counter wording explicitly qualifies
the recorded receiver read budget. Git has eight authored clean/staged/worktree/
mixed/deletion/addition modes, variable counts and NUL-delimited unusual paths.
Index edits compare HEAD with index, including staged deletions outside the
current index; worktree edits compare index with disk. Scheduled sleep, observed
sleep and whole elapsed duration are distinct retained measurements.

Independent stdlib audits recount actual callbacks/timestamps, sent/read payloads,
HEAD/index Git blob identities and status/disk bytes. All 18 fields match. Raw
fixture-content intersections train:validation/train:calibration/validation:calibration
are zero. These are actual APIs in **author-created local fixtures**, not sampled
production sessions, wire/IP capture or independently reviewed P2 ground truth.

## Execution identity and failed preparation

Fixed worker profile `trusted-tool-relation-states/0.2`, Linux arm64/Python3.13.16,
Git2.47.3/Tenacity9.1.4. Image
`sha256:4c21136ee6a6af5e49e2ee3d46317eeff1927bdde4163ca65f990495a4837985`;
runtime source SHA `5ded8f3bdf45d3e420c889d15e8dd38b2e95a631b2209eab0ab931f6638717a3`;
dependency SHA `255600482631fdd1a04f299af2f0f1e748d783caafa896bdee322fce18f099bf`.
Requests cannot supply executable code, argv, imports, paths or network addresses.
Container captures are confined with network none and unavailable captures UNKNOWN.

Two parent-image FROM recipes failed before any capture: a bare local digest was
interpreted as a registry name; the local repository digest was inspectable but
BuildKit still attempted registry resolution. `build.log` and `build-v2.log` remain.
Successful `build-recipe-v3/` uses the original immutable Python base and exact
SHA-checked 31 Debian packages/Tenacity wheel installed offline. No host package
installation or mutation of previous worker/image sources. Build `--network=none`
controls RUN instructions; it does not establish all build metadata access was
offline. The new private dependency copies are ignored by Git.

## Frozen labels, inputs and tokenizer recount

Cohort SHA `82eb8ca05308cb985a22908eddf695253be5318ea4dd2bc3d636686b3d4cd30a`;
latest design SHA `0c0d269123ee2abedb78cfd60d3bce97573f4b836cfcbfaccc4f83987b212ebb`;
supervision SHA `b921938d794b597e068a25aad7375d7968e49d18a8d463e12219163626371c05`.
Earlier design declarations remain and were superseded **before** label derivation
for explicit import reexport and scoped UDP wording. Raw observations did not change.

Every fixture includes all52competing-field pairs:49complete within-tool edges
and3cross-tool bridges;18roles form one component, degrees3..8. Four known goal
aliases/four report captions/EN+PT report language are crossed independently using
a shuffled32-way factorial, twice in train/once in validation. Both query languages
occur per fixture. Report form/level vary separately; validation query wrappers
differ. All tools, primitive fields, aliases, captions and pair edges are seen in
train; **there is no novel tool/primitive/pair confirmation**. Some language was
already exposed in prior studies. No annotation role IDs, truth or commands enter
the model strings.

Labels mean explicit requested field equality, narrower than general relevance.
Each competing pair uses measured/value-swap claims under both objectives, with
identical per-goal positive/negative numeric multisets. False requested claims
remain relevant contradictions. Derived/multifield, diagnosis and broad usefulness
queries reuse each field's vocabulary but are semantic UNKNOWN, never binary
negatives. Missing structural bindings bypass learned scoring as UNKNOWN.

| Recounted supervision | Train | Validation |
|---|---:|---:|
| Authored rows |60,288|30,144|
| Binary rows |53,248|26,624|
| Semantic UNKNOWN rows |6,912|3,456|
| Structural UNKNOWN rows |128|64|
| Unique projected inputs |50,084|23,692|
| Unique negatives / positives / semantic UNKNOWN |25,016 /18,282 /6,786|12,576 /7,660 /3,456|
| Relevant contradiction rows |11,828|5,920|
| Maximum full raw pair tokens |138|137|
| Maximum projected pair tokens |76|76|
| Truncations |0|0|

Content/effective-input/entity intersections between splits are zero. Duplicate
effective labels do not conflict. Row multiplicity is not statistical independence:
there are96development fixtures, not90,432independent observations. Deduplication
changes binary class balance; the next training recipe must use the measured
global class counts. Gzip JSONL retains all complete rows/views with SHA identities.
Pinned tokenizer is mMARCO XLM-R revision8008f0154ca2387468013ed439df09d70c122412,
local-only,512pair window. Both full and projected token counts were independently
recounted; projection is not a DROP policy or a useful dossier-context claim.

## Verification and next decision

221tests pass with0skips16.880s, including local LCC integration; scoped RuffF/E9
passes. Logs: `../goal-full-tests-varied-tool-states-final.log` and
`scoped-ruff-supervision.log`. Trailing UNKNOWN in the test log is a mocked failed
capture regression, not a failed actual request. Zero model forwards/API/P2/default/
hosting/publication in this phase. No new weights or trained-epoch claims exist.

Offline independent recount (after explicit local tokenizer setup):

```sh
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false \
PYTHONPATH=research/goal-engine-2026-10-04/tool-relation-states-v2/supervision-v1/sources \
python -m research.audit_tool_relation_state_supervision \
  --out research/goal-engine-2026-10-04/tool-relation-states-v2/supervision-v1 \
  --recount-tokenizer
```

Evidence: `cohort-audit.json`, `design-audit.json`, each split's `audit.json`,
`supervision-v1/{protocol,coverage,audit}.json` and saved source/raw copies.
[Next training](NEXT_TRAINING.md) requires development transfer and policy quality,
then separately reserved confirmation and full semantic LCC outcomes/cost.
