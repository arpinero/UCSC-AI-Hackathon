# STAGE B TASK — reasoning-engineer

You are `reasoning-engineer`, one of six parallel coding agents building the
Forensics / Investigation Agent. Execute this task completely and autonomously.
Work ONLY in this worktree, on branch `feat/reasoning`. You own
`src/forensics/reasoning/` (and its tests).

## Ground rules (mandatory)

- Read first: `AGENTS.md`, `docs/OWNERSHIP.md`, `docs/CONTRACTS.md`,
  `contracts/investigation.py`, `contracts/inference.py`,
  `src/forensics/inference/base.py`, `src/forensics/inference/mock.py`,
  `src/forensics/tools/base.py`, `src/forensics/tools/mock.py`.
- Python: `source /home/asus/forensics-agent/.venv/bin/activate`.
- Bus: `export FORENSICS_COORD_DB=/home/asus/forensics-agent-coordination/coordination.db`
  heartbeat on start; PROGRESS at milestones; BLOCKER to coordinator on
  problems. REQUEST (not edit) anything you need from model-engineer or
  tools-engineer; use their mocks meanwhile.
- NEVER: push, modify `contracts/` (frozen), edit files outside your
  ownership, fake model output, or cite evidence that was not provided.
- All checks green before finishing: `pytest`, `ruff check .`, `mypy`.
  Never claim tests pass without running them.

## YOUR MISSION (owner: src/forensics/reasoning/)

The actual intelligence of the forensics agent. All components receive
`InferenceBackend` and `ToolRegistry` via constructor injection — the engine
must work with the Stage A mocks today and real backends after integration.
Never import a concrete backend.

### 1. Investigation loop (`investigation.py`)
- `InvestigationEngine.investigate(request: InvestigationRequest,
  evidence: list[Evidence]) -> InvestigationFindings`.
- Model-directed tool use: iteratively ask the backend (generate_structured
  toward ToolCallRequest) which tool to call next, execute via the registry
  (`invoke()` — audit records), feed results back, up to a bounded number of
  steps (e.g., 8). If the model's tool selection is invalid/unavailable,
  fall back to a deterministic rule-based selection so the engine NEVER
  dead-ends on a weak model.
- Findings must cite ONLY evidence ids that exist in the provided evidence
  (validate; hard requirement). Reconstruct a timeline (via build_timeline
  or from evidence timestamps) into TimelineEvent entries.
- If evidence is insufficient: low confidence, non-empty uncertainties, and
  an explicit escalation recommendation instead of invented conclusions.

### 2. Proposal evaluation (`debate.py`)
- `evaluate_proposal(proposal: dict, evidence: list[Evidence],
  findings: InvestigationFindings) -> DebatePosition` — SUPPORT / OPPOSE /
  ABSTAIN with reasoning grounded in cited evidence, confidence, and
  concrete `conditions_to_change_position`.
- `challenge(findings/position)` — generate a Challenge CouncilMessage
  payload when another agent's claim is unsupported by available evidence.

### 3. Position revision (`revision.py`)
- Given a current DebatePosition and newly arrived evidence, decide whether
  any `conditions_to_change_position` are met; if so produce an explicit
  `PositionRevision` (previous + new position + triggering evidence ids +
  explanation). The position changes ONLY because of evidence — never
  because of social pressure; if a CHALLENGE cites no new evidence that meets
  your stated conditions, the position stands and you answer the challenge.

### 4. Final recommendation (`report.py`)
- `recommend(findings, position) -> recommended_actions + report payload`
  suitable for submit_incident_report; include abstention/escalation paths.

### 5. Tests (with MockInferenceBackend + Stage A mock tools)
- Full happy-path investigation: findings cite only real evidence; timeline
  ordered; tool calls bounded.
- Weak-model path: backend returns garbage -> rule-based fallback still
  produces valid findings.
- Proposal SUPPORT and OPPOSE cases; ABSTAIN when evidence thin.
- Revision: contradictory evidence flips SUPPORT->OPPOSE with a proper
  PositionRevision; pressure-only challenge does NOT flip the position.
- No-fabrication: citing a nonexistent evidence id must fail loudly in tests.

## FINAL HANDOFF (mandatory)
1. Commit everything on `feat/reasoning`.
2. READY_FOR_INTEGRATION to `integration-qa` (--branch feat/reasoning
   --commit <SHA> --body '<JSON: implemented_features, test_commands,
   test_results, known_limitations>').
3. PROGRESS summary to `coordinator`.
