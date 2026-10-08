# Genuine agent requests v1

This folder covers an importer for prompts the owner typed into his coding agents. Each prompt becomes a redacted LCC request record. The data comes from his own machine, and he consented to the import. The records stay in `~/.lcc` and are never committed.

- Code: `research/import_agent_requests.py`
- Tests: `tests/test_import_agent_requests.py`, which uses small synthetic fixtures only
- Logs: `import-tests-red.log` (the module was missing), `import-tests-green.log` (16 tests), `full-suite.log` (293 tests passed)
- `summary.json`: counts only, no text

```
python3 -m research.import_agent_requests run       # idempotent; prints counts per source
python3 -m research.import_agent_requests summary   # counts per source / language / session
```

## Where data lives

The importer writes only to `~/.lcc/request-log/imported/<source>.jsonl`, outside this repo. Session hashes use `~/.lcc/request-log/.salt`, the salt file the live logger uses. If the file is missing, the importer creates it with `lcc.request_log._salt` (O_EXCL, mode 0600). Nothing in this folder contains prompt text.

## Record

`id` is the first 16 hex characters of `sha256(source \0 redacted_goal)`. It is also the dedupe key, so reruns append nothing.

The other fields are `source`, `provenance="genuine_agent_prompt"`, `goal`, `language`, `session_hash`, `timestamp_utc` (ISO, Z), `imported_at_utc` and `redaction_rules_sha256` (`lcc.request_log.RULESET_SHA256`).

- `goal` is the output of `lcc.request_log.redact` and is at most `MAX_GOAL_CHARS` (1000) characters.
- `language` comes from `detect_language` run on the redacted goal.
- `session_hash` is `session_hash("<source>:<native session id>", salt)`.

Redaction, language detection and hashing are imported from `/Users/Master/LCC/src/lcc/request_log.py`. They are not reimplemented here.

## Sources and rules

| source | store read (read-only) | human prompt = |
|---|---|---|
| claude | `~/.claude/projects/**/*.jsonl` | `type=user` records that are not meta, sidechain, compact summary, agent, tool result or SDK entrypoint, and not under `subagents/`. The text must not start with `<`, `You are Claude Code`, `[Workflow harness`, `[Request interrupted` and similar markers. |
| codex | `~/.codex/sessions/**/rollout-*.jsonl`, `history.jsonl` | `input_text` in sessions whose `source` is `vscode` or `cli` and that have no parent thread. The text after `## My request for Codex:` is kept. Text starting with `<…>`, AGENTS.md, file-list, in-app-browser, `Automation:` or plan-accept is dropped. Replayed turns are deduped. |
| hermes | `~/.hermes/state.db` (`mode=ro`) | `role=user` rows from desktop, cli, tui or whatsapp sessions with `display_kind` null or `steer`. The gateway, OOB, reply and attached-context wrappers are removed first. System and cron prefixes are dropped, and compaction copies are deduped. |
| antigravity | `~/.gemini/antigravity-cli/history.jsonl` | CLI input history. Slash commands and immediate re-submissions are dropped. |
| grok | `~/.grok/sessions/*/prompt_history.jsonl` | `is_bash=false`, excluding pasted log dumps and bare paths. |
| cursor | `~/.cursor/projects/*/agent-transcripts/*/*.jsonl` | Only the text inside `<user_query>`. Cursor built-ins and agent-dispatched briefs (`# Codex Task:`, `You are a senior …`) are dropped. |
| opencode | `~/.local/share/opencode/opencode.db` (`mode=ro`) | User text parts from top-level sessions, excluding `synthetic` parts and pasted log dumps. |

These steps apply to all sources:

- Empty prompts are dropped.
- Pure slash commands (`/compact`) are dropped.
- Prompts longer than 1000 characters are dropped as `too_long`, because they are likely pasted context or LLM-written briefs.
- Exact duplicates of a redacted goal within one source are dropped as `duplicate`. Repeated short replies such as `sim` or `continue` are therefore stored once per source.

Not decodable, so not imported:

- Antigravity IDE/CLI conversation stores: protobuf in SQLite `step_payload`, plus encrypted `.pb` files. That is about 1,100 conversations.
- Codex `thread_history_1.sqlite` and `state_5.sqlite`, which were not inspected and likely duplicate the rollouts.

Cursor records have no timestamp unless an injected `<timestamp>` tag is present, so `timestamp_utc` is null for 55 of 59 Cursor records.

## Counts (run 2026-10-08)

| source | written | sessions | pt | en | other/unknown | too_long | duplicate | injected/non-human/automation dropped |
|---|---|---|---|---|---|---|---|---|
| claude | 693 | 199 | 448 | 224 | 21 | 168 | 124 | 259 injected; 22,569 non-human records; 418 subagent files |
| codex | 930 | 358 | 644 | 262 | 24 | 584 | 204 (+76 replay) | 2,642 injected; 130,624 in subagent/exec sessions; 36 empty |
| hermes | 1,626 | 291 | 1,257 | 331 | 38 | 131 | 187 (+240 compaction copies) | 503 injected; 510 injected display kinds; 1,496 automation sources; 10 empty |
| opencode | 365 | 149 | 283 | 73 | 9 | 84 | 84 | 67 synthetic/subagent parts; 2 log dumps |
| grok | 85 | 31 | 62 | 22 | 1 | 20 | 13 | 2 log dumps |
| cursor | 59 | 12 | 37 | 22 | 0 | 18 | 5 | 179 automation briefs/built-ins; 1 without user_query |
| antigravity | 24 | 5 | 17 | 6 | 1 | 1 | 1 replay | 2 slash commands |
| **total** | **3,782** | **1,045** | **2,748** | **940** | **94** | **1,006** | | |

A second `run` wrote 0 records, and the output files kept the same sha256 hashes. No `denied_path` drops occurred.

A regex scan of the stored goals found 0 emails, 0 `sk-`/`ghp_`/`xox` tokens, 0 32-character hex strings and 0 `/Users/` paths.

Redaction v2 (2026-10-08). A review found 20 to 25 character mixed-case tokens, a bare `senha <value>` and an 11-digit run glued to letters. Three rules were added to `lcc.request_log.RULES` with tests: a `<TOKEN>` rule for 20 or more word characters that contain a 12+ alphanumeric run mixing lower case, upper case and digits; a `<TOKEN>` rule for a secret keyword followed by a value that contains a digit; and a `<NUMBER>` rule for 9 or more digits without a word boundary. The importer now refuses to append to a file written under an older `RULESET_SHA256`. All 7 output files were deleted and regenerated: 3,782 records, all on the new ruleset. A rescan found 0 hits for those shapes and 0 emails, URLs, `/Users/` paths, IPs, JWTs, Bearer values or key prefixes. Not covered: hyphenated slugs (one record, id `73029557e7ff6fc8`, should be checked by hand) and unquoted personal names.

## Privacy guarantees

- A path denylist (`DENY` in code, covered by tests) blocks every open: `safe_open` and `connect_ro` raise before touching any path that contains oauth, token, creds, credential, auth, secret, api_key, `.key`, `.pem`, cookie, keychain, `.env`, browser-profile, Login Data, installation_id or google_accounts. Browser profiles are never walked.
- Transcript stores are opened read-only. The SQLite databases are opened with `mode=ro`.
- Raw text is never written or printed. Only `redact()`ed goals are stored, and the CLI prints counts only.
- No network access is used, and nothing is committed. The data lives only in `~/.lcc`.

## Caveats

- Regex redaction cannot catch unquoted personal names (see the `RULES` comment in `lcc.request_log`).
- Sessions run inside this LCC-judge workflow count as Claude sessions when their first message was typed by the owner.
- Some prompts under 1000 characters are pasted briefs, so they are not hand-typed goals. The `provenance` field means the owner submitted the prompt, not that he wrote it himself.
