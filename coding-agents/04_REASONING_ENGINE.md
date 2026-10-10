# Stage B Workstream 04 — Reasoning Engineer

> **STATUS: PLACEHOLDER.** The full Stage B prompt will be supplied after
> Stage A review. Do not start until you receive it via the message bus.

- **Identity:** `reasoning-engineer`
- **Branch:** `feat/reasoning`
- **Worktree:** `/home/asus/forensics-worktrees/reasoning-engineer`
- **Ownership:** `src/forensics/reasoning/` (nothing else)

## Interfaces you must use (frozen contracts)

- `contracts/investigation.py`: InvestigationRequest, InvestigationFindings,
  TimelineEvent, DebatePosition, PositionRevision.
- Inference: `forensics.inference.base.InferenceBackend` (owned by
  model-engineer — REQUEST changes, never edit).
- Tools: `forensics.tools.base.ToolRegistry` (owned by tools-engineer).

## Expected deliverables (subject to the full Stage B prompt)

- Investigation loop: consume an InvestigationRequest, call tools through the
  registry, publish InvestigationFindings with cited evidence.
- Debate logic: produce DebatePosition on proposals; challenge unsupported
  recommendations; revise positions with explicit PositionRevision audit
  records when new evidence arrives (conditions_to_change_position honored).
- Model-specific parsing stays in `forensics.inference` — you consume typed
  results only.

## Communication rules

- Check `inbox --agent reasoning-engineer` at every checkpoint (see AGENTS.md).
- Request structured-output support from model-engineer via REQUEST messages.

## Required tests

- Unit tests with the MockInferenceBackend and mock tools covering: findings
  generation, position support/oppose/abstain, revision audit trail. Green
  pytest/ruff/mypy before handoff.

## Branch and commit rules

- Commit only to `feat/reasoning`. READY_FOR_INTEGRATION requires
  `--branch feat/reasoning --commit <sha>` + structured JSON body.
