# Coding-Agent Communication (Level 2 dev coordination)

This is the DEVELOPMENT message bus for the six coding agents — completely
separate from the runtime council messaging (AGNTCY / contracts/messages.py).

## Implementation

- **Python standard library only** (`sqlite3`, `argparse`, `dataclasses`):
  runs from any worktree with plain `python3` — no venv activation required
  to send/read messages.
- **Storage:** one SQLite database, WAL mode, `busy_timeout=15000` ms,
  `BEGIN IMMEDIATE` transactions, local filesystem check (ext4 verified;
  network filesystems are detected and warned about).
- **Path (outside every worktree, never committed):**

```bash
export FORENSICS_COORD_DB=/home/asus/forensics-agent-coordination/coordination.db
```

Verified init output: `journal_mode: wal, filesystem_type: ext4,
network_filesystem: False, agents_registered: 7`.

## Identities (7)

`model-engineer`, `tools-engineer`, `agntcy-engineer`, `reasoning-engineer`,
`evaluation-engineer`, `integration-qa`, `coordinator`.
Identities are self-declared (`--sender`); the bus validates them against
the registry and enforces role rules (e.g. only `coordinator` may send
CONTRACT_CHANGE_DECISION, and only in reply to an existing request).

## Message types

PROGRESS, REQUEST, RESPONSE, BLOCKER, CONTRACT_CHANGE_REQUEST,
CONTRACT_CHANGE_DECISION, READY_FOR_INTEGRATION, TEST_FAILURE, BROADCAST,
HEARTBEAT.

Structured JSON bodies are REQUIRED for BLOCKER (component, reproduction,
affected_workstream, suggested_fix, can_continue), READY_FOR_INTEGRATION
(implemented_features, test_commands, test_results, known_limitations +
--branch/--commit), CONTRACT_CHANGE_REQUEST (contract, proposed_change,
rationale), and CONTRACT_CHANGE_DECISION (decision, rationale,
contract_version when approved).

## Status lifecycle

`PENDING -> READ -> ACKNOWLEDGED -> RESOLVED` (transitions idempotent and
non-regressing). Correlation IDs: a new message threads at itself; `reply`
inherits the original's correlation_id; broadcasts share one correlation.

## CLI reference (exact syntax)

```bash
python3 -m coordination.cli [--db PATH] [--json] <command> ...

init                                     # create DB, WAL, register 7 identities
register   --agent <id> [--role TEXT]     # (re)register identity
send       --sender <id> --recipient <id> --type <TYPE> --subject TEXT
           [--body TEXT | --body-file F] [--priority LOW|NORMAL|HIGH|URGENT]
           [--correlation-id ID] [--branch B] [--commit SHA] [--message-id ID]
reply      --sender <id> --to <message_id> [--type RESPONSE] [--subject TEXT]
           --body ... [--branch B] [--commit SHA] [--message-id ID]
broadcast  --sender <id> --subject TEXT --body ...
heartbeat  --agent <id> [--note TEXT]     # liveness + progress note -> coordinator
inbox      --agent <id> [--all] [--limit N]
read       --agent <id> --message-id <ID> # PENDING -> READ for the recipient
ack        --agent <id> --message-id <ID> # recipient only
resolve    --agent <id> --message-id <ID>  # sender/recipient/coordinator
status                                     # per-agent counts + heartbeats
history    [--agent A] [--sender S] [--recipient R] [--correlation-id C]
           [--type T] [--after-seq N] [--limit N] [--full]
watch      --agent <id> [--timeout 30] [--interval 1]   # bounded poll; exit 10 on timeout
```

Exit codes: 0 ok, 1 unexpected, 2 validation, 3 database unavailable,
4 not found, 5 permission, 6 idempotency conflict, 10 watch timeout.

`--json` gives machine-readable output (all commands). Idempotency: retrying
`send`/`reply` with the same `--message-id` and identical content is a no-op;
differing content with the same id is rejected (conflict).

## Verified capabilities vs. checkpoint polling (read carefully)

Inspected coding-agent execution environment (verified 2026-10-10):
the agent runner is the **Cline VS Code extension (v4.1.23)** inside a
VS Code Remote-SSH server on this machine, with sessions stored under
`~/.cline/sessions` and `~/.openclaw`.

Three distinct capability levels:

1. **Messages persisted and visible to the CLI — VERIFIED.** Any process,
   any worktree, any time: `inbox`, `history`, `status` show all traffic.
2. **Running agents check and process messages at defined checkpoints —
   SUPPORTED (by discipline, enforced by AGENTS.md).** Sessions can run
   local scripts (verified — that is how agents use the CLI), so they
   check `inbox` at the mandatory checkpoints: task start, before touching
   another agent's files, after finishing a component, on blockers, before
   integration commits, before declaring completion.
3. **Automatic wakeup/interruption of an LLM session when a message
   arrives — NOT SUPPORTED (not verified).** No session hook, background
   notification, or programmatic "poke" mechanism was found in the
   installed runner. **Do not claim otherwise.** Consequently:
   - No agent may assume another agent has seen a message until the other
     agent acknowledges it.
   - `watch` is bounded polling with a clean exit — useful inside a task,
     not a substitute for checkpoints.
   - If a human can host sessions with a runner that supports hooks, that
     capability can be added later; until then, polling is the contract.

A successful two-process smoke test proves the BUS works across processes
and worktrees; it does NOT prove autonomous LLM sessions receive anything
without polling. The real smoke test executed on the shared database
PASSED (request -> read -> reply -> read -> ack, with ordering, correlation
and status transitions verified) — see scripts/smoke_two_process.sh.
