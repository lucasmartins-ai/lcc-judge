"""Explicit experimental consumer integration; requires the prepared LCC checkout."""
from lcc_engine.observations import ObservationEngine, ObservationRequest
from lcc.relevance.observations import compact_observations

scope = ObservationRequest('billing-api', 'http_5xx_count',
                           '2027-01-01T12:00:00Z', '2027-01-01T12:05:00Z')
text = ('time=2027-01-01T12:02:00Z level=INFO entity=billing-api '
        'field=http_5xx_count value=0 unit=count\n\n'
        'time=2027-01-01T12:02:00Z level=ERROR entity=other-api '
        'field=http_5xx_count value=40 unit=count\n\n'
        'Unresolved identity: this note may refer to billing-api or another service.')
result = compact_observations(text, scope, engine=ObservationEngine(), min_block_chars=0)
assert 'value=0' in result.compacted_text
assert 'value=40' not in result.compacted_text
assert 'Unresolved identity:' in result.compacted_text
print(result.compacted_text)
