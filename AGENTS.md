# AGENTS.md — Rules for ALL coding agents working in this repository

You are one of six parallel coding agents building the Forensics / Investigation
Agent. Read this file before doing anything else.

## Identities

`model-engineer`, `tools-engineer`, `agntcy-engineer`, `reasoning-engineer`,
`evaluation-engineer`, `integration-qa`, plus `coordinator` (a logical role that
approves contract changes; it is not a seventh continuously running agent).

## The message bus (MANDATORY)

All coordination happens through the shared SQLite bus — never through ad-hoc
file drops or chat logs. The database lives OUTSIDE every worktree:

```bash
export FORENSICS_COORD_DB=/home/asus/forensics-agent-coordination/coordination.db
python3 -m coordination.cli inbox --agent <your-identity>     # check mail
```

`python3 -m coordination.cli --help` lists all commands. Use `--json` for
machine-readable output. The bus validates identities, message types, and
structured bodies; it rejects secrets and oversized payloads.

## Communication checkpoints (REQUIRED)

There is NO verified mechanism that automatically wakes an LLM session when a
message arrives. Therefore you MUST check your inbox with the CLI:

1. At the start of every task (`inbox`), and handle PENDING mail first.
2. Before modifying any file owned by another agent (send a REQUEST first).
3. After completing a component (send PROGRESS or READY_FOR_INTEGRATION).
4. Immediately when blocked (send BLOCKER with the structured JSON body).
5. Before committing integration-facing changes.
6. Before declaring your workstream complete (zero unread messages, and send
   a READY_FOR_INTEGRATION message).

`watch --agent <id> --timeout 30` gives bounded polling; it exits 0 when mail
arrives, 10 on timeout. Never rely on being notified — poll explicitly.

## Ownership

- Edit ONLY files under your ownership (see `docs/OWNERSHIP.md`). Changes to
  another agent's area require an approved REQUEST in the message bus.
- `contracts/` is FROZEN at v1. Do not edit contract files. To change them,
  send a `CONTRACT_CHANGE_REQUEST` (JSON body: contract, proposed_change,
  rationale) to `coordinator` and wait for a `CONTRACT_CHANGE_DECISION`.
  Only then does anyone edit the contract, with a version bump and a broadcast.
- Git commits and shared contracts are the source of truth. Bus messages are
  coordination records only — they never mutate contracts or code.

## Workflow

1. `cd` into YOUR worktree (see `docs/OWNERSHIP.md` for the path).
2. Activate the environment: `source /home/asus/forensics-agent/.venv/bin/activate`
   (or use `/home/asus/forensics-agent/.venv/bin/pytest` etc. directly).
3. Work on YOUR branch only. Commit early and often with clear messages.
4. Run `pytest`, `ruff check .`, and `mypy` before every READY_FOR_INTEGRATION.
5. Include branch + commit SHA + test results in handoff messages.
6. Use synthetic incident data only. All forensic tools are read-only except
   `submit_incident_report`. Never touch real systems or credentials.

## Hard prohibitions

- Do not push to remotes, deploy services, or download model weights without
  explicit human approval.
- Do not modify `pyproject.toml` dependency pins without a REQUEST to the
  coordinator (shared toolchain).
- Do not kill or reconfigure the running `ollama` (:11434) or `llama-server`
  (:8000) processes on this machine.
- Do not store secrets, tokens, or large artifacts in messages or commits.
- Do not modify teammates' projects (`~/compliance-agent`, `~/containment-agent`).
