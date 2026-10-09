# Amendment — Jev cap raised to US$85 (2026-10-09)

Made **before any remote call** (no runs/jev_* directory existed; no Jev result had been seen).

- Why: the offline projection (project-cost.json) put jev_block at $42.29 and jev_transcript at
  $39.71 on the conservative cap basis ($31.03 / $27.64 uninflated), $82 together, above the
  $35 first approved. The owner chose, in chat, to run both arms with a hard cap of **US$85 total**.
- Change: protocol.json remote.cap_usd 35 -> 85, remote.arm_cap_usd 17.5 -> 45. Sections of
  PROTOCOL.md that cite $35/$17.50 describe the superseded cap.
- Harness fixes from the pre-run review (no change to offline arms, probes or scoring): global cost
  ledger across run dirs; remote runs refuse --runs/--ids (no selective retry); LCC's
  _jev_ledger.jsonl is scrubbed of the key; unused hardcoded cap constants removed.
- Hashes: protocol.json f7d8bf14db66acd5ea40a7b7c4345a0fa67a41d129f30c7005e99394ec9a99b4 -> 9b2edeed79c4eef710e17b0608ea002e6de5812f9fae899c43ff7042ab3c7d5d;
  research/real_context_bench.py 69ec9855c81c47411d89fa39e077e59ffdf8386101f79791498bfb93557f5ef4 -> 1d462543b39382113b1f03854d80f6850897f7591787c41c57c936f15604ec5e.
