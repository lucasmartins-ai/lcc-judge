# Eight-field retrieval contract — frozen before the probe

The exact public candidate strings are in registry.json. Each supported request
must designate one recorded field for an explicit caller/capture instance.
Ambiguous, negated/underspecified, out-of-registry, derived, diagnostic and broad
context requests abstain. The probe can fail to recognize those categories; the
contract is a target, not a quality claim.

| Field | Unit | Source meaning |
| --- | --- | --- |
| retry_attempts | calls | All operation calls, initial and terminating calls included |
| retry_failures | calls | Only calls that raised an exception |
| retry_scheduled_sleep_ns | nanoseconds | Sum of requested pause intervals |
| retry_actual_sleep_ns | nanoseconds | Sum of monotonic sleeper entry-to-exit intervals; exclude operation calls |
| udp_sent_datagrams | datagrams | Successful local send events including empty messages |
| udp_sent_payload_bytes | bytes | Sum of application payload lengths; exclude headers and delivery assumptions |
| git_index_edits | paths | Distinct HEAD-to-index changes, staged additions/modifications/deletions |
| git_worktree_edits | paths | Distinct tracked index-to-disk changes, including local deletions |

Git scope excludes untracked/ignored entries. Worker raw-state definitions and
independent raw recount are pinned before inference. No UTC is inferred from
monotonic clocks. Future field adapters must preserve provenance and original
slices. Original prose is not silently assigned a field using the benchmark
annotation; this goal-only probe never consumes records.

Query support and record validity have different labels. A supported question
remains supported when its record is malformed; that record remains UNKNOWN/KEEP.
False or contradictory values do not make a matching record irrelevant.

Fixed recipe: score a query against all 12 bilingual definitions (8 fields and
4 unsupported kinds), accept only a unique maximum selecting a field. Ties and
unsupported winners abstain. No fitted cutoff, probability claim, training or
post-result definition choice. Neural and lexical use the same strings.

Success requires accepted-binding precision >=.99, supported coverage >=.80 and
semantic UNKNOWN recognition >=.95 in aggregate and both languages. Correct
supported coverage, per-field/per-kind confusion and unique-question counts are
also reported. A failing probe stops before fresh confirmation and LCC outcomes.
Independent human semantic review remains pending. An eight-field pass cannot
certify the historical eighteen-field or broader engine + LCC quality gates.
