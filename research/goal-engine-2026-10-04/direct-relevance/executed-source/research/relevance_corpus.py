"""Synthetic P1 observation retrieval, explicitly separate from P2 necessity.

Ground truth comes from typed entity/field/window records. The oracle never uses
incident status, generator kind, or a model. Held-out fields are new; schemas and
the author-designed task are shared. This is not external production evidence.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
import random
import re


# domain: (requested field, human description, other field, unit)
FIELDS = {
    'container_cpu': ('cpu_throttle_pct', 'CPU throttling percentage', 'cpu_load_pct', '%'),
    'memory_pressure': ('resident_bytes', 'resident memory usage', 'allocated_bytes', 'bytes'),
    'nginx_requests': ('http_5xx_count', 'server error count', 'http_4xx_count', 'count'),
    'worker_queue': ('queue_wait_ms', 'time waiting in the queue', 'execution_ms', 'ms'),
    'postgres_replica': ('replica_lag_ms', 'replication delay', 'query_time_ms', 'ms'),
    'disk_health': ('disk_retry_count', 'disk retry count', 'disk_read_count', 'count'),
    'dns_resolution': ('dns_timeout_count', 'DNS timeout count', 'dns_lookup_count', 'count'),
    'cert_rotation': ('cert_remaining_hours', 'certificate validity remaining', 'rotation_age_hours', 'hours'),
    'rpc_latency': ('rpc_p99_ms', '99th percentile RPC duration', 'rpc_p50_ms', 'ms'),
    'object_storage': ('object_checksum_failures', 'checksum mismatch count', 'object_write_count', 'count'),
    'build_cache': ('cache_miss_count', 'cache miss count', 'cache_hit_count', 'count'),
    'task_scheduler': ('scheduled_delay_ms', 'scheduler delay', 'task_duration_ms', 'ms'),
    # Frozen final domains: never used in loss or validation selection.
    'robot_battery': ('battery_voltage_mv', 'battery voltage', 'motor_voltage_mv', 'mV'),
    'broker_consumer': ('consumer_backlog_count', 'unconsumed message backlog', 'published_count', 'count'),
    'browser_webrtc': ('rtp_packet_loss_pct', 'RTP packet loss percentage', 'rtp_jitter_ms', '%'),
    'data_contract': ('schema_rejection_count', 'schema rejection count', 'parse_error_count', 'count'),
    'edge_power': ('supply_current_ma', 'power supply current', 'standby_current_ma', 'mA'),
    'search_segment': ('segment_merge_ms', 'index segment merge duration', 'index_read_ms', 'ms'),
}
TRAIN_DOMAINS = tuple(list(FIELDS)[:12])
FINAL_DOMAINS = tuple(list(FIELDS)[12:])
FORMATS = ('jsonl', 'key_value', 'pipe', 'sentence')
KINDS = ('healthy_relevant', 'anomalous_relevant', 'wrong_entity', 'wrong_field',
         'wrong_window', 'ambiguous_entity', 'missing_window')
SPLIT_SEEDS = {'train': 442401, 'validation': 442402, 'final': 442403}
REFERENCE_RANGES = {
    'container_cpu': (0, 50), 'memory_pressure': (0, 536870912),
    'nginx_requests': (0, 3), 'worker_queue': (0, 100),
    'postgres_replica': (0, 250), 'disk_health': (0, 2),
    'dns_resolution': (0, 2), 'cert_rotation': (72, 720),
    'rpc_latency': (0, 150), 'object_storage': (0, 0),
    'build_cache': (0, 10), 'task_scheduler': (0, 100),
    'robot_battery': (3500, 4200), 'broker_consumer': (0, 20),
    'browser_webrtc': (0, 2), 'data_contract': (0, 0),
    'edge_power': (50, 500), 'search_segment': (0, 500),
}


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def model_input(row: dict) -> tuple[str, str]:
    return row['objective'], row['text']


def typed_control(objective: str, text: str) -> int | None:
    """Parse only the declared observation grammar; fail closed outside it.

    This control receives the same strings as neural models. It does not read
    annotations, row IDs, domain names, statuses or the generator oracle.
    """
    entity_match = re.search(r'\bnode-[0-9a-f]{8}\b', objective)
    field_match = (re.search(r'\(field ([a-z][a-z0-9_]*)\)', objective) or
                   re.search(r'Which blocks report ([a-z][a-z0-9_]*),', objective) or
                   re.search(r'\(([a-z][a-z0-9_]*)\) during', objective))
    times = re.findall(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z', objective)
    if not entity_match or not field_match or len(times) != 2 or times[0] > times[1]:
        return None
    observations = []
    for line in text.splitlines():
        if not line.strip() or line.startswith('# Requested observation:'):
            continue
        try:
            if line.startswith('{'):
                record = json.loads(line)
                entity, field, timestamp = record['entity'], record['field'], record['time']
            else:
                patterns = (
                    r'^time=(\S+) level=\S+ entity=(\S+) field=(\S+) value=\S+ unit=\S+$',
                    r'^(\S+) \| \S+ \| (\S+) \| ([a-z][a-z0-9_]*)=\S+ \S+$',
                    r'^At (\S+), (\S+) reported ([a-z][a-z0-9_]*) = \S+ \S+ \(\S+\)\.$',
                )
                match = next((m for p in patterns if (m := re.fullmatch(p, line))), None)
                if match is None:
                    return None
                timestamp, entity, field = match.groups()
        except (ValueError, KeyError, TypeError):
            return None
        obs = dict(entity=entity, field=field, time=timestamp)
        if entity.startswith('unresolved(') and entity.endswith(')'):
            obs['entity_candidates'] = entity[11:-1].split(',')
            obs['entity'] = None
        if timestamp == 'unknown':
            obs['time'] = None
        elif not re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z', timestamp):
            return None
        observations.append(obs)
    if not observations:
        return None
    return verify_label(dict(schema_supported=True,
                             request=dict(entity=entity_match.group(), field=field_match.group(1),
                                          start=times[0], end=times[1]), observations=observations))


def verify_label(row: dict) -> int | None:
    """Direct P1 observation relevance, not whether the observation is necessary."""
    if not row['schema_supported']:
        return None
    request = row['request']
    uncertain = False
    for obs in row['observations']:
        candidates = obs.get('entity_candidates')
        if candidates and request['entity'] in candidates and obs['field'] == request['field']:
            uncertain = True
            continue
        if obs.get('entity') != request['entity'] or obs['field'] != request['field']:
            continue
        if obs.get('time') is None:
            uncertain = True
            continue
        if request['start'] <= obs['time'] <= request['end']:
            return 1
    return None if uncertain else 0


def render(obs: dict, style: str, level: str) -> str:
    entity = obs.get('entity') or 'unresolved(' + ','.join(obs['entity_candidates']) + ')'
    timestamp = obs.get('time') or 'unknown'
    if style == 'jsonl':
        return json.dumps(dict(time=timestamp, level=level, entity=entity,
                               field=obs['field'], value=obs['value'], unit=obs['unit']), sort_keys=True)
    if style == 'key_value':
        return (f"time={timestamp} level={level} entity={entity} "
                f"field={obs['field']} value={obs['value']} unit={obs['unit']}")
    if style == 'pipe':
        return f"{timestamp} | {level} | {entity} | {obs['field']}={obs['value']} {obs['unit']}"
    return f"At {timestamp}, {entity} reported {obs['field']} = {obs['value']} {obs['unit']} ({level})."


def make_group(domain: str, seed: int, index: int) -> list[dict]:
    rng = random.Random(f'{seed}:{domain}:{index}')
    field, description, other_field, unit = FIELDS[domain]
    entity = f"node-{rng.getrandbits(32):08x}"
    other = entity[:-1] + ('0' if entity[-1] != '0' else '1')
    start = datetime(2027, 1, 1, tzinfo=timezone.utc) + timedelta(days=rng.randrange(365), hours=rng.randrange(24))
    iso = lambda value: value.strftime('%Y-%m-%dT%H:%M:%SZ')
    request = dict(entity=entity, field=field, start=iso(start), end=iso(start + timedelta(minutes=5)))
    objectives = (
        f"Find observations of {description} (field {field}) for {entity} between {request['start']} and {request['end']}. Include healthy or anomalous values.",
        f"Which blocks report {field}, meaning {description}, for entity {entity} in [{request['start']}, {request['end']}]? Healthy measurements also count.",
        f"Keep evidence about {entity}'s {description} ({field}) during {request['start']} through {request['end']}, regardless of whether its value looks normal.",
    )
    objective = objectives[index % len(objectives)]
    style = FORMATS[index % len(FORMATS)]
    level = rng.choice(('INFO', 'WARN', 'ERROR'))  # Independent of target/label.
    # Identical query-vocabulary comment for every label: lexical overlap is no oracle.
    comment = f"# Requested observation: entity {entity}; field {field}; window {request['start']} to {request['end']}"
    filler = []
    for _ in range((0, 2, 6, 12)[index % 4]):
        filler.append(dict(entity=other, field=rng.choice((field, other_field)),
                           time=iso(start + timedelta(minutes=2)), value=rng.randrange(10, 99), unit=unit))
    noise = [render(obs, style, level) for obs in filler]
    rows = []
    for kind in KINDS:
        # Positives include both states; negatives are balanced over groups.
        # These are fixture-specific reference ranges, not production SLO claims.
        healthy = kind == 'healthy_relevant' or (kind != 'anomalous_relevant' and index % 2 == 0)
        low, high = REFERENCE_RANGES[domain]
        value = rng.randrange(low, high + 1) if healthy else high + rng.randrange(10, 99)
        obs = dict(entity=entity, field=field, time=iso(start + timedelta(minutes=2)),
                   value=value, unit=unit)
        if kind == 'wrong_entity':
            obs['entity'] = other
        elif kind == 'wrong_field':
            obs['field'] = other_field
        elif kind == 'wrong_window':
            obs['time'] = iso(start - timedelta(minutes=2))
        elif kind == 'ambiguous_entity':
            obs['entity'] = None
            obs['entity_candidates'] = [entity, other]
        elif kind == 'missing_window':
            obs['time'] = None
        lines = noise.copy()
        # Same position across all candidates in an objective; no label-specific padding.
        position = index % (len(lines) + 1)
        decisive = render(obs, style, level)
        lines.insert(position, decisive)
        lines.insert(0, comment)
        text = '\n'.join(lines)
        row = dict(id=digest([seed, domain, index, kind])[:24], group=digest([seed, domain, index])[:24],
                   domain=domain, kind=kind, format=style, objective=objective, text=text,
                   request=request.copy(), observations=[obs] + filler, schema_supported=True,
                   observation_status='healthy' if healthy else 'anomalous',
                   fixture_reference_range=[low, high],
                   evidence_span=[text.index(decisive), text.index(decisive) + len(decisive)],
                   source='synthetic-p1-observation/0.1', seed=seed)
        row['label'] = verify_label(row)
        row['content_hash'] = digest(model_input(row))
        rows.append(row)
    return rows


def build_split(split: str, groups_per_domain: int) -> list[dict]:
    if split not in SPLIT_SEEDS or groups_per_domain < 1:
        raise ValueError('Unknown split or invalid group count')
    domains = FINAL_DOMAINS if split == 'final' else TRAIN_DOMAINS
    return [row for domain in domains for index in range(groups_per_domain)
            for row in make_group(domain, SPLIT_SEEDS[split], index)]
