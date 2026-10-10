# Forensics / Investigation Agent

Forensics / Investigation component of the **Cyber Incident Response Council** —
a multi-agent system where specialized AI agents investigate cyber incidents,
debate containment responses, exchange evidence, and vote on decisions.

**Stage A status:** foundation only. Contracts, interfaces, infrastructure,
and the coding-agent message bus are implemented and tested. No investigation
functionality is implemented yet (that is Stage B).

## Layout

| Path | Purpose |
|---|---|
| `contracts/` | Frozen (v1) Pydantic schemas shared by all workstreams |
| `src/forensics/` | Implementation packages (inference, tools, messaging, reasoning, api) |
| `coordination/` | Stdlib-only SQLite message bus for the six coding agents |
| `tests/` | Pytest suites (contracts, coordination, unit, integration, e2e) |
| `coding-agents/` | Stage B instructions for each coding agent |
| `simulations/` | Synthetic incident scenarios and ground truth (Stage B) |
| `docs/` | Architecture, audit, research, ownership, and handoff documents |
| `scripts/` | Verification and smoke-test scripts |

## Setup

```bash
cd /home/asus/forensics-agent
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
```

## Verify the foundation

```bash
.venv/bin/pytest            # all tests
.venv/bin/ruff check .      # lint
.venv/bin/mypy              # type check
```

## Coordination message bus (coding agents)

The six Stage B coding agents (plus `coordinator`) communicate through one
shared SQLite database that lives **outside** every worktree:

```bash
export FORENSICS_COORD_DB=/home/asus/forensics-agent-coordination/coordination.db
python3 -m coordination.cli init      # one-time setup
python3 -m coordination.cli register --agent tools-engineer --role "Forensic tools"
python3 -m coordination.cli send --sender tools-engineer --recipient integration-qa \
    --type PROGRESS --subject "search_logs interface done" --body "Tests passing."
python3 -m coordination.cli inbox --agent integration-qa
python3 -m coordination.cli history --sender tools-engineer --limit 20
```

See `docs/CODING_AGENT_COMMUNICATION.md` for the full command reference and
`AGENTS.md` for the mandatory communication checkpoints.

## Rules for all coding agents

Read `AGENTS.md` before making any change. Shared contracts in `contracts/`
are **frozen**; changes require a `CONTRACT_CHANGE_REQUEST` and coordinator
approval as described in `docs/OWNERSHIP.md`.
