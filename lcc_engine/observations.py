"""Explicit observation retrieval for a narrow, independently typed P1 operation.

No inference about incident causality, aliases or counterfactual necessity. Every
unsupported block remains UNKNOWN/KEEP. This operation is separate from the
neural rank_context shadow provider; it does not change LCC defaults.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
import math
import re
import time


_ENTITY = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.:/-]{0,127}')
_FIELD = re.compile(r'[A-Za-z][A-Za-z0-9_]{0,127}')
_TIME = re.compile(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z')
_UNIT = re.compile(r'[A-Za-z%][A-Za-z0-9%_/-]{0,31}')
_NUMBER = r'-?\d+(?:\.\d+)?'


def _timestamp(value: str) -> datetime:
    if not isinstance(value, str) or not _TIME.fullmatch(value):
        raise ValueError('Timestamp must use YYYY-MM-DDTHH:MM:SSZ')
    return datetime.strptime(value, '%Y-%m-%dT%H:%M:%SZ')


@dataclass(frozen=True)
class ObservationRequest:
    entity: str
    field: str
    start: str
    end: str

    def __post_init__(self):
        if (not isinstance(self.entity, str) or not _ENTITY.fullmatch(self.entity) or
                not isinstance(self.field, str) or not _FIELD.fullmatch(self.field)):
            raise ValueError('Explicit entity and field slots are required')
        if _timestamp(self.start) > _timestamp(self.end):
            raise ValueError('Window start must be at or before its end')


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON key')
        result[key] = value
    return result


def _record(line: str) -> dict:
    if line.startswith('{'):
        value = json.loads(line, object_pairs_hook=_unique_object)
        if not isinstance(value, dict) or set(value) != {'time', 'level', 'entity', 'field', 'value', 'unit'}:
            raise ValueError('Unsupported JSON schema')
    else:
        patterns = (
            rf'^time=(\S+) level=(\S+) entity=(\S+) field=(\S+) value=({_NUMBER}) unit=(\S+)$',
            rf'^(\S+) \| (\S+) \| (\S+) \| ([A-Za-z][A-Za-z0-9_]*)=({_NUMBER}) (\S+)$',
            rf'^At (\S+), (\S+) reported ([A-Za-z][A-Za-z0-9_]*) = ({_NUMBER}) (\S+) \((\S+)\)\.$',
        )
        matches = [(i, match) for i, pattern in enumerate(patterns) if (match := re.fullmatch(pattern, line))]
        if not matches:
            raise ValueError('Unsupported record grammar')
        index, match = matches[0]
        if index == 2:
            timestamp, entity, field, number, unit, level = match.groups()
        else:
            timestamp, level, entity, field, number, unit = match.groups()
        value = dict(time=timestamp, level=level, entity=entity, field=field, value=float(number), unit=unit)
    if (not isinstance(value['entity'], str) or not _ENTITY.fullmatch(value['entity']) or
            not isinstance(value['field'], str) or not _FIELD.fullmatch(value['field']) or
            not isinstance(value['unit'], str) or not _UNIT.fullmatch(value['unit']) or
            value['level'] not in {'INFO', 'WARN', 'ERROR', 'DEBUG', 'TRACE'} or
            type(value['value']) not in (int, float) or not math.isfinite(value['value'])):
        raise ValueError('Unsupported record value or ambiguous identity')
    _timestamp(value['time'])
    return value


class ObservationEngine:
    """Local exact-match engine for caller-supplied entity/field/window requests.

    DROP is valid only within this explicit retrieval contract and supported
    grammar. General causal questions cannot be submitted through this API.
    """

    is_local = True
    name = 'observation-parser'

    def __init__(self, *, max_block_bytes=262144, max_blocks=8192):
        if type(max_block_bytes) is not int or max_block_bytes < 1 or type(max_blocks) is not int or max_blocks < 1:
            raise ValueError('Positive integer resource limits are required')
        self.max_block_bytes, self.max_blocks = max_block_bytes, max_blocks

    def supports_operation(self, operation):
        return operation == 'rank_observations'

    def rank_observations(self, request: ObservationRequest, blocks: list[dict]) -> dict:
        if not isinstance(request, ObservationRequest):
            raise ValueError('ObservationRequest with explicit slots is required')
        if not isinstance(blocks, list) or len(blocks) > self.max_blocks:
            raise ValueError('Blocks must be a bounded list')
        ids = []
        for block in blocks:
            if (not isinstance(block, dict) or not isinstance(block.get('id'), str) or
                    not block['id'] or not isinstance(block.get('text'), str)):
                raise ValueError('Each block requires a string id and text')
            ids.append(block['id'])
        if len(ids) != len(set(ids)):
            raise ValueError('Block IDs must be unique')
        started = time.perf_counter()
        items = []
        comment = (f'# Requested observation: entity {request.entity}; field {request.field}; '
                   f'window {request.start} to {request.end}')
        for block in blocks:
            text = block['text']
            encoded = text.encode()
            status, count, reason = 'UNKNOWN', 0, 'unsupported_or_ambiguous'
            if len(encoded) > self.max_block_bytes:
                reason = 'block_exceeds_byte_limit'
            else:
                try:
                    records = [_record(line.strip()) for line in text.splitlines()
                               if line.strip() and line != comment]
                    if records:
                        count = len(records)
                        matched = any(r['entity'] == request.entity and r['field'] == request.field and
                                      request.start <= r['time'] <= request.end for r in records)
                        status, reason = ('MATCH', 'explicit_observation') if matched else ('NO_MATCH', 'no_observation_in_requested_scope')
                except (ValueError, TypeError, KeyError, OverflowError):
                    pass
            items.append(dict(id=block['id'], status=status, decision='DROP' if status == 'NO_MATCH' else 'KEEP',
                              reason=reason, records=count, bytes=len(encoded),
                              text_sha256=hashlib.sha256(encoded).hexdigest()))
        return dict(schema='lcc-observation-ranking/0.1', operation='rank_observations',
                    mode='experimental_selection', is_local=True, items=items,
                    kept_ids=[r['id'] for r in items if r['decision'] == 'KEEP'],
                    dropped_ids=[r['id'] for r in items if r['decision'] == 'DROP'],
                    input_bytes=sum(r['bytes'] for r in items),
                    kept_bytes=sum(r['bytes'] for r in items if r['decision'] == 'KEEP'),
                    unknowns=sum(r['status'] == 'UNKNOWN' for r in items),
                    necessity_estimated=False, set_sufficiency_estimated=False,
                    calibrated_probability=False, latency_ms=(time.perf_counter()-started)*1000)
