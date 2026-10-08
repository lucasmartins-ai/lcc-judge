# Explicit observation retrieval (P1)

The neural `rank_context` provider remains in shadow. A separate local operation,
`rank_observations`, accepts an explicit entity, field and inclusive UTC window.
It retrieves observations within that scope regardless of whether they are
healthy, anomalous or contradictory. An anomaly in a different entity is not
relevant merely because it is an anomaly.

```python
from lcc_engine.observations import ObservationEngine, ObservationRequest

request = ObservationRequest(
    entity="billing-api", field="http_5xx_count",
    start="2027-01-01T12:00:00Z", end="2027-01-01T12:05:00Z",
)
result = ObservationEngine().rank_observations(request, [
    {"id": "b1", "text":
     "time=2027-01-01T12:02:00Z level=INFO entity=billing-api "
     "field=http_5xx_count value=0 unit=count"},
])
```

Caller-supplied slots are required. The operation does not infer a field from a
general causal question or resolve entity aliases. It supports four declared
record forms, each containing time, level, entity, field, numeric value and unit:

- JSON lines with exactly those six keys; duplicate keys are rejected.
- `time=... level=... entity=... field=... value=... unit=...`
- `TIME | LEVEL | ENTITY | FIELD=VALUE UNIT`
- `At TIME, ENTITY reported FIELD = VALUE UNIT (LEVEL).`

UTC timestamps must be valid `YYYY-MM-DDTHH:MM:SSZ` values. Levels are INFO, WARN,
ERROR, DEBUG or TRACE. Entity/field/unit syntax is checked; numeric values must be
finite and cannot be booleans. The documented synthetic query annotation is
ignored only when it exactly matches the supplied request. Other comments,
unknown schemas, missing timestamps, unresolved entities and opaque causal text
make the entire block UNKNOWN/KEEP. An unknown line overrides an obvious match.

MATCH keeps a whole block. NO_MATCH drops it only under this retrieval contract.
UNKNOWN keeps it. The output returns IDs, statuses and hashes without rewriting
the input. It is neither a probability estimate nor a necessity/sufficiency test.
Default limits are 8192 blocks and 262144 UTF-8 bytes per block; oversized blocks
are kept. There is no transformer token window for this operation.

The prepared local LCC integration accepts this typed request explicitly:

```python
from lcc.relevance.observations import compact_observations

compiled = compact_observations(text, request, engine=ObservationEngine())
print(compiled.compacted_text)
```

The consumer verifies block IDs/hashes/statuses, preserves original slices and
all inter-block gaps, and keeps the whole candidate set when the local runtime or
its receipt is invalid. Existing prefix/short-block protections remain. See
examples/lcc_observations.py. This source integration is prepared in the local
LCC checkout, not a released CLI/default or upstream package capability.

A frozen four-profile pilot executed 144 actual downstream calls: six exposed
synthetic tasks × 8K/32K cl100k dossiers × full/local/Laya/Jev × three repeats.
The local route returned 36/36 correct exact JSON answers, kept every declared
observation and ambiguity, and removed mean 92.50%/98.10% of input bytes.
This validates the fixed literal workflow only. Sources/raw outputs/cached token
accounting are checked by `python -m research.audit_observation_lcc_pilot`.
See research/goal-engine-2026-10-04/observation-lcc-pilot/audit.json.

The general neural provider remains shadow. Synthetic schema/outcome tests do not
establish preservation for arbitrary incident diagnosis or broad semantic
replacement. The next neural target is semantic relation to a natural-language
tool objective; exact identifier/field/window routing is a separate operation.
