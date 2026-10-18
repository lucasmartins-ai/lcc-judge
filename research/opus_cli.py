"""Claude Opus via the owner's subscription CLI, for the v5 cycle (edge v2 generator, system-1 teacher, sealed
final arm). Same safe argv as research.llm_judge_arm's 'opus' arm (no tools, no settings / CLAUDE.md, no
session persistence, never --dangerously-skip-permissions, ANTHROPIC_* stripped so an API key can never bill),
with the system prompt and JSON schema swapped per task.

Every CLI call (ok, failed or limit) is appended to LEDGER before it runs, and call() refuses once the ledger
holds CAP calls: the 1,500-call cap for the whole v5 cycle is enforced here, not by convention. Answers are cached
by sha256 of (system, schema, prompt), so reruns resume without spending calls. A usage-limit reply raises
llm_judge_arm.LimitHit at once (no retry loop).
"""
import hashlib
import json
import os
import subprocess
import time
from pathlib import Path

from research import llm_judge_arm as lj

ROOT = Path.home() / '.lcc/bench/v5'
LEDGER = ROOT / 'opus-calls.jsonl'
CACHE = ROOT / 'opus-cache'
CAP = 1500
TIMEOUT_S = 420


def argv(system, schema):
    a = lj.argv_for('opus')
    a[a.index('--json-schema') + 1] = json.dumps(schema)
    a[a.index('--system-prompt') + 1] = system
    assert not any('dangerously' in x for x in a) and a[a.index('--tools') + 1] == ''
    return a


def calls_used(ledger=LEDGER):
    return sum(1 for _ in open(ledger)) if Path(ledger).exists() else 0


def parse(stdout, stderr, rc):
    """-> structured object. Raises LimitHit / RuntimeError."""
    env = None
    try:
        env = json.loads(stdout)
    except ValueError:
        pass
    bad = rc != 0 or not isinstance(env, dict) or env.get('is_error') is True
    obj = None if bad else env.get('structured_output')
    if obj is None and not bad and isinstance(env.get('result'), str):
        try:
            obj = json.loads(env['result'].strip().removeprefix('```json').removesuffix('```'))
        except ValueError:
            obj = None
    if not isinstance(obj, dict):
        msg = f'{stdout[-2000:]}\n{stderr[-2000:]}'
        if lj.LIMIT_RE.search(msg):
            raise lj.LimitHit(lj.LIMIT_RE.search(msg).group(0))
        raise RuntimeError(f'no structured output (exit {rc}): {msg[-300:]!r}')
    return obj


def call(system, schema, prompt, tag, root=ROOT, runner=None):
    """Cached structured call. tag: short label for the ledger (e.g. 'gen', 'teacher', 'sealed')."""
    key = hashlib.sha256(json.dumps([system, schema, prompt], ensure_ascii=False).encode()).hexdigest()
    root = Path(root)
    cp = root / 'opus-cache' / f'{key}.json'
    if cp.exists():
        return json.loads(cp.read_text())
    ledger = root / 'opus-calls.jsonl'
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    cp.parent.mkdir(exist_ok=True, mode=0o700)
    if calls_used(ledger) >= CAP:
        raise SystemExit(f'opus cap reached ({CAP} calls)')
    cwd = root / '_empty_cwd'
    cwd.mkdir(exist_ok=True, mode=0o700)
    if any(cwd.iterdir()):
        raise SystemExit(f'{cwd} must stay empty')
    with open(ledger, 'a') as f:
        f.write(json.dumps(dict(t=round(time.time()), tag=tag, key=key[:16])) + '\n')
    if runner is None:
        r = subprocess.run(argv(system, schema), input=prompt, capture_output=True, text=True, cwd=cwd,
                           timeout=TIMEOUT_S, env={k: v for k, v in os.environ.items()
                                                   if not k.startswith(('PYTHON', 'ANTHROPIC_'))})
        so, se, rc = r.stdout, r.stderr, r.returncode
    else:
        so, se, rc = runner(prompt)
    obj = parse(so, se, rc)
    cp.write_text(json.dumps(obj, ensure_ascii=False))
    return obj
