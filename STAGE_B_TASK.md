# STAGE B TASK — integration-qa

You are `integration-qa`, one of six parallel coding agents building the
Forensics / Investigation Agent. Execute this task completely and autonomously.
Work ONLY in this worktree, on branch `test/integration-qa`. You own
`tests/integration/`, `tests/end_to_end/`, and validation scripts. The
coordinator has also pre-approved you to create `src/forensics/api/` (the
runnable service), because nobody else owns it — announce this on the bus
(PROGRESS) before you start on it.

## Ground rules (mandatory)

- Read first: `AGENTS.md`, `docs/OWNERSHIP.md`, `docs/CONTRACTS.md`,
  `docs/schema_export.json`, the Stage A test suites under `tests/`.
- Python: `source /home/asus/forensics-agent/.venv/bin/activate`.
- Bus: `export FORENSICS_COORD_DB=/home/asus/forensics-agent-coordination/coordination.db`
  heartbeat on start; check inbox at every checkpoint; you are the default
  recipient for other agents' READY_FOR_INTEGRATION messages (they will
  arrive while you run — poll `inbox --agent integration-qa` periodically).
- NEVER: push, merge unfinished branches, modify `contracts/` (frozen),
  bind anything except 127.0.0.1 (ephemeral ports in tests), touch other
  agents' worktrees, kill/reconfigure ollama (:11434)/llama-server (:8000),
  add heavy dependencies. Prefer the standard library.
- All checks green before finishing: `pytest`, `ruff check .`, `mypy`.
  Never claim tests pass without running them.

## YOUR MISSION

### 1. Cross-component integration tests (now, against mocks)
`tests/integration/` — prove the frozen contracts interoperate, using ONLY
components that exist on your branch (Stage A mocks):
- Evidence/Incident fixtures validate; InvestigationRequest drives
  `forensics.tools` mock registry; findings validate against
  `InvestigationFindings`; ToolInvocation audit records are produced.
- Contracts cross-validation: every Stage A mock produces data that other
  contracts accept (e.g., evidence ids flow into findings' cited_evidence_ids).
- Structured payload fixtures for all 9 CouncilMessage types validate.

### 2. End-to-end acceptance test (mock-powered, real interfaces)
`tests/end_to_end/test_investigation_cycle.py`: a complete cycle using real
component interfaces with mock inference/tools:
incident -> InvestigationRequest -> engine-style loop (use the Stage A mock
backend's generate_structured and the mock tool registry directly) ->
InvestigationFindings (validated) -> DebatePosition (SUPPORT/OPPOSE) ->
PositionRevision audit trail -> report payload -> ToolInvocation audit.
Design it so the mocks are swappable for the real implementations that will
arrive via merges (accept injected backend/registry — do not hardcode mocks).

### 3. Runnable local service (pre-approved for src/forensics/api/)
- `src/forensics/api/service.py`: a minimal localhost JSON service using
  ONLY the stdlib `http.server` (no new dependencies), binding 127.0.0.1 on
  a configurable port (env `FORENSICS_API_PORT`, default 8747). It wires
  injected backend/tools/engine components behind documented endpoints such
  as health, receive incident, request investigation (returns findings),
  receive proposal (returns position), receive evidence (returns a
  PositionRevision or no-change), and emits council messages through an
  injected transport. Endpoint paths are YOURS to define in code — keep a
  concise `src/forensics/api/README.md` documenting the exact routes,
  request/response examples (validated from your tests), and startup
  command. The service must start and serve within one test (ephemeral port
  or 127.0.0.1:PORT with retry), then shut down cleanly.

### 4. Validation scripts
- `scripts/verify_stage_b.sh`: full pytest + ruff + mypy + the smoke
  two-process bus test, printing a clear PASS/FAIL summary.
- `scripts/demo_scenario.py`: reproducible demonstration runner wiring the
  (injected) components through one synthetic incident cycle, printing the
  message sequence. Mocks now; real components after merges.

### 5. Merge review discipline (you do NOT merge)
The coordinator performs merges into this branch. When READY_FOR_INTEGRATION
messages arrive in your inbox, record them (ack), but do not merge branches.
After each coordinator merge, run the full suite here and report results.

## FINAL HANDOFF (mandatory)
1. Commit everything on `test/integration-qa`.
2. READY_FOR_INTEGRATION to `coordinator` (--branch test/integration-qa
   --commit <SHA> --body '<JSON: implemented_features, test_commands,
   test_results, known_limitations>').
3. PROGRESS summary to `coordinator`.
