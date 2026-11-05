# Encoder cost spike (2026-11-05)

Measurement only: no training, no quality claim. The question is whether a two-layer LCC model
(block encoder plus a session layer over the block vectors) is cheap enough on CPU to be worth a
pre-registered study. Context numbers and the design come from the 2026-11-05 handoff (blocks
<= 2K tokens; the information a prompt needs sits p50 36K tokens back).

## Criteria (agreed with the owner in chat before any measurement)

Judged on the **int8** model, CPU only (no MPS), 4 threads, with the load average recorded next
to every number. The machine is a shared M1 Max (64 GB), so every latency is an upper bound.

| criterion | GO if |
|---|---|
| warm pass, p90 | encode the blocks added since the previous user prompt plus the new prompt, then run the session layer over 1,573 vectors (p90 blocks per item): **<= 2 s** |
| cold encode, median session | every block of the item nearest the p50 block count (435): **<= 30 s** |
| peak RSS | whole process, model loaded and all measurements run: **<= 500 MB** |

All three pass: GO. Any one fails: NO-GO for that configuration. Reference: specialist v3 takes
0.8 s for 1,000 blocks at 90 MB peak RSS (`research/bench-results/latest.md`, one thread).

### Amendment 1 (after the tokenizer stats, before any model run)

The item nearest the p50 block count (435 blocks) holds 209,060 Granite tokens, 3.5x the 59K
the agreed criterion named for a median session. Block count and token count rank items
differently, and encode time follows tokens. The cold items are therefore picked by Granite
tokens per item (p50 and p90). The block-count item is kept in `out/stats.json` as
`cold_p50_by_blocks` and not timed. Thresholds are unchanged.

## Setup

- Encoder: `ibm-granite/granite-embedding-97m-multilingual-r2`, revision `835ad14`, Apache-2.0,
  ModernBERT, 12 layers, hidden 384, 180K vocab, CLS pooling. Weights and tokenizer only.
- Session layer: a stub, 2-layer `nn.TransformerEncoder` (d 384, 6 heads, FF 1536), random
  weights, fp32, over N block vectors plus one goal vector.
- Data: the 2,873 block-judge items in `~/.lcc/bench/next-action-v2/items` with their texts from
  `~/.lcc/bench/next-action-v1/texts`. Lengths are counted with the Granite tokenizer; blocks are
  truncated at 2,048 tokens, sorted by length and batched at 8,192 padded tokens.
- int8: PyTorch dynamic quantization of `nn.Linear` (qnnpack). Embeddings stay fp32. PyTorch marks
  this API deprecated; a product build would use another runtime, so int8 here is a proxy.
- `int8-pruned`: the embedding table cut to the token ids seen in these items; an unseen id maps
  to `[MASK]`. The out-of-vocabulary rate is measured on 20% of sessions held out of the fit.
- Items: cold = the items nearest p50 and p90 of Granite tokens per item (amendment 1); warm =
  the items nearest p50 and p90 of Granite tokens added since the previous user prompt (the rule
  in the script before the stats run). The warm total adds the session layer at 1,573 vectors as
  the criterion says, whatever the warm item's own block count (the p90 warm item has 365).
- RSS: the criterion uses `ru_maxrss`, the whole-process peak. Per-phase peaks come from `ps`
  sampled about every 0.2 s; they are lower bounds and miss short phases.
- Script: `spike.py` (modes `stats`, `fp32`, `int8`, `int8-pruned`); raw output in `out/`.

### Deviation: run 1 discarded

The first model run had a batching bug: batch size came from the shortest block in the batch,
so a 2-token block opened a batch of up to 4,096 blocks padded to the longest of them (peak RSS
37 GB, cold p50 in 14-21 minutes, from the run log; that output was overwritten). Everything
below is run 2. `batches()` now has a self-check that fails on the old rule. Run 2 also samples
RSS per phase and runs the session layer after the encodes, so the p99 stub's memory shows alone.

## Results (run 2, 2026-11-05)

**Verdict: NO-GO, on peak RSS.** The whole process peaked at 4.0-4.2 GB against 500 MB in every
configuration, and the first phase (imports, load, quantize) already reached 1.0-1.5 GB.

The two time criteria also missed as measured, but the 1-minute load average was 24.7-109.6 on
10 cores during the runs. That much contention can slow a 4-thread job several times over, so
these runs do not establish whether warm p90 and cold median would pass on an idle machine.

| criterion (GO if) | int8 | int8-pruned | fp32 |
|---|---:|---:|---:|
| peak RSS <= 500 MB (whole process) | **4,240 MB** | **4,016 MB** | **4,122 MB** |
| warm p90 <= 2 s (measured under load) | 76.8 s | 46.8 s | 16.9 s |
| cold median <= 30 s (measured under load) | 44.2 s | 67.6 s | 64.2 s |
| load average at start | 24.7 | 66.3 | 109.6 |

### Workload (tokenizer only, `out/stats.json`)

- 2,873 items, 649 sessions, 431,923 unique blocks, every block text present.
- Granite tokens per block: p50 53, p90 466, p99 2,511, max 4,427. 5,849 blocks (1.35%)
  exceed 2,048 and are truncated. The Granite tokenizer counts about 1.3x the items' `tokens`
  field per block (p50 ratio), so the handoff's "0 blocks over 2,048" does not hold here.
- Granite tokens per item (context at the prompt): p50 88,568, p90 336,708, p99 3,698,021.
- Added since the previous user prompt (the warm workload): p50 31 blocks / 5,631 tokens,
  p90 296 blocks / 65,429 tokens, p99 1,149 blocks / 144,084 tokens.
- Vocabulary: 86,094 of 180K ids appear. Fit on 80% of sessions (82,415 ids), the other 20%
  (123 sessions) see 0.11% of their tokens out of vocabulary.

### Timings and memory (`out/<mode>-t4.json`)

Every time below ran under the load shown in the last row. The session-layer stub is the same
fp32 code in all three modes, yet its times differ up to 2.6x between modes (9,882 vectors:
2,035-5,357 ms), so treat load noise on any time here as at least that large.

| | int8 | int8-pruned | fp32 |
|---|---:|---:|---:|
| model file (state dict) | 291 MB | 154 MB | 372 MB |
| one block, 54 / 443 tokens | 31 / 184 ms | 231 / 870 ms | 17 / 68 ms |
| one block, 1,243 / 2,048 tokens | 446 / 841 ms | 1,464 / 4,924 ms | 246 / 535 ms |
| cold p50 item (862 blocks, 90,292 tokens) | 44.2 s | 67.6 s | 64.2 s |
| cold p90 item (2,475 blocks, 341,534 tokens) | 209.8 s | 292.5 s | 136.9 s |
| warm p50 (41 blocks, 5,732 tokens), encode only | 13.2 s | 5.8 s | 3.8 s |
| warm p90 (362 blocks, 66,185 tokens), encode only | 76.7 s | 46.7 s | 16.9 s |
| session layer, 435 / 1,573 / 9,882 vectors | 12 / 124 / 2,205 ms | 22 / 60 / 2,035 ms | 11 / 62 / 5,357 ms |
| RSS peak, imports + load + quantize (sampled) | 1,415 MB | 1,534 MB | 1,014 MB |
| RSS peak, cold p50 encode (sampled) | 4,187 MB | 3,908 MB | 3,871 MB |
| RSS peak, cold p90 encode (sampled) | 2,342 MB | 2,263 MB | 2,330 MB |
| RSS peak, warm p90 encode (sampled) | 1,967 MB | 1,884 MB | 1,847 MB |
| RSS peak, session layer at 9,882 (sampled) | 4,039 MB | 4,016 MB | 4,122 MB |
| load average at start | 24.7 | 66.3 | 109.6 |

The int8-pruned per-block latencies are 3-8x int8's. That run started at load 66 against 25,
but load alone does not obviously explain it, and pruned was faster than int8 on warm p90. The
cause is unknown.

### What the numbers point to

- **Memory fails before any work.** The first phase, which covers importing torch and
  transformers, loading the checkpoint and quantizing, already peaks at 1.0-1.5 GB. How much of
  that a pre-built model file or a lighter runtime would save is not measured.
- **The 4 GB peaks are not explained.** The cold p50 encode peaked near 4 GB, while the cold p90
  encode, with more long blocks, peaked at 2.3 GB; the sparse sampler cannot say which batch
  caused it. At 9,882 vectors the stub session layer also reached 4 GB, likely because
  PyTorch's attention there holds the full N x N matrix (not measured).
- **Tokens per turn set the time budget.** A p90 turn adds 65K tokens; 2 s would need about
  33K tokens/s. The best rate measured here is about 3.9K tokens/s (fp32, warm p90, load 65-76),
  8.4x short. How much of that gap is load is not measured.
- **int8 against fp32 is not settled.** int8 single-block latencies were higher than fp32 at
  every length, but int8 ran at load 25 and fp32 at 110, and cold p50 went the other way (44.2
  against 64.2 s).
- **The session layer is small next to the encoder:** at most 124 ms at the p50 and p90 block
  counts, against seconds of encoding, in every mode.

### What this does and does not say

- It rules out this encoder, run in PyTorch at a 2K window, on memory against the agreed
  500 MB. It says nothing about quality.
- Not measured: an idle machine (needed before any time claim); encoding each block as it
  arrives, so a compaction pays only the session layer; a smaller encoder (fewer layers, or a
  512-token window, which holds 90% of blocks whole); an ONNX or other int8 runtime; a
  pre-built model file.
- Per prompt, an intake-sized input (443 tokens) took 68-870 ms across the modes under load,
  in a process of 1.0-1.5 GB or more, against intake v1's 1.2 MB model and 0.26 ms.
- The specialist v3 reference (0.8 s for 1,000 blocks, 90 MB) was itself measured at load 239.

## Spike 2: ONNX Runtime on an idle machine (criteria written before the run, 2026-11-05)

The owner chose this follow-up after spike 1. It asks whether the 4 GB comes from PyTorch or
from the model, and settles the time criteria on an idle machine.

- **Criteria:** the three above, unchanged (warm p90 <= 2 s with the session layer at 1,573
  vectors; cold median <= 30 s; whole-process peak RSS <= 500 MB), same items
  (`out/stats.json`), 4 threads, CPU only (`CPUExecutionProvider`).
- **Configurations:**
  - `ort-fp32`: IBM's own `onnx/model.onnx` (revision `835ad14`) as published.
  - `ort-int8`: ONNX Runtime dynamic int8 of the MatMul weights and the embedding table.
  - `ort-int8-pruned`: the embedding table cut to the 86,097 ids from spike 1, then the same
    int8. Unseen ids map to `[MASK]`.
- **Process:** a separate venv with only onnxruntime 1.31.1, onnx 1.23.2, tokenizers 0.23.3
  and numpy 2.5.4. The measured process imports neither torch nor transformers.
- **Session layer:** a numpy stub of the same shape (2 post-norm layers, d 384, 6 heads, FF
  1536, random fp32 weights). Attention runs in chunks of 1,024 query rows, so it never holds
  the full N x N matrix.
- **Idle rule:** each mode starts only when a 10 s `top` sample shows the CPU at least 70%
  idle, checked every 15 minutes, giving up after 12 hours. CPU idle and load average are
  recorded before and after each mode. A mode whose after-sample is below 50% idle is flagged
  as not idle.
- **Decision:** a configuration is GO if it passes all three. Spike 2 is GO if at least one
  ONNX configuration is GO.
- **PyTorch rerun:** PyTorch fp32 and int8 are re-run under the same idle rule only to settle
  spike 1's time criteria. Spike 1's verdict (NO-GO on RSS) does not change.
- **Not measured:** quality, including the effect of int8 and of the `[MASK]` mapping.

### Spike 2 amendment 1 (after one smoke run under load, before the idle run)

A smoke run of `ort-int8-pruned` and PyTorch `fp32` at load 54-72 checked the code end to end
(`out/*-smoke.json`, not used for any criterion). It showed the ONNX process at 440 MB after
load, then growing to 3.9 GB during the cold p50 encode: ONNX Runtime's memory arena keeps
what the longest batches allocate.

Added, as **exploratory**: `ort-int8-pruned-lowmem`, the same file with the arena off, batches
of at most 2,048 padded tokens, and the numpy session stub chunked by 256 rows and computed in
place (same math). It is designed after seeing data, so it cannot make spike 2 GO by itself. If
only this variant passes, the result reads "NO-GO as registered, exploratory variant passes",
and a confirmation run needs its own criteria.

Sanity checks, not quality measures: ONNX fp32 and PyTorch fp32 give the same CLS vector
(cosine 1.0000 on three test strings); int8 against fp32 gives 0.965-0.983; pruned int8 against
int8 gives 0.984-0.988 (the embedding scale changes with the table).

### Spike 2 amendment 2 (after a code review, before the idle run)

No mode had started when these changes were made; the driver was stopped and restarted.

- **Bug fixed in the numpy session stub.** `sc / np.sqrt(dh)` promoted the scores to float64
  under NumPy 2, so the regular branch used twice the memory of a float32 layer. The smoke run
  had it (5.3 GB at 9,882 vectors). Both branches now stay float32 and agree up to float rounding (max difference 0.0 on a 1,574-vector test).
  Amendment 1's "same math" holds only from this fix on.
- **Idle flag replaced.** The 10 s sample after a mode ends could not see contention during the
  run. The driver now samples CPU idle back to back while each mode runs and logs the mean and
  minimum. The job itself takes about 40% of 10 cores, so a mode whose mean CPU idle during the
  run is below 40% is flagged as not idle. This supersedes the "after-sample below 50%" rule.
- **Deadline.** No mode starts 12 hours or more after launch. Each mode skipped by the deadline
  gets its own `gave_up` row, and the driver's exit code counts failed or skipped modes.
- **PyTorch path, refactored into a shared `measure()`:** latency token ids now come from
  Python's `random` (same range, different draws), the stub's input from a fresh generator,
  and the stub is built before the latency phase. Expected effect: noise only.
- The numpy stub has no biases (PyTorch's has); both use ReLU and post-norm.
