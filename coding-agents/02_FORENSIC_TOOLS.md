# Stage B Workstream 02 — Forensic Tools Engineer

> **STATUS: PLACEHOLDER.** The full Stage B prompt will be supplied after
> Stage A review. Do not start until you receive it via the message bus.

- **Identity:** `tools-engineer`
- **Branch:** `feat/forensic-tools`
- **Worktree:** `/home/asus/forensics-worktrees/tools-engineer`
- **Ownership:** `src/forensics/tools/` (nothing else)

## Interfaces you must implement (frozen contracts)

- Base class + registry: `forensics.tools.base.ForensicTool` /
  `forensics.tools.base.ToolRegistry` (validation, timeouts, audit records).
- Seven tools, args/result models in `contracts/tools.py`:
  `search_logs`, `get_host_context`, `get_user_context`,
  `lookup_mitre_technique`, `enrich_ip`, `build_timeline`,
  `submit_incident_report`.
- Existing mocks: `src/forensics/tools/mock.py` (keep tests passing).

## Expected deliverables (subject to the full Stage B prompt)

- Real read-only implementations over the synthetic incident store
  (`simulations/scenarios/`, owned by evaluation-engineer — coordinate!).
- Every result must carry evidence provenance (stable `evidence_id`s).
- `submit_incident_report` is the ONLY tool that may write (report artifacts).

## Communication rules

- Check `inbox --agent tools-engineer` at every checkpoint (see AGENTS.md).
- The synthetic data format is owned by `evaluation-engineer`: REQUEST, do
  not define it yourself.

## Required tests

- Extend `tests/unit/test_tools.py`; every tool: valid args, invalid args,
  timeout, provenance. `pytest`/`ruff`/`mypy` green before handoff.

## Branch and commit rules

- Commit only to `feat/forensic-tools`. READY_FOR_INTEGRATION requires
  `--branch feat/forensic-tools --commit <sha>` + structured JSON body.
