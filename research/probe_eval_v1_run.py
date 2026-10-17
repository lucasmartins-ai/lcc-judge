"""Operational driver for the frozen probe_eval_v1 harness (the harness file itself is not changed).

Guard added after the 2026-10-17 outage: a CLI that is logged out ("Not logged in") is treated like a usage limit,
so the run stops at once instead of caching the item as a failed call. Same CLI as the harness:

    python -m research.probe_eval_v1_run answer --set D --arm full
"""
import re
import sys

from research import probe_eval_v1 as pe

pe.LIMIT_RE = re.compile(pe.LIMIT_RE.pattern + r'|not logged in|please run /login|session limit', re.I)

if __name__ == '__main__':
    sys.exit(pe.main())
