# Integration Snapshot: `forensics` branch

This branch is a **work-in-progress integration snapshot** of the Forensics /
Investigation Agent, published for the four-agent Cyber Incident Response
Council integration. It is NOT a Stage B completion. Development by the six
Stage B coding agents is ongoing in parallel and is not interrupted by this
snapshot.

## Snapshot basis

- Base commit: `278b920` (branch `main`, Stage A foundation)
- Snapshot date: 2026-10-11 (initial baseline 2026-10-10, revised after the
  integration-qa READY_FOR_INTEGRATION handoff)
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
- **integration-qa Stage B suite** (merged from `test/integration-qa` @
  `8382f08`, posted READY_FOR_INTEGRATION on the coordination bus):
  the investigation HTTP API service (`src/forensics/api/`), integration
  tests (`tests/integration/`), end-to-end investigation-cycle tests
  (`tests/end_to_end/`), and validation/demo scripts
  (`scripts/verify_stage_b.sh`, `scripts/demo_scenario.py`).

## What is NOT included (work in progress)

Snapshot policy: only committed work announced via READY_FOR_INTEGRATION
on the coordination bus is merged. As of the snapshot time the following
workstreams are excluded (their code exists only as uncommitted files or
commits without a readiness handoff, and is not yet published):

- `model-engineer` (`feat/inference`): LLM inference backends committed at
  `093ebd3` (llama.cpp + Transformers SOC backends) but no
  READY_FOR_INTEGRATION posted yet and shared-file changes
  (`pyproject.toml`) pending coordinator review — work continues.
- `tools-engineer` (`feat/forensic-tools`): forensic tool suite — in
  progress (uncommitted).
- `agntcy-engineer` (`feat/agntcy`): AGNTCY/SLIM runtime messaging — in
  progress (uncommitted).
- `reasoning-engineer` (`feat/reasoning`): investigation/debate engine — in
  progress (uncommitted).
- `evaluation-engineer` (`feat/evaluation`): synthetic scenarios, loader,
  scoring, benchmark — in progress (uncommitted).

A later snapshot will merge each remaining workstream once its agent posts
READY_FOR_INTEGRATION on the coordination bus.

## Running the checks

```bash
source .venv/bin/activate   # or use the team venv
pytest
ruff check .
mypy
```

Note: this snapshot contains the Stage A foundation plus the integration-qa
suite. The inference, tools, messaging, reasoning, and simulation components
are still placeholders, so a full end-to-end investigation against a live
model is not yet exercisable; the e2e suite currently drives the mock
inference backend.
