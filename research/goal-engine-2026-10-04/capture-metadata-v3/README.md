# Capture metadata v3 (producer-side)

Closes the typed-API gap from [../TYPED_API_METADATA_GAP.md](../TYPED_API_METADATA_GAP.md)
using option 1, producer-side metadata. This change adds code and tests only. No
capture ran, no protocol was frozen, and no existing receipt or hash-pinned
source changed.

## Code

- `research/tool_relation_state_capture_v3.py` (schema `trusted-tool-relation-states-metadata/0.3`)
  wraps the unchanged v2 observers (`observe_retry`, `observe_udp`, `observe_git`
  in `research/tool_relation_state_worker.py`).
- `tests/test_tool_relation_state_capture_v3.py`. TDD logs:
  `capture-v3-red.log` (module missing) and `capture-v3-green.log` (8 OK).

## Record contract (one per measured field, 18 per fixture)

| Slot | Source |
| --- | --- |
| `time` | `datetime.now(timezone.utc)`, read right after that source's observer returns, formatted `YYYY-MM-DDTHH:MM:SSZ`. The code has no path that turns `perf_counter_ns` or another monotonic value into UTC. |
| `clock` | `system_wall_utc`, recording where `time` came from. |
| `field`, `unit` | `FIELD_UNITS`, the collector's own schema. Its keys match what `retry_fields`/`udp_fields`/`git_fields` return, and units are `count`, `ns` or `bytes`. If an observer's keys drift from it, the capture fails. Nothing is read from the caption registry (`tool_relation_contracts*`) or from `binding`. |
| `entity` | `tool-` + sha256(`relation-states-v3:{seed}:{index}`)[:12], the producer's own instance ID. |
| `level` | `INFO`, declared by the producer. Only fully measured observations are emitted, and a capture error fails the whole request. |
| `value` | the observed integer |

`to_observation_blocks(records)` deterministically turns records into
`rank_observations` blocks (`{id, text, status, missing}`). `text` is a
six-key JSON line. A record becomes `UNKNOWN` and keeps only its present slots
in these cases: a slot is missing, `clock` is not `system_wall_utc`, or `time`
is not a `Z`-suffixed UTC string. The engine then returns it as UNKNOWN/KEEP,
never DROP.

## What the future frozen cohort must do

1. Build a separate worker image whose pinned `SOURCES` include
   `research/tool_relation_state_capture_v3.py`, and run `main()` inside it
   (`require_worker` still applies).
2. Freeze a new protocol in a new directory, with a new seed range kept apart
   from v2 train/validation/calibration. Pin the v3 module hash.
3. Run the capture once, with no selective retry, and keep partial evidence as UNKNOWN.
   On a capture error `main()` prints a partial receipt (`partial_fixture`,
   `failed_source`, `error_type`, `all_reference_checks_passed=false`) before
   re-raising. Both receipts record `versions` (git, tenacity), `python` and each
   fixture's `fixture_content_sha256`. Store the partial receipt as is.
4. Build requests with a UTC window derived from the observed record `time`
   range (with a declared margin), never from a synthetic range.
5. Check that the converter returns 0 `UNKNOWN` blocks on a complete capture
   and that `rank_observations` returns MATCH or NO_MATCH as expected.

## Known limits

- Times have one-second resolution, which is the format `ObservationRequest`
  accepts. All fields from one source share one timestamp.
- Wall-clock accuracy depends on the host and container clock (NTP). A cohort
  receipt should record that clock source.
- `level` is constant. If WARN for retry exhaustion is wanted, that is a
  contract change to decide before the freeze.
