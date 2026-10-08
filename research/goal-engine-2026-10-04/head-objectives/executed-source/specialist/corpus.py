"""Programmatic corpus for the EXP-02 necessity decision head.

Anti-memorization rules (docs/04 §1, learned from laya-lcc-relevance-v1):
- No fixed evidence sentences: every item is composed at generation time from
  domain vocabularies (subjects, values, levels, depths all randomized).
- Evidence and noise come from different composition paths; decoys share
  vocabulary with evidence and differ only in values (the P2 skill).
- Unrelated negatives sometimes carry *anomalous* values for a different
  subject (distractor anomalies kill "anomaly anywhere = keep" shortcuts).
- Log level is independent of the label (kills the ERROR=keep shortcut).
- Objective mentions the subject via name OR alias (kills string matching).
- OOD split holds out BOTH paraphrase template families AND subject-name
  pools. In-domain numbers are never quoted before the OOD gate (R2).

Output: JSONL splits in data/exp02/ + a manifest with generator version and
content-hash digests.
"""

from __future__ import annotations

import hashlib
import json
import os
import random
from dataclasses import dataclass, field

GENERATOR_VERSION = "corpus-exp02/0.4"
# v0.4 (2026-10-03): strict holdout partition in neg_unrelated distractors.
# Train and val splits draw distractors STRICTLY from TRAIN_DOMAINS, eliminating
# the holdout signature leakage identified in the 2026-10-03 independent audit.
# v0.3 (2026-10-03, EXP-2026-10-03-02): domain-diversity intervention after the
# probe v1.2 finding that transfer to unseen archetypes collapses (J≈.66 at
# control) while the v0.2 OOD gate read .891 — the gate held out templates and
# subjects but NEVER DOMAINS, so it could not predict probe generalization.
# Changes: +10 training archetypes (objectives are subject-free, probe-style),
# 4 domains held out entirely as the OOD split, and neg_unrelated now comes from
# a different domain's vocabulary (semantically unrelated to the objective).

OOD_HOLDOUT_NAMES = ("vector_drift", "bot_traffic", "pdf_render", "sms_delivery")

LEVELS = ("INFO", "WARN", "ERROR", "DEBUG")

TRAIN_PREFIX = (
    "checkout", "billing", "booking", "auth", "search", "cache", "queue",
    "ingest", "payment", "session", "index", "build", "report", "worker",
)
OOD_PREFIX = (
    "ledger", "notify", "catalog", "telemetry", "dispatch", "archive",
    "metrics", "policy", "signup", "pricing",
)
SUFFIX = ("svc", "api", "core", "worker", "relay")
ALIAS_NOUN = ("service", "component", "pipeline", "job")

FILLER_TPL = (
    "heartbeat ok seq={a}",
    "cache warm shard={b} keys={c} hit_ratio=0.{d}",
    "replayed offset={a} partition={b} lag_ms={e}",
    "gc pause young_gen elapsed_ms={e}",
    "pool stats active={c} idle={b} waiting=0",
    "checkpoint written offset={a} bytes={c}000",
    "retry scheduled attempt={b} backoff_ms={e}",
    "config reload ok changed={c} keys",
    "session sweep scanned={c} expired={b}",
    "metric flush points={c} interval_s=15",
)


@dataclass(frozen=True)
class Domain:
    name: str
    symptom: str                       # "the checkout timeout incident"
    anomaly: dict[str, str]            # decisive anomalous field values
    healthy: dict[str, str]            # same fields, healthy values
    field_tpl: str                     # extra fields appended to the line
    objectives: tuple[str, ...]        # 2 train + 2 OOD paraphrase families
    subject_hint: str = ""             # optional subject word for the objective


DOMAINS: tuple[Domain, ...] = (
    Domain(
        "http_status", "the checkout timeout incident",
        {"status": "504", "upstream": "payment-gateway", "elapsed_ms": "30021"},
        {"status": "200", "upstream": "payment-gateway", "elapsed_ms": "142"},
        "request_id={rid}",
        (
            "Which status code did {subj} return during {symptom}?",
            "During {symptom}, what response status came back from {subj}?",
            "What HTTP outcome did {subj} produce when {symptom} occurred?",
            "Report the response status observed on {subj} across {symptom}.",
        ),
    ),
    Domain(
        "disk_quota", "the build runner quota exhaustion",
        {"usage_pct": "97.3", "action": "evict-build-cache"},
        {"usage_pct": "41.0", "action": "none"},
        "path={path}",
        (
            "Which path exhausted the disk quota on {subj}?",
            "Where did storage usage spike on {subj} during the quota problem?",
            "What did the usage reading look like on {subj} when space ran out?",
            "State the disk usage the runner reported for {subj} at exhaustion time.",
        ),
    ),
    Domain(
        "config_change", "the login regression",
        {"flag": "legacy_token_verify", "value": "true", "rollout": "100pct"},
        {"flag": "legacy_token_verify", "value": "false", "rollout": "100pct"},
        "changed_by={rid}",
        (
            "Which configuration value changed on {subj} right before {symptom}?",
            "What flag state did {subj} have when {symptom} started?",
            "Which setting was flipped on {subj} ahead of {symptom}?",
            "Report the configuration change recorded for {subj} before {symptom}.",
        ),
    ),
    Domain(
        "pool_saturation", "the ingest backlog incident",
        {"active": "64", "idle": "0", "waiting": "211", "saturation": "1.00"},
        {"active": "12", "idle": "52", "waiting": "0", "saturation": "0.19"},
        "pool={rid}",
        (
            "Which worker pool was saturated on {subj} during {symptom}?",
            "What were the pool numbers on {subj} when the queue backed up?",
            "How saturated did {subj} report its workers during {symptom}?",
            "Give the saturation reading captured on {subj} at the incident peak.",
        ),
    ),
    Domain(
        "cache_perf", "the origin overload",
        {"hit_ratio": "0.11", "origin_rps": "9421", "evictions": "0"},
        {"hit_ratio": "0.93", "origin_rps": "141", "evictions": "0"},
        "shard={b}",
        (
            "What hit ratio did {subj} show when {symptom} began?",
            "How effective was the cache on {subj} at the start of {symptom}?",
            "Which cache reading explains {symptom} on {subj}?",
            "State the hit ratio logged by {subj} during the overload window.",
        ),
    ),
    Domain(
        "retry_storm", "the billing deadlock",
        {"attempts": "7", "backoff_ms": "64000", "final": "abort"},
        {"attempts": "1", "backoff_ms": "250", "final": "ok"},
        "error={rid}",
        (
            "How many times did {subj} retry before giving up?",
            "What retry count did {subj} reach during {symptom}?",
            "How aggressively did {subj} retry before the final outcome?",
            "Report the attempt count recorded for {subj} in the deadlock window.",
        ),
    ),
    Domain(
        "sweep_jobs", "the memory climb",
        {"expired": "38922", "reaper": "stalled", "leak_estimate_mb": "1841"},
        {"expired": "104", "reaper": "ok", "leak_estimate_mb": "0"},
        "scanned={a}",
        (
            "What did the session sweep on {subj} report when {symptom} started?",
            "How many expired sessions did {subj} count during {symptom}?",
            "What reaper state did {subj} log while memory was climbing?",
            "Give the sweep numbers recorded on {subj} during the leak window.",
        ),
    ),
    Domain(
        "deploy_rollout", "the latency regression",
        {"rollout": "100pct", "error_rate_pct": "8.2", "p99_ms": "14200"},
        {"rollout": "10pct", "error_rate_pct": "0.1", "p99_ms": "340"},
        "deploy={rid}",
        (
            "Which deployment state did {subj} show during {symptom}?",
            "What rollout and error numbers did {subj} report when latency spiked?",
            "How wide was the rollout on {subj} when {symptom} appeared?",
            "State the release exposure recorded for {subj} at the regression peak.",
        ),
    ),
    # --- v0.3 (EXP-2026-10-03-02): +10 training archetypes, none of them a
    # probe v1.2 case archetype (anti-contamination: probes stay held out) ---
    Domain(
        "api_contract", "the payload contract break",
        {"fields_missing": "7", "schema": "v3", "violations": "4410"},
        {"fields_missing": "0", "schema": "v3", "violations": "0"},
        "request_id={rid}",
        (
            "How many fields did {subj} drop from its replies during {symptom}?",
            "What violation count did {subj} log when {symptom} started?",
            "Which gap size showed up across {subj} during {symptom}?",
            "State the missing-field tally recorded on {subj} amid {symptom}.",
        ),
    ),
    Domain(
        "geoshard_routing", "the region routing fault",
        {"region": "us-east-1", "expected": "eu-west-1", "misrouted_pct": "38.2"},
        {"region": "eu-west-1", "expected": "eu-west-1", "misrouted_pct": "0.4"},
        "shard={b}",
        (
            "Where did {subj} send traffic during {symptom}?",
            "What region did {subj} pick when {symptom} began?",
            "Which placement did {subj} choose amid {symptom}?",
            "Report the routing destination captured on {subj} across {symptom}.",
        ),
    ),
    Domain(
        "audit_log_gap", "the compliance trail gap",
        {"events": "0", "coverage_pct": "61.2", "state": "gap"},
        {"events": "9921", "coverage_pct": "100", "state": "complete"},
        "stream={a}",
        (
            "How many audit entries did {subj} capture during {symptom}?",
            "What record count did {subj} report when {symptom} started?",
            "How complete was the trail on {subj} across {symptom}?",
            "Give the entry total observed on {subj} amid {symptom}.",
        ),
    ),
    Domain(
        "cost_runaway", "the runaway compute bill",
        {"spend_usd": "8821", "budget_usd": "500", "jobs": "4410"},
        {"spend_usd": "94", "budget_usd": "500", "jobs": "12"},
        "account={rid}",
        (
            "How much did {subj} spend during {symptom}?",
            "What bill total did {subj} reach when {symptom} started?",
            "How far over budget did {subj} run across {symptom}?",
            "Report the cost figure recorded on {subj} at the peak of {symptom}.",
        ),
    ),
    Domain(
        "fraud_false_positive", "the overzealous fraud sweep",
        {"blocked": "9921", "appeals": "4410", "rule": "velocity-7"},
        {"blocked": "12", "appeals": "0", "rule": "velocity-7"},
        "policy={rid}",
        (
            "How many transactions did {subj} refuse during {symptom}?",
            "What block count did {subj} reach when {symptom} began?",
            "How aggressive was {subj} with holds across {symptom}?",
            "State the refusal tally logged by {subj} amid {symptom}.",
        ),
    ),
    Domain(
        "i18n_missing", "the broken translation rollout",
        {"keys_missing": "8821", "locale": "pt-BR", "fallback_pct": "41"},
        {"keys_missing": "0", "locale": "pt-BR", "fallback_pct": "0"},
        "bundle={b}",
        (
            "How many strings did {subj} fail to translate during {symptom}?",
            "What gap did {subj} report when {symptom} started?",
            "How much did {subj} fall back during {symptom}?",
            "Report the missing-key count observed on {subj} across {symptom}.",
        ),
    ),
    Domain(
        "image_pull_failure", "the deploy fetch errors",
        {"pulls_failed": "4410", "image": "api:2026.10.1", "backoff_s": "64"},
        {"pulls_failed": "0", "image": "api:2026.10.1", "backoff_s": "1"},
        "node={a}",
        (
            "How many fetches did {subj} fail during {symptom}?",
            "What pull failure count did {subj} log when {symptom} began?",
            "How often did {subj} miss the download across {symptom}?",
            "State the failed-pull tally recorded on {subj} amid {symptom}.",
        ),
    ),
    Domain(
        "monitoring_flap", "the noisy monitoring storm",
        {"flaps": "4410", "checks": "9021", "alert": "firing"},
        {"flaps": "2", "checks": "9021", "alert": "ok"},
        "probe={b}",
        (
            "How many times did {subj} flip during {symptom}?",
            "What transition count did {subj} record when {symptom} started?",
            "How often did {subj} change state across {symptom}?",
            "Give the flip total observed on {subj} amid {symptom}.",
        ),
    ),
    Domain(
        "pii_in_logs", "the data exposure finding",
        {"pii_rows": "9921", "sample": "address", "redaction": "off"},
        {"pii_rows": "0", "sample": "address", "redaction": "on"},
        "file={rid}",
        (
            "How many rows did {subj} expose during {symptom}?",
            "What sensitive-record count did {subj} report when {symptom} surfaced?",
            "How wide was the leak on {subj} across {symptom}?",
            "State the exposed-row tally logged by {subj} amid {symptom}.",
        ),
    ),
    Domain(
        "grpc_deadline", "the call deadline failures",
        {"deadlines": "8821", "exceeded_pct": "61", "target_ms": "2000"},
        {"deadlines": "3", "exceeded_pct": "0.2", "target_ms": "2000"},
        "method={rid}",
        (
            "How many calls did {subj} run out of time on during {symptom}?",
            "What deadline count did {subj} hit when {symptom} began?",
            "How often did {subj} overshoot across {symptom}?",
            "Report the expired-call tally recorded on {subj} amid {symptom}.",
        ),
    ),
    # --- v0.3 OOD holdout: these four NEVER appear in train/val — the OOD gate
    # becomes a true unseen-archetype read that can predict probe transfer ---
    Domain(
        "vector_drift", "the ranking quality slide",
        {"drift": "0.147", "threshold": "0.03", "samples": "9021"},
        {"drift": "0.008", "threshold": "0.03", "samples": "9021"},
        "model={rid}",
        (
            "How far did {subj} drift during {symptom}?",
            "What divergence reading did {subj} show when {symptom} started?",
            "How unstable was {subj} across {symptom}?",
            "State the deviation measured on {subj} amid {symptom}.",
        ),
    ),
    Domain(
        "bot_traffic", "the scripted traffic wave",
        {"bot_pct": "94.1", "requests": "882104", "captcha": "off"},
        {"bot_pct": "1.2", "requests": "441020", "captcha": "on"},
        "zone={b}",
        (
            "What share of hits on {subj} was automated during {symptom}?",
            "How much scripted traffic did {subj} see when {symptom} began?",
            "What percentage did {subj} attribute to scripts across {symptom}?",
            "Report the automation ratio observed on {subj} amid {symptom}.",
        ),
    ),
    Domain(
        "pdf_render", "the document generation hang",
        {"pages_done": "3", "pages_total": "120", "state": "stalled"},
        {"pages_done": "120", "pages_total": "120", "state": "done"},
        "job={rid}",
        (
            "How many pages did {subj} finish during {symptom}?",
            "What progress count did {subj} reach when {symptom} started?",
            "How far did {subj} get across {symptom}?",
            "State the completed-page tally recorded on {subj} amid {symptom}.",
        ),
    ),
    Domain(
        "sms_delivery", "the message delivery shortfall",
        {"delivered_pct": "61.2", "carrier": "vodafone", "queued": "99210"},
        {"delivered_pct": "99.8", "carrier": "vodafone", "queued": "14"},
        "route={b}",
        (
            "What delivery rate did {subj} achieve during {symptom}?",
            "How many messages actually arrived from {subj} when {symptom} began?",
            "What success percentage did {subj} post across {symptom}?",
            "Report the arrival ratio observed on {subj} amid {symptom}.",
        ),
    ),
)

#: v0.3 split discipline: train/val never see the holdout archetypes, and the OOD
#: split sees NOTHING but them (domains, templates and subjects all unseen).
TRAIN_DOMAINS = tuple(d for d in DOMAINS if d.name not in OOD_HOLDOUT_NAMES)
HOLDOUT_DOMAINS = tuple(d for d in DOMAINS if d.name in OOD_HOLDOUT_NAMES)


def _subject(rng: random.Random, pool: tuple[str, ...]) -> tuple[str, str]:
    name = f"{rng.choice(pool)}-{rng.choice(SUFFIX)}"
    alias = f"the {name.split('-')[0]} {rng.choice(ALIAS_NOUN)}"
    return name, alias


def _filler(rng: random.Random, n: int) -> list[str]:
    return [_filler_line(rng) for _ in range(n)]


def _filler_line(rng: random.Random) -> str:
    return rng.choice(FILLER_TPL).format(
        a=rng.randint(10000, 99999), b=rng.randint(1, 64),
        c=rng.randint(10, 9999), d=rng.randint(10, 98), e=rng.randint(3, 480),
    )


def _line(rng: random.Random, subject: str, fields: dict[str, str]) -> str:
    level = rng.choice(LEVELS)  # independent of label — anti-shortcut
    kv = " ".join(f"{k}={v}" for k, v in fields.items())
    hh, mm, ss = rng.randint(0, 23), rng.randint(0, 59), rng.randint(0, 59)
    return f"{hh:02d}:{mm:02d}:{ss:02d} {level} {subject} {kv}"


def make_item(domain: Domain, split: str, index: int, seed: int = 0) -> dict:
    """One (objective, block, label) item. split: train | val | ood."""
    rng = random.Random(f"{GENERATOR_VERSION}:{domain.name}:{split}:{index}:{seed}")
    ood = split == "ood"
    pool = OOD_PREFIX if ood else TRAIN_PREFIX
    name, alias = _subject(rng, pool)

    # label 1 = evidence line present (anomaly values); 0 = decoy or unrelated
    kind = rng.choices(["pos", "neg_decoy", "neg_unrelated"], weights=[1, 1, 1])[0] \
        if split != "val" else ("pos" if index % 2 == 0 else rng.choice(["neg_decoy", "neg_unrelated"]))
    label = 1 if kind == "pos" else 0

    mention = alias if rng.random() < 0.5 else name
    tpl_pool = domain.objectives[2:] if ood else domain.objectives[:2]
    objective = rng.choice(tpl_pool).format(subj=mention, symptom=domain.symptom)

    fields = dict(domain.anomaly if label == 1 else domain.healthy)
    # substitute the domain-specific extra field values
    fmt = dict(
        rid=f"{rng.randint(16**5, 16**6-1):x}",
        path=f"/var/lib/{rng.choice(('docker', 'builds', 'tmp', 'cache'))}/{rng.randint(1, 40)}",
        b=rng.randint(1, 64),
        a=rng.randint(10000, 99999),
    )
    extra = domain.field_tpl.format(**fmt)

    if kind == "neg_unrelated":
        # v0.4: unrelated comes from a DIFFERENT domain's vocabulary, with strict
        # split isolation: train and val draw ONLY from TRAIN_DOMAINS (zero holdout
        # leakage), and ood draws ONLY from HOLDOUT_DOMAINS.
        other, _ = _subject(rng, pool)
        domain_pool = HOLDOUT_DOMAINS if ood else TRAIN_DOMAINS
        other_domain = rng.choice([d for d in domain_pool if d.name != domain.name])
        other_fields = dict(other_domain.anomaly if rng.random() < 0.3 else other_domain.healthy)
        other_extra = other_domain.field_tpl.format(**fmt)
        decisive = _line(rng, other, {**other_fields, **_extra_dict(other_extra)})
    else:
        decisive = _line(rng, name, {**fields, **_extra_dict(extra)})

    # Length control: independent stream, same target distribution for all kinds.
    lrng = random.Random(f"{GENERATOR_VERSION}:len:{domain.name}:{split}:{index}:{seed}")
    target_words = lrng.randint(120, 700)
    d_words = len(decisive.split()) + 1
    prefix_budget = max(4, int((target_words - d_words) * lrng.uniform(0.35, 0.65)))

    block_lines: list[str] = []
    used = 0
    while used < prefix_budget:
        line = _filler_line(rng)
        used += len(line.split()) + 1
        block_lines.append(line)
    block_lines.append(decisive)
    tail_budget = max(2, target_words - used - d_words)
    used = 0
    while used < tail_budget:
        line = _filler_line(rng)
        used += len(line.split()) + 1
        block_lines.append(line)

    text = "\n".join(block_lines)
    content_hash = hashlib.sha256((objective + "\n" + text).encode()).hexdigest()[:16]
    return {
        "id": f"{domain.name}-{split}-{index:05d}",
        "split": split,
        "domain": domain.name,
        "kind": kind,
        "label": label,
        "objective": objective,
        "text": text,
        "content_hash": content_hash,
        "generator_version": GENERATOR_VERSION,
    }


def _extra_dict(extra: str) -> dict[str, str]:
    out = {}
    for part in extra.split():
        if "=" in part:
            k, v = part.split("=", 1)
            out[k] = v
    return out


def build_split(split: str, per_domain: int, seed: int = 0) -> list[dict]:
    items = []
    domains = HOLDOUT_DOMAINS if split == "ood" else TRAIN_DOMAINS
    for domain in domains:
        for i in range(per_domain):
            items.append(make_item(domain, split, i, seed=seed))
    return items


def write_dataset(out_dir: str, counts: dict[str, int], seed: int = 0) -> dict:
    os.makedirs(out_dir, exist_ok=True)
    manifest = {"generator_version": GENERATOR_VERSION, "seed": seed, "splits": {}}
    seen: set[str] = set()
    for split, n in counts.items():
        items = build_split(split, n, seed=seed)
        kept = []
        for it in items:
            if it["content_hash"] in seen:
                continue  # content-hash disjointness across splits
            seen.add(it["content_hash"])
            kept.append(it)
        path = os.path.join(out_dir, f"{split}.jsonl")
        with open(path, "w") as f:
            for it in kept:
                f.write(json.dumps(it) + "\n")
        manifest["splits"][split] = {
            "n": len(kept),
            "digest": hashlib.sha256("".join(sorted(it["content_hash"] for it in kept)).encode()).hexdigest()[:16],
        }
    with open(os.path.join(out_dir, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2)
    return manifest


if __name__ == "__main__":
    import sys

    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "..", "data", "exp02e")
    # v0.4 counts: train = 18 train domains x 130 = 2340 (≈ v0.2's 2400),
    # val = 18 x 45 = 810, ood = 4 holdout domains x 240 = 960 (same as v0.2)
    m = write_dataset(out, {"train": 130, "val": 45, "ood": 240})
    print(json.dumps(m, indent=2))
