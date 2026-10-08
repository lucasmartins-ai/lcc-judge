"""Probe suite for effective-context measurement (Sprint 2 encoder bake-off).

Design (see docs/05-benchmark-strategy.md §4):
- Depth probes: one critical fact placed at ~N tokens inside realistic filler.
- Two noise families (two difficulty levels):
  * ``noise_unrelated`` (P1 / detection): filler only, no incident line —
    "can the model notice the evidence-bearing block at depth?" (critical-
    recall analogue; lexical overlap with the objective is intentional).
  * ``noise_decoy`` (P2 / judgment): same shape and vocabulary, but the line
    shows a *healthy* run — "can the model tell the incident from the
    lookalike?" (value-level semantics; pure lexical matching cannot).
- Depth 0 is the control: decisive line alone, no filler.
- Deterministic: same seed -> same bytes. Depth is measured in tiktoken
  cl100k_base tokens (``depth_ref`` in the results; models tokenize
  differently, which is itself part of the measured behavior).
"""

from __future__ import annotations

import random
from dataclasses import dataclass

import tiktoken

_ENC = tiktoken.get_encoding("cl100k_base")

#: v1.1 (2026-10-02): noise_unrelated middle is ONE timestamped distractor line
#: matched in length to the decisive line (v1 ran ~55 tokens longer — a confound),
#: and log level is drawn uniformly for every kind (v1 tied ERROR to fact — a
#: label cue). See research/experiments.md EXP-2026-10-02-02 interpretation 2.
#:
#: v1.2 (2026-10-03): case set expanded 8 -> 62 (54 newly authored cases,
#: independent of the training generator — anti-contamination per Sprint-2 next
#: steps). Construction rules unchanged from v1.1; n=62 gives 3844 AUC pairs so
#: the J@16K .891-vs-.90 boundary stops sitting on 1/64 cell granularity.
PROBE_VERSION = "1.2"

#: distractor bodies for noise_unrelated: different subsystem, similar length.
UNRELATED_BODIES = (
    "service=search-idx shard=14 docs=22104 status=200 elapsed_ms=88",
    "service=cache-proxy region=eu-west hits=99211 misses=1022 status=200",
    "service=mailer-daemon queue=0 sent=4120 bounced=3 status=ok",
    "service=ingest-relay batch=77 records=9210 dropped=0 status=ok",
    "service=auth-svc logins=8821 failures=2 latency_p50=41ms status=ok",
    "service=reporting cron=nightly rows=120441 duration_s=212 status=ok",
)

SERVICES = [
    "checkout-api", "booking-svc", "payment-gateway", "auth-svc", "search-idx",
    "mailer-daemon", "queue-worker", "billing-core", "cache-proxy", "ingest-relay",
]
MESSAGES = [
    "heartbeat ok seq={seq}",
    "cache warm shard={shard} keys={keys} hit_ratio=0.{hr}",
    "replayed offset={seq} partition={shard} lag_ms={lag}",
    "gc pause young_gen elapsed_ms={lag}",
    "pool stats active={keys} idle={shard} waiting=0",
    "checkpoint written offset={seq} bytes={keys}000",
    "retry scheduled attempt={shard} backoff_ms={lag}",
    "config reload ok changed={keys} keys",
    "session sweep scanned={keys} expired={shard}",
    "metric flush points={keys} interval_s=15",
]
CODE_LINES = [
    "for shard in range(self.shards):",
    "    batch = self.queue.get_nowait()",
    "    if batch is None:",
    "        return None",
    "    self.metrics.increment('jobs.processed')",
    "    conn.execute(SQL_UPSERT, params)",
    "    await asyncio.sleep(self.backoff)",
    "result = pipeline.map(items, workers=8)",
    "except TransientError as exc:",
    "    logger.warning('transient: %s', exc)",
]


def count_tokens(text: str) -> int:
    return len(_ENC.encode(text))


def _filler_line(rng: random.Random) -> str:
    if rng.random() < 0.3:
        return rng.choice(CODE_LINES)
    tpl = rng.choice(MESSAGES)
    return tpl.format(
        seq=rng.randint(10000, 99999),
        shard=rng.randint(1, 64),
        keys=rng.randint(10, 9999),
        hr=rng.randint(10, 98),
        lag=rng.randint(3, 480),
    )


def _log_line(rng: random.Random, level: str, body: str) -> str:
    h = rng.randint(0, 23)
    m = rng.randint(0, 59)
    s = rng.randint(0, 59)
    return f"{h:02d}:{m:02d}:{s:02d} {level} {rng.choice(SERVICES)} {body}"


@dataclass(frozen=True)
class ProbeCase:
    case_id: str
    objective: str
    fact_body: str        # the decisive log body (incident line)
    decoy_body: str       # plausible healthy line, same shape
    hint: str


# 62 tasks (8 original + 54 authored for v1.2). Lexical overlap between objective
# words and fact body is kept low: the probe measures usable signal at depth, not
# keyword matching. fact/decoy always share keys and differ only in values (P2).
CASES: list[ProbeCase] = [
    ProbeCase(
        "booking_timeout",
        "What upstream service caused the 03:14 booking failure, and with which status?",
        "request_id=8f2ad3 upstream=payment-gateway status=504 elapsed_ms=30021",
        "request_id=1c9e40 upstream=payment-gateway status=200 elapsed_ms=142",
        "incident line among health lines",
    ),
    ProbeCase(
        "disk_quota",
        "Which path exhausted the build runner's disk quota?",
        "path=/var/lib/docker/overlay2 usage=97.3pct action=evict-build-cache",
        "path=/var/lib/docker/overlay2 usage=41.0pct action=none",
        "evidence is a usage spike, not a keyword",
    ),
    ProbeCase(
        "auth_regression",
        "What changed in the auth service right before the login errors spiked?",
        "flag=legacy_token_verify value=true changed_by=deploy-4821 rollout=100pct",
        "flag=legacy_token_verify value=false changed_by=deploy-4819 rollout=100pct",
        "true vs false is the whole answer",
    ),
    ProbeCase(
        "queue_backlog",
        "Which worker pool was saturated during the ingest backlog incident?",
        "pool=mailer-daemon active=64 idle=0 waiting=211 saturation=1.00",
        "pool=mailer-daemon active=12 idle=52 waiting=0 saturation=0.19",
        "numeric evidence",
    ),
    ProbeCase(
        "cache_stampede",
        "What was the cache hit ratio when the origin overload began?",
        "shard=17 keys=8821 hit_ratio=0.11 origin_rps=9421 evictions=0",
        "shard=17 keys=8821 hit_ratio=0.93 origin_rps=141 evictions=0",
        "ratio evidence, paraphrased objective",
    ),
    ProbeCase(
        "retry_storm",
        "How many retry attempts did the billing core make before giving up?",
        "service=billing-core attempts=7 backoff_ms=64000 error=deadlock final=abort",
        "service=billing-core attempts=1 backoff_ms=250 error=none final=ok",
        "count evidence",
    ),
    ProbeCase(
        "config_drift",
        "Which configuration key caused the search indexer's drift alert?",
        "key=index.merge_threads value=512 previous=16 source=hotfile-timestamp",
        "key=index.merge_threads value=16 previous=16 source=baseline",
        "value/previous pair is decisive",
    ),
    ProbeCase(
        "session_leak",
        "What was the session sweep's expired count when memory started climbing?",
        "scanned=120441 expired=38922 reaper=stalled leak_estimate_mb=1841",
        "scanned=120441 expired=104 reaper=ok leak_estimate_mb=0",
        "long-range distractor heavy",
    ),
    # --- v1.2 expansion (2026-10-03): independently authored, not generated ---
    ProbeCase(
        "payment_decline_spike",
        "What was the card decline rate during the processor outage?",
        "decline_pct=31.4 bin=4410xx code=51 currency=EUR",
        "decline_pct=1.2 bin=4410xx code=00 currency=EUR",
        "rate + response-code pair",
    ),
    ProbeCase(
        "tls_cert_expiry",
        "Which certificate was invalid during the handshake errors?",
        "cn=api.internal expires=2026-09-14 chain=intermediate err=expired",
        "cn=api.internal expires=2027-06-01 chain=intermediate err=none",
        "a date decides validity",
    ),
    ProbeCase(
        "dns_resolver_timeout",
        "How slow had the resolver become when lookups failed?",
        "resolver=ns2.edge-dns.net rtt_ms=5003 errors=8821 state=timeout",
        "resolver=ns2.edge-dns.net rtt_ms=18 errors=0 state=ok",
        "latency + error count",
    ),
    ProbeCase(
        "rate_limit_flood",
        "How many calls did the edge throttle during the burst?",
        "route=/v2/search limit=600 rejected=44120 queued=0 action=drop",
        "route=/v2/search limit=600 rejected=3 queued=0 action=allow",
        "counter decides, config identical",
    ),
    ProbeCase(
        "disk_write_latency",
        "What write latency did the data volume report during stalls?",
        "dev=nvme0n1 p99_ms=4810 iops=12 depth=93 state=saturated",
        "dev=nvme0n1 p99_ms=3 iops=4410 depth=2 state=healthy",
        "three numbers flip together",
    ),
    ProbeCase(
        "jvm_heap_pressure",
        "How full was the heap right before the service died?",
        "heap_mb=7910 max_mb=8192 gc=stalled kills=1",
        "heap_mb=2048 max_mb=8192 gc=idle kills=0",
        "ratio against a shared max",
    ),
    ProbeCase(
        "replica_lag",
        "How far behind was the follower when reads went stale?",
        "replica=read-r2 lag_s=3811 slots=8821 state=stalled",
        "replica=read-r2 lag_s=1 slots=8821 state=streaming",
        "same slot, different lag",
    ),
    ProbeCase(
        "clock_skew",
        "How much drift did the node show during the login failures?",
        "node=api-17 offset_ms=9410 ref=ntp-1 sync=lost",
        "node=api-17 offset_ms=3 ref=ntp-1 sync=ok",
        "magnitude of skew",
    ),
    ProbeCase(
        "webhook_delivery_failures",
        "What fraction of callbacks failed during the partner outage?",
        "target=partner-cb.example fail_pct=88.1 tries=5 code=503",
        "target=partner-cb.example fail_pct=0.4 tries=1 code=200",
        "failure percentage",
    ),
    ProbeCase(
        "executor_rejections",
        "How many tasks did the server pool refuse under load?",
        "pool=http-accept capacity=256 rejected=12041 queued=8821 state=full",
        "pool=http-accept capacity=256 rejected=0 queued=4 state=idle",
        "rejection counter at fixed capacity",
    ),
    ProbeCase(
        "index_staleness",
        "How stale was the product index when search missed items?",
        "index=catalog-v9 lag_min=441 docs=9921044 state=behind",
        "index=catalog-v9 lag_min=0 docs=9921401 state=fresh",
        "lag, not the index name",
    ),
    ProbeCase(
        "lock_wait_time",
        "How long did transactions wait on locks during the freeze?",
        "table=orders row_wait_ms=8210 waiting=441 blockers=3",
        "table=orders row_wait_ms=2 waiting=0 blockers=0",
        "wait magnitude",
    ),
    ProbeCase(
        "flag_rollout_exposure",
        "What share of users had the new flow enabled when errors began?",
        "flag=new-checkout exposure=100pct cohort=all errors=8821",
        "flag=new-checkout exposure=5pct cohort=internal errors=1",
        "exposure percentage",
    ),
    ProbeCase(
        "api_deprecation_410",
        "How many endpoints had vanished when clients started failing?",
        "version=v1 removed=14 code=410 callers=8821",
        "version=v1 removed=0 code=200 callers=8821",
        "removal count + status",
    ),
    ProbeCase(
        "connection_pool_exhaust",
        "Which datasource ran dry during the checkout timeouts?",
        "ds=orders-ro pool_size=40 in_use=40 waiting=2104 state=exhausted",
        "ds=orders-ro pool_size=40 in_use=9 waiting=0 state=healthy",
        "in_use at the ceiling",
    ),
    ProbeCase(
        "gc_pause_storm",
        "How long were the collector pauses during the hiccups?",
        "gc=oldgen pause_p99_ms=9110 cycles=4410 state=thrashing",
        "gc=oldgen pause_p99_ms=12 cycles=88 state=idle",
        "pause magnitude",
    ),
    ProbeCase(
        "consumer_lag",
        "How many messages had the settlement consumer missed?",
        "topic=settle.v2 group=billing lag=882104 parts=64 state=behind",
        "topic=settle.v2 group=billing lag=12 parts=64 state=caught-up",
        "lag counter",
    ),
    ProbeCase(
        "oauth_token_ttl",
        "What token lifetime was in effect during the 401 wave?",
        "issuer=idp.internal ttl_s=60 rejections=4410",
        "issuer=idp.internal ttl_s=3600 rejections=0",
        "lifetime value decides",
    ),
    ProbeCase(
        "ingest_throughput_drop",
        "How far below target did event ingestion fall during the jam?",
        "pipe=events rows_s=1180 target=92000 state=throttled",
        "pipe=events rows_s=91440 target=92000 state=nominal",
        "actual vs shared target",
    ),
    ProbeCase(
        "autoscale_pending",
        "How many pods were stuck pending during the capacity crunch?",
        "cluster=prod-eu pending=44 max_nodes=80 state=full",
        "cluster=prod-eu pending=0 max_nodes=80 state=ready",
        "pending count",
    ),
    ProbeCase(
        "currency_mismatch",
        "What currency did checkout charge during the localization bug?",
        "locale=pt-BR charged=USD price=19.90 expected=BRL",
        "locale=pt-BR charged=BRL price=99.90 expected=BRL",
        "charged vs expected must be compared",
    ),
    ProbeCase(
        "email_bounce_rate",
        "How high did bounces climb during the sending failure?",
        "stream=transactional bounce_pct=41.2 mx=bulk-01 send=paused",
        "stream=transactional bounce_pct=0.8 mx=bulk-01 send=active",
        "bounce percentage",
    ),
    ProbeCase(
        "duplicate_orders",
        "How many checkouts were double-processed during the incident?",
        "route=/checkout attempts=3 dupes=1920 idem=missing",
        "route=/checkout attempts=1 dupes=0 idem=present",
        "dupe counter + idempotency state",
    ),
    ProbeCase(
        "backup_failure",
        "How did the nightly snapshot end?",
        "job=pg-full dur_s=8810 bytes=0 result=failed reason=checksum",
        "job=pg-full dur_s=8810 bytes=99210442 result=ok reason=none",
        "bytes written decide the outcome",
    ),
    ProbeCase(
        "migration_lock",
        "Which schema change held the blocking lock?",
        "migration=20260930_add_idx lock=AccessExclusive waited_s=4410 blocked=882",
        "migration=20260930_add_idx lock=None waited_s=0 blocked=0",
        "lock mode + wait",
    ),
    ProbeCase(
        "csv_encoding",
        "What encoding were the exports written in during the corruption?",
        "export=orders enc=latin-1 expected=utf-8 bad_rows=88210",
        "export=orders enc=utf-8 expected=utf-8 bad_rows=0",
        "enc vs expected comparison",
    ),
    ProbeCase(
        "gpu_oom",
        "How much accelerator memory had the job allocated when it died?",
        "job=rank-0 vram_mb=81200 limit_mb=80000 oom=1 restarts=3",
        "job=rank-0 vram_mb=41200 limit_mb=80000 oom=0 restarts=0",
        "allocation against the limit",
    ),
    ProbeCase(
        "breaker_trip",
        "How many faults did it take to open the payments breaker?",
        "breaker=payments fails=47 window=30s state=open",
        "breaker=payments fails=1 window=30s state=closed",
        "failure count at fixed window",
    ),
    ProbeCase(
        "api_quota_exhaust",
        "How much of the provider allowance had been burned?",
        "vendor=geo-api used_pct=97.2 reset_h=516 reply=429",
        "vendor=geo-api used_pct=41.0 reset_h=516 reply=200",
        "quota percentage",
    ),
    ProbeCase(
        "raft_leader_flap",
        "How many times did the group change leadership in five minutes?",
        "raft=kv-store term=8821 changes=44 state=unstable",
        "raft=kv-store term=12 changes=0 state=steady",
        "change counter",
    ),
    ProbeCase(
        "report_timezone",
        "Which zone were the daily numbers bucketed in?",
        "report=daily tz=UTC-12 expected=America/Sao_Paulo shifted_rows=88210",
        "report=daily tz=America/Sao_Paulo expected=America/Sao_Paulo shifted_rows=0",
        "tz vs expected comparison",
    ),
    ProbeCase(
        "pod_restart_loop",
        "How many times did the worker container cycle in an hour?",
        "pod=jobs-worker-7 restarts=44 exit=137 cause=oomkilled",
        "pod=jobs-worker-7 restarts=0 exit=0 cause=completed",
        "restart counter",
    ),
    ProbeCase(
        "cdn_origin_offload",
        "How much traffic fell through to origin during the edge outage?",
        "pop=fra-01 offload_pct=94 origin_rps=88210 state=degraded",
        "pop=fra-01 offload_pct=2 origin_rps=141 state=healthy",
        "offload percentage",
    ),
    ProbeCase(
        "full_table_scan",
        "What did the planner do when dashboards timed out?",
        "query=orders_by_user examined=992104404 idx=none ms=30100",
        "query=orders_by_user examined=120 idx=used ms=12",
        "rows examined + index use",
    ),
    ProbeCase(
        "vpn_tunnel_drops",
        "How often did the branch tunnel disconnect?",
        "tunnel=dc-mia drops=8821 uptime_pct=61",
        "tunnel=dc-mia drops=0 uptime_pct=99.99",
        "drop counter + uptime",
    ),
    ProbeCase(
        "artifact_checksum",
        "How many build outputs failed verification?",
        "build=8841 artifacts=1204 mismatches=88 signed=false",
        "build=8841 artifacts=1204 mismatches=0 signed=true",
        "mismatch count at fixed artifact total",
    ),
    ProbeCase(
        "redis_eviction",
        "How many entries did the cache shed under pressure?",
        "node=redis-3 evicted=882104 used_pct=99 policy=lru",
        "node=redis-3 evicted=0 used_pct=41 policy=lru",
        "eviction counter, policy shared",
    ),
    ProbeCase(
        "lb_target_unhealthy",
        "How many backends were pulled from rotation during the outage?",
        "asg=api-prod healthy=0 total=12 removed=12",
        "asg=api-prod healthy=12 total=12 removed=0",
        "healthy vs removed at fixed total",
    ),
    ProbeCase(
        "login_redirect",
        "Where did the sign-in page send users during the incident?",
        "from=/login to=http://admin.internal:9000 code=302 hits=4410",
        "from=/login to=https://app.example.com code=302 hits=4410",
        "target URL is the only difference",
    ),
    ProbeCase(
        "index_fragmentation",
        "How fragmented had the events index become?",
        "table=events frag_pct=94 size_gb=882 reindex=overdue",
        "table=events frag_pct=2 size_gb=882 reindex=ok",
        "fragmentation percentage",
    ),
    ProbeCase(
        "dedup_leak",
        "How many repeats slipped past the dedup filter?",
        "stream=clicks dupes=44102 rate_pct=5.0 state=leaking",
        "stream=clicks dupes=12 rate_pct=0.1 state=clean",
        "dupe counter + rate",
    ),
    ProbeCase(
        "ci_cache_miss",
        "What hit rate did the pipeline cache see during slow builds?",
        "cache=gradle hit_pct=4 dur_s=2880",
        "cache=gradle hit_pct=94 dur_s=180",
        "hit percentage",
    ),
    ProbeCase(
        "compaction_stall",
        "How long had compaction been falling behind?",
        "table=metrics stuck_s=7210 behind=882104 state=stalled",
        "table=metrics stuck_s=2 behind=0 state=idle",
        "stuck duration + backlog",
    ),
    ProbeCase(
        "canary_rollback",
        "What error percentage forced the pilot release back?",
        "release=2026.10.1 exposure=8pct err_pct=14.2 decision=rollback",
        "release=2026.10.1 exposure=8pct err_pct=0.1 decision=promote",
        "error rate at fixed exposure",
    ),
    ProbeCase(
        "bucket_access_denied",
        "Which permission change broke the uploads?",
        "bucket=uploads-prod code=403 policy=modified principal=ci-deploy",
        "bucket=uploads-prod code=200 policy=unchanged principal=ci-deploy",
        "policy state + status",
    ),
    ProbeCase(
        "cpu_throttling",
        "How much CPU was clawed back on the API nodes?",
        "node=api-3 throttle_pct=88 runq=44 state=throttled",
        "node=api-3 throttle_pct=0 runq=2 state=ok",
        "throttle percentage",
    ),
    ProbeCase(
        "seat_oversell",
        "How many bookings exceeded available inventory?",
        "flight=LA442 oversold=14 seats=8821 check=failed",
        "flight=LA442 oversold=0 seats=8821 check=passed",
        "oversell counter at fixed seats",
    ),
    ProbeCase(
        "log_flood",
        "How many lines per second did checkout emit during the storm?",
        "svc=checkout lines_s=882104 bytes_s=9921044",
        "svc=checkout lines_s=1410 bytes_s=99210",
        "rate magnitude",
    ),
    ProbeCase(
        "partition_skew",
        "How unevenly were events distributed across partitions?",
        "topic=user-events skew=0.97 top=882104 bottom=120",
        "topic=user-events skew=0.02 top=441020 bottom=412044",
        "skew ratio + extrema",
    ),
    ProbeCase(
        "legacy_cipher",
        "Which crypto suite did the old client insist on?",
        "client=java-8 cipher=TLS_RSA_WITH_AES_128_CBC_SHA downgrade=1 handshake=fail",
        "client=java-8 cipher=TLS_AES_128_GCM_SHA256 downgrade=0 handshake=ok",
        "suite name decides, no keywords",
    ),
    ProbeCase(
        "stale_nodes_after_rollback",
        "How many machines still ran the bad build after revert?",
        "cluster=prod stale_nodes=44 total_nodes=44 state=stuck",
        "cluster=prod stale_nodes=0 total_nodes=44 state=clean",
        "stale count at fixed total",
    ),
    ProbeCase(
        "stream_backpressure",
        "How many events were buffered when the pipeline paused?",
        "stream=user-events buffered=882104000 cap=1000000000 state=paused",
        "stream=user-events buffered=1024 cap=1000000000 state=flowing",
        "buffer depth at fixed cap",
    ),
    ProbeCase(
        "cron_skew",
        "How many scheduled runs fired at the wrong hour?",
        "scheduler=nightly-cron wrong_hour=441 total=882 tz=UTC",
        "scheduler=nightly-cron wrong_hour=0 total=882 tz=UTC",
        "wrong-hour counter",
    ),
    ProbeCase(
        "upload_incomplete",
        "How many files were left half-uploaded after the timeout?",
        "bucket=uploads parts_done=3 parts_total=88 state=incomplete",
        "bucket=uploads parts_done=88 parts_total=88 state=complete",
        "parts_done at fixed total",
    ),
]


def make_block(
    case: ProbeCase,
    depth_tokens: int,
    kind: str,
    seed: int = 0,
    tail_tokens: int = 256,
) -> dict:
    """Build a probe block: filler to ~depth, one decisive line, short tail.

    kind: 'fact' inserts the incident line; 'noise_decoy' inserts the healthy
    lookalike; 'noise_unrelated' inserts filler only. depth 0 = control
    (decisive line alone, no filler, no tail).
    """
    if kind not in ("fact", "noise_decoy", "noise_unrelated"):
        raise ValueError(kind)
    rng = random.Random(f"{case.case_id}:{depth_tokens}:{kind}:{seed}")
    body = case.fact_body if kind == "fact" else case.decoy_body
    if depth_tokens == 0:
        tail_tokens = 0

    prefix: list[str] = []
    used = 0
    while used < max(0, depth_tokens - 48):
        line = _filler_line(rng)
        used += count_tokens(line) + 1
        prefix.append(line)

    middle: list[str] = []
    level = rng.choice(("INFO", "WARN", "ERROR", "DEBUG"))  # never a label cue
    if kind == "noise_unrelated":
        middle.append(_log_line(rng, level, rng.choice(UNRELATED_BODIES)))
    else:
        middle.append(_log_line(rng, level, body))

    suffix: list[str] = []
    tail_used = 0
    while tail_used < tail_tokens:
        line = _filler_line(rng)
        tail_used += count_tokens(line) + 1
        suffix.append(line)

    text = "\n".join(prefix + middle + suffix)
    return {
        "case_id": case.case_id,
        "kind": kind,
        "depth_tokens": depth_tokens,
        "probe_version": PROBE_VERSION,
        "fact_position_tokens": count_tokens("\n".join(prefix)),
        "total_tokens": count_tokens(text),
        "text": text,
    }


def build_grid(depths: list[int], cases: list[ProbeCase] | None = None, seed: int = 0) -> list[dict]:
    blocks = []
    for case in cases or CASES:
        for depth in depths:
            for kind in ("fact", "noise_unrelated", "noise_decoy"):
                blocks.append(make_block(case, depth, kind, seed=seed))
    return blocks
