# Integration Snapshot: `forensics` branch

This branch is a **work-in-progress integration snapshot** of the Forensics /
Investigation Agent, published for the four-agent Cyber Incident Response
Council integration. It is NOT a Stage B completion. Development by the six
Stage B coding agents is ongoing in parallel and is not interrupted by this
snapshot.

## Snapshot basis

- Base commit: `278b920` (branch `main`, Stage A foundation)
- Snapshot date: 2026-10-10
- Starting point: the shared Stage A foundation — project scaffold, frozen
  v1 Pydantic contracts (`contracts/`), the SQLite coding-agent message bus
  (`coordination/`), inference and tool interfaces, and project docs.

## What is included

- Project scaffold and packaging (`pyproject.toml`, `src/forensics/`).
- Frozen v1 contracts (`contracts/`, Pydantic; see `docs/CONTRACTS.md` and
  `docs/schema_export.json`).
- Coordination bus (stdlib-only SQLite message bus + CLI, `coordination/`).
- Documentation: architecture, ownership, contracts, model research,
  AGNTCY integration research, Stage B handoff, and team integration plan
  (`docs/`, `coding-agents/`, `AGENTS.md`).
- Placeholder modules for the six Stage B workstreams.

## What is NOT included (work in progress, not yet committed)

As of the snapshot time, none of the six Stage B workstreams had committed
implementation code to their branches yet; their work exists only as
uncommitted files in their local worktrees and is therefore excluded by
policy (no uncommitted or unfinished work is published):

- `model-engineer` (`feat/inference`): LLM inference backends
  (llama.cpp, transformers/Qwen tool parsing) — in progress.
- `tools-engineer` (`feat/forensic-tools`): forensic tool suite — in progress.
- `agntcy-engineer` (`feat/agntcy`): AGNTCY/SLIM runtime messaging — in progress.
- `reasoning-engineer` (`feat/reasoning`): investigation/debate engine — in progress.
- `evaluation-engineer` (`feat/evaluation`): synthetic scenarios, loader,
  scoring, benchmark — in progress.
- `integration-qa` (`test/integration-qa`): API service and integration /
  end-to-end tests — in progress.

A later snapshot will merge each workstream once its agent posts
READY_FOR_INTEGRATION on the coordination bus.

## Running the checks

```bash
source .venv/bin/activate   # or use the team venv
pytest
ruff check .
mypy
```

Note: this snapshot contains only foundation code; the six workstream
placeholder modules are intentionally minimal, so most Stage B functionality
is not yet exercisable end to end.
