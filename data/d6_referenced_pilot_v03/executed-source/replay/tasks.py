"""Curated fixtures for replay harness development; not P2 ground truth.

Per docs/04-dataset-strategy.md §4 and docs/07-risk-register.md (R19):
- 20 realistic tasks across debugging, coding, investigation, and structured_decision.
- Legacy executor/verifier names below are fixture placeholders, not installed executors.
- Pinned seeds, objectives, and context blocks.
- Explicit candidate blocks and expected keywords; decisive annotations are synthetic.
  Keyword checks do not execute coding tasks or validate fixes. Real outcome receipts
  and independently validated verifiers are required before P2 training admission.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Any, Callable


@dataclass
class ContextBlock:
    block_id: str
    content: str
    block_type: str  # log, code, diff, trace, config, doc
    source: str
    is_decisive: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "block_id": self.block_id,
            "content": self.content,
            "metadata": {
                "source": self.source,
                "block_type": self.block_type,
                "tool": None,
                "position": 0,
                "protected": False,
                "dependencies": [],
                "provenance": {"origin": "lcc-replay-pilot/v1", "transform": "none"},
            },
        }

    def to_executor_dict(self) -> dict[str, Any]:
        """Stable public identity; annotated IDs remain only in audit/label records."""
        value = self.to_dict()
        value['block_id'] = 'b_' + hashlib.sha256(self.block_id.encode()).hexdigest()[:16]
        return value


@dataclass
class ReplayTask:
    task_id: str
    task_class: str
    objective: str
    blocks: list[ContextBlock]
    candidate_block_id: str
    verifier_id: str = "ast-evaluator@1.0"
    executor_id: str = "hermes-replay-executor@2.1"
    required_keywords: list[str] = field(default_factory=list)

    @property
    def candidate_block(self) -> ContextBlock:
        for b in self.blocks:
            if b.block_id == self.candidate_block_id:
                return b
        raise KeyError(f"Candidate block {self.candidate_block_id} not found in task {self.task_id}")

    def content_hash(self) -> str:
        ctx_str = "\n".join(b.content for b in self.blocks)
        return hashlib.sha256((self.objective + "\n" + ctx_str).encode()).hexdigest()[:16]


TASKS: list[ReplayTask] = [
    # Task 1: Debugging connection pool exhaustion
    ReplayTask(
        task_id="task_001_conn_pool",
        task_class="debugging",
        objective="Identify the root cause of connection pool timeout errors in payment-gateway.",
        blocks=[
            ContextBlock("blk_01_arch", "Architecture: payment-gateway connects to Postgres via PgBouncer with pool_size=20.", "doc", "docs/arch.md"),
            ContextBlock("blk_01_cfg", "pg_pool: max_connections=20 timeout_ms=5000 leak_detection_threshold_ms=10000", "config", "config/database.yml"),
            ContextBlock("blk_01_log_noise", "2026-10-03T10:00:01Z [INFO] payment-gateway healthcheck ok 200", "log", "var/log/syslog"),
            ContextBlock("blk_01_leak_trace", "2026-10-03T10:01:23Z [ERROR] connection pool exhausted: active=20 idle=0 waiting=42; leaked_conn_holding_stack at billing.py:144 acquire_conn() without release in stripe_webhook_handler", "trace", "var/log/payment.log", is_decisive=True),
            ContextBlock("blk_01_metric", "metric: pg_pool_wait_duration_p99 value=5012ms threshold=2000ms", "log", "metrics/pg.log"),
        ],
        candidate_block_id="blk_01_leak_trace",
        required_keywords=["billing.py:144", "stripe_webhook_handler", "acquire_conn"],
    ),
    # Task 2: Investigation of redis cache stampede
    ReplayTask(
        task_id="task_002_redis_stampede",
        task_class="investigation",
        objective="Determine why redis cache hit ratio dropped to 12% at 09:30 UTC.",
        blocks=[
            ContextBlock("blk_02_noise1", "redis-cluster node 1: 1420 keys loaded, memory_used=4.2gb", "log", "redis/node1.log"),
            ContextBlock("blk_02_decisive", "2026-10-03T09:30:00Z [WARN] cache ttl expired synchronously for top_products_cache: key_expiry_time=3600s with jitter=0s; 1200 workers stampeded database", "log", "var/log/cache.log", is_decisive=True),
            ContextBlock("blk_02_noise2", "db query latency p50=12ms p99=450ms during read traffic burst", "log", "postgres/queries.log"),
            ContextBlock("blk_02_doc", "Cache guidelines: always set jitter on keys with high QPS to prevent stampedes.", "doc", "wiki/cache.md"),
        ],
        candidate_block_id="blk_02_decisive",
        required_keywords=["jitter=0s", "stampeded", "top_products_cache"],
    ),
    # Task 3: Coding deadlock fix in inventory reservation
    ReplayTask(
        task_id="task_003_inv_deadlock",
        task_class="coding",
        objective="Propose a fix for concurrent deadlock in inventory reservation.",
        blocks=[
            ContextBlock("blk_03_code_vuln", "def reserve_items(items):\n    # Bug: items acquired in arbitrary order causing circular wait\n    for item in items:\n        with lock_item(item.id):\n            decrement_stock(item)", "code", "services/inventory.py", is_decisive=True),
            ContextBlock("blk_03_trace", "2026-10-03T11:15:00Z [ERROR] Deadlock detected: transaction 44 waiting for lock on item 89 held by tx 45; tx 45 waiting for lock on item 12 held by tx 44", "trace", "var/log/inventory.log"),
            ContextBlock("blk_03_noise", "order-service checkout started for user_id=99281", "log", "var/log/orders.log"),
        ],
        candidate_block_id="blk_03_code_vuln",
        required_keywords=["sorted", "order", "circular wait"],
    ),
    # Task 4: Structured decision: Rollback deploy vs feature flag flip
    ReplayTask(
        task_id="task_004_rollback_decision",
        task_class="structured_decision",
        objective="Decide whether to execute full container rollback or flip dynamic flag.",
        blocks=[
            ContextBlock("blk_04_flag_doc", "Flag FAST_CHECKOUT: enables new checkout UI. Killswitch at /api/flags/fast_checkout=false takes effect in 500ms.", "doc", "docs/flags.md", is_decisive=True),
            ContextBlock("blk_04_error_rate", "Errors started immediately after flag enable at 14:00Z; container binary itself is identical to build v4.2.1.", "log", "deploy/audit.log", is_decisive=True),
            ContextBlock("blk_04_deploy_meta", "deploy v4.2.2 started 13:50Z, healthy checks 200/200", "log", "ci/deploy.log"),
        ],
        candidate_block_id="blk_04_flag_doc",
        required_keywords=["flip", "FAST_CHECKOUT", "killswitch"],
    ),
    # Task 5: Debugging memory leak in WebSocket server
    ReplayTask(
        task_id="task_005_ws_leak",
        task_class="debugging",
        objective="Locate object accumulation causing OOM in websocket-gateway.",
        blocks=[
            ContextBlock("blk_05_heap", "Heap dump summary: 450,000 instances of UnclosedClientSession in websocket/session_manager.py:88 client_cleanup() registered event listener never removed", "trace", "heaps/dump-12.txt", is_decisive=True),
            ContextBlock("blk_05_noise", "GC pause duration: young=4ms mixed=120ms full=1400ms", "log", "var/log/jvm.log"),
            ContextBlock("blk_05_config", "websocket.max_connections: 50000 ping_interval: 30s", "config", "ws.conf"),
        ],
        candidate_block_id="blk_05_heap",
        required_keywords=["UnclosedClientSession", "event listener", "session_manager.py"],
    ),
    # Task 6: Coding: SQL injection vulnerability remediation
    ReplayTask(
        task_id="task_006_sql_injection",
        task_class="coding",
        objective="Fix SQL injection vulnerability in user search filter.",
        blocks=[
            ContextBlock("blk_06_vuln", "def search_users(tenant_id, query):\n    # Raw string format injection\n    sql = f\"SELECT * FROM users WHERE tenant_id = '{tenant_id}' AND name LIKE '%{query}%'\"\n    return db.execute(sql)", "code", "api/users.py", is_decisive=True),
            ContextBlock("blk_06_audit", "Security audit finding SEC-402: parameter query in /api/v1/users/search vulnerable to SQLi", "doc", "audit/sec.md"),
            ContextBlock("blk_06_noise", "tenant_id header parsed from JWT bearer token", "doc", "auth.md"),
        ],
        candidate_block_id="blk_06_vuln",
        required_keywords=["parameterized", "prepare", "db.execute"],
    ),
    # Task 7: Investigation: Kafka consumer group lag accumulation
    ReplayTask(
        task_id="task_007_kafka_lag",
        task_class="investigation",
        objective="Identify why payment-consumer lag grew to 500k messages on partition 4.",
        blocks=[
            ContextBlock("blk_07_lag", "partition 4 consumer offset=12000 log_end_offset=512000 lag=500000", "log", "kafka/metrics.log"),
            ContextBlock("blk_07_thread_dump", "Thread-4 (partition 4): BLOCKED on external HTTP call to vendor-fraud-api.com:443 with timeout=None in fraud_check.py:42", "trace", "stacks/thread_dump.txt", is_decisive=True),
            ContextBlock("blk_07_noise", "partitions 0, 1, 2, 3 processing rate: 2500 msg/sec", "log", "kafka/consumer.log"),
        ],
        candidate_block_id="blk_07_thread_dump",
        required_keywords=["vendor-fraud-api.com", "timeout=None", "fraud_check.py:42"],
    ),
    # Task 8: Structured decision: Circuit breaker threshold tuning
    ReplayTask(
        task_id="task_008_circuit_breaker",
        task_class="structured_decision",
        objective="Recommend circuit breaker trip threshold for partner billing service.",
        blocks=[
            ContextBlock("blk_08_sla", "Partner billing SLA guarantees 99.5% availability with max acceptable latency 1500ms; downstream cascading timeout at 2000ms.", "doc", "slas/partner.md", is_decisive=True),
            ContextBlock("blk_08_traffic", "Current traffic: 300 req/sec; current failure rate 2.1% under normal loads.", "log", "metrics/traffic.log"),
            ContextBlock("blk_08_noise", "DNS resolution time: 2ms via local Unbound cache.", "log", "dns.log"),
        ],
        candidate_block_id="blk_08_sla",
        required_keywords=["1500ms", "cascading", "threshold"],
    ),
    # Task 9: Debugging SSL handshake timeout
    ReplayTask(
        task_id="task_009_ssl_timeout",
        task_class="debugging",
        objective="Diagnose why external API webhooks fail during TLS handshake.",
        blocks=[
            ContextBlock("blk_09_noise", "HTTP client pool created with max_connections=50.", "log", "client.log"),
            ContextBlock("blk_09_pcap", "Packet capture analysis: Client sends TLS ClientHello; Server responds with fragmented Certificate (4096-bit RSA chain > MTU 1500); DF bit set causes PMTUD blackhole on router 10.0.1.1 drop ICMP Fragmentation Needed", "trace", "net/pcap_analysis.txt", is_decisive=True),
            ContextBlock("blk_09_sysctl", "net.ipv4.tcp_mtu_probing = 0", "config", "etc/sysctl.conf"),
        ],
        candidate_block_id="blk_09_pcap",
        required_keywords=["PMTUD", "blackhole", "fragmented Certificate", "MTU"],
    ),
    # Task 10: Coding: Idempotency key handling for checkout
    ReplayTask(
        task_id="task_010_idempotency",
        task_class="coding",
        objective="Implement idempotency check before charge dispatch.",
        blocks=[
            ContextBlock("blk_10_spec", "Idempotency requirements: check Redis key `idemp:{key}` with SET NX EX 120; if exists return cached response; otherwise execute charge.", "doc", "rfcs/idempotency.md", is_decisive=True),
            ContextBlock("blk_10_stub", "def process_payment(idempotency_key, amount):\n    # TODO: implement check\n    return stripe.Charge.create(amount=amount)", "code", "payment.py"),
            ContextBlock("blk_10_noise", "Stripe API version: 2024-06-12", "config", "stripe.env"),
        ],
        candidate_block_id="blk_10_spec",
        required_keywords=["SET NX", "idemp:", "cached response"],
    ),
    # Task 11: Investigation: CPU spike caused by regex catastrophic backtracking
    ReplayTask(
        task_id="task_011_regex_backtrack",
        task_class="investigation",
        objective="Explain 100% CPU lockup on ingress gateway.",
        blocks=[
            ContextBlock("blk_11_flame", "CPU flamegraph: 98.4% CPU in re.match regex pattern `^([a-zA-Z0-9]+)*$` matching input string 'aaaaaaaaaaaaaaaaaaaaaaaaaaaa!' in validation.py:31", "trace", "profiling/flamegraph.txt", is_decisive=True),
            ContextBlock("blk_11_noise", "Ingress worker count: 8 workers, Nginx frontend reverse proxy.", "config", "nginx.conf"),
            ContextBlock("blk_11_log", "Worker PID 14002 unresponsiveness watchdog triggered kill -9.", "log", "supervisor.log"),
        ],
        candidate_block_id="blk_11_flame",
        required_keywords=["backtracking", "validation.py:31", "catastrophic"],
    ),
    # Task 12: Debugging disk space exhaustion in worker node
    ReplayTask(
        task_id="task_012_disk_space",
        task_class="debugging",
        objective="Find what is filling up /var partition to 100%.",
        blocks=[
            ContextBlock("blk_12_df", "Filesystem: /dev/sda1 on /var size=100G used=100G avail=0", "log", "df.txt"),
            ContextBlock("blk_12_lsof", "lsof +L1: deleted file unlinked but held open by process python3 PID 8810: /var/log/app.log.1 (size=84GB) open for 24 days", "trace", "lsof.txt", is_decisive=True),
            ContextBlock("blk_12_cron", "logrotate cron configured at daily, compress, rotate 7", "config", "logrotate.conf"),
        ],
        candidate_block_id="blk_12_lsof",
        required_keywords=["unlinked", "held open", "PID 8810"],
    ),
    # Task 13: Coding: Race condition in bank account transfer
    ReplayTask(
        task_id="task_013_account_transfer",
        task_class="coding",
        objective="Add transaction isolation to prevent double spending during balance transfer.",
        blocks=[
            ContextBlock("blk_13_code", "def transfer(from_acc, to_acc, amount):\n    b = db.query('SELECT balance FROM accounts WHERE id = ?', from_acc)\n    if b >= amount:\n        db.execute('UPDATE accounts SET balance = balance - ? WHERE id = ?', amount, from_acc)\n        db.execute('UPDATE accounts SET balance = balance + ? WHERE id = ?', amount, to_acc)", "code", "ledger.py", is_decisive=True),
            ContextBlock("blk_13_bug_report", "User was able to trigger 3 simultaneous transfers of $100 with only $100 balance.", "doc", "issues/892.md"),
            ContextBlock("blk_13_noise", "Transfer fee is 0% for domestic bank wires.", "doc", "fees.md"),
        ],
        candidate_block_id="blk_13_code",
        required_keywords=["SELECT ... FOR UPDATE", "transaction", "isolation"],
    ),
    # Task 14: Structured decision: Database shard rebalancing strategy
    ReplayTask(
        task_id="task_014_shard_rebalance",
        task_class="structured_decision",
        objective="Select online versus maintenance window migration for shard 7.",
        blocks=[
            ContextBlock("blk_14_stats", "Shard 7 contains 4.8TB data, 12,000 IOPS write load. Maintenance window allows max 30 min downtime; full pg_dump/restore requires 6 hours.", "doc", "sharding/plan.md", is_decisive=True),
            ContextBlock("blk_14_logical", "Logical replication CDC via Debezium supports cutover in <15 seconds once caught up.", "doc", "cdc.md", is_decisive=True),
            ContextBlock("blk_14_noise", "Hardware: AWS r6i.4xlarge instances with gp3 EBS volumes.", "config", "infra.tf"),
        ],
        candidate_block_id="blk_14_stats",
        required_keywords=["Logical replication", "CDC", "downtime"],
    ),
    # Task 15: Debugging CORS error on frontend API calls
    ReplayTask(
        task_id="task_015_cors_error",
        task_class="debugging",
        objective="Determine why browser blocks POST requests from app.domain.com to api.domain.com.",
        blocks=[
            ContextBlock("blk_15_options", "2026-10-03T12:00:00Z OPTIONS /v1/checkout HTTP/1.1 response: Access-Control-Allow-Origin: * but Access-Control-Allow-Credentials: true; browser rejects credentials with wildcard origin", "trace", "net/browser_console.log", is_decisive=True),
            ContextBlock("blk_15_noise", "Cookie session: domain=.domain.com, SameSite=Lax, Secure=true", "config", "session.json"),
            ContextBlock("blk_15_middleware", "CORS middleware config: origins=['*'], allow_credentials=True", "code", "server/cors.py"),
        ],
        candidate_block_id="blk_15_options",
        required_keywords=["wildcard", "Access-Control-Allow-Credentials", "app.domain.com"],
    ),
    # Task 16: Coding: Rate limiter with leaky bucket algorithm
    ReplayTask(
        task_id="task_016_rate_limiter",
        task_class="coding",
        objective="Implement rate limiting decorator with leak rate and capacity.",
        blocks=[
            ContextBlock("blk_16_formula", "Leaky bucket formula: water = max(0, water - (now - last_leak) * leak_rate); if water + 1 <= capacity: allow; water += 1", "doc", "algorithms/bucket.md", is_decisive=True),
            ContextBlock("blk_16_api_spec", "Target rate: 100 requests per minute with burst capacity 150.", "doc", "api_limits.md"),
            ContextBlock("blk_16_noise", "HTTP 429 Too Many Requests response payload schema.", "doc", "responses.md"),
        ],
        candidate_block_id="blk_16_formula",
        required_keywords=["water", "leak_rate", "capacity"],
    ),
    # Task 17: Investigation: Silent data corruption in numeric rounding
    ReplayTask(
        task_id="task_017_float_rounding",
        task_class="investigation",
        objective="Find why billing reconciliation showed 1-cent discrepancy on monthly invoices.",
        blocks=[
            ContextBlock("blk_17_calc", "Tax calculation function: `total = float(subtotal) * 1.0825`; rounding happens via Python float `round(total, 2)` instead of `decimal.Decimal(subtotal) * Decimal('1.0825')` with ROUND_HALF_EVEN", "code", "accounting/tax.py", is_decisive=True),
            ContextBlock("blk_17_report", "Monthly audit report: 1,420 invoices had mismatch of -$0.01 between line items sum and invoice total.", "doc", "audit/sep2026.csv"),
            ContextBlock("blk_17_noise", "Invoices generated on the 1st of every month via Celery cron.", "log", "celery.log"),
        ],
        candidate_block_id="blk_17_calc",
        required_keywords=["Decimal", "float", "rounding"],
    ),
    # Task 18: Structured decision: Kubernetes pod disruption budget
    ReplayTask(
        task_id="task_018_k8s_pdb",
        task_class="structured_decision",
        objective="Configure PodDisruptionBudget for critical search-indexing cluster.",
        blocks=[
            ContextBlock("blk_18_quorum", "Search index cluster requires minimum 3 out of 5 quorum replicas alive to process queries without read degradation.", "doc", "k8s/search_ha.md", is_decisive=True),
            ContextBlock("blk_18_deploy", "Deployment replicas: 5; node upgrades drain 1 node at a time.", "config", "k8s/deploy.yaml"),
            ContextBlock("blk_18_noise", "Image: elasticsearch:8.11.2 with custom synonyms plugin.", "config", "Dockerfile"),
        ],
        candidate_block_id="blk_18_quorum",
        required_keywords=["minAvailable: 3", "quorum", "maxUnavailable: 2"],
    ),
    # Task 19: Debugging DNS resolution flap in Alpine containers
    ReplayTask(
        task_id="task_019_alpine_dns",
        task_class="debugging",
        objective="Diagnose 5-second latency spikes in Go service running on Alpine Linux.",
        blocks=[
            ContextBlock("blk_19_musl", "musl libc resolver in Alpine does not support `options single-request-reopen`; concurrent A and AAAA queries with same source port cause conntrack drop in Linux kernel NAT", "trace", "net/dns_spike.txt", is_decisive=True),
            ContextBlock("blk_19_resolv", "nameserver 10.96.0.10\nsearch default.svc.cluster.local svc.cluster.local cluster.local\noptions ndots:5", "config", "etc/resolv.conf"),
            ContextBlock("blk_19_noise", "Go runtime version: go1.22.4 linux/arm64", "doc", "version.txt"),
        ],
        candidate_block_id="blk_19_musl",
        required_keywords=["musl", "single-request-reopen", "conntrack"],
    ),
    # Task 20: Coding: Token bucket rate limiter test suite
    ReplayTask(
        task_id="task_020_limiter_tests",
        task_class="coding",
        objective="Write unit test verifying burst handling in token bucket.",
        blocks=[
            ContextBlock("blk_20_req", "Test must assert that 5 consecutive requests at t=0 succeed when capacity=5, and the 6th immediately returns False; then after 1s recovery 1 request succeeds.", "doc", "specs/test_spec.md", is_decisive=True),
            ContextBlock("blk_20_noise", "import unittest; from unittest.mock import patch", "code", "tests/base.py"),
            ContextBlock("blk_20_config", "DEFAULT_BURST = 5; REFILL_RATE = 1.0", "config", "limits.py"),
        ],
        candidate_block_id="blk_20_req",
        required_keywords=["capacity=5", "6th", "recovery"],
    ),
]
