# STAGE B TASK — agntcy-engineer

You are `agntcy-engineer`, one of six parallel coding agents building the
Forensics / Investigation Agent. Execute this task completely and autonomously.
Work ONLY in this worktree, on branch `feat/agntcy`. You own
`src/forensics/messaging/` (and its tests).

## Ground rules (mandatory)

- Read first: `AGENTS.md`, `docs/OWNERSHIP.md`, `docs/CONTRACTS.md`,
  `docs/AGNTCY_INTEGRATION.md`, `contracts/messages.py`.
- Python: `source /home/asus/forensics-agent/.venv/bin/activate`.
- Bus: `export FORENSICS_COORD_DB=/home/asus/forensics-agent-coordination/coordination.db`
  heartbeat on start; PROGRESS at milestones; BLOCKER to coordinator on
  problems (structured JSON body per AGENTS.md).
- NEVER: push, deploy, modify `contracts/` (frozen), start long-running
  daemons that outlive your session, bind anything except 127.0.0.1 on an
  EPHEMERAL port in tests, touch other agents' worktrees, kill/reconfigure
  ollama (:11434) or llama-server (:8000), store secrets.
- All checks green before finishing: `pytest`, `ruff check .`, `mypy`.
  Never claim tests pass without running them.

## YOUR MISSION (owner: src/forensics/messaging/)

### Step 1 — verify SLIM on ARM64 (do this FIRST, timeboxed to ~20 min)
In a THROWAWAY venv under /tmp (not the shared venv), attempt to install the
AGNTCY SLIM Python bindings (check PyPI: try `pip install slim-bindings`,
`pip install agntcy-slim`, or whatever `pip index` / web search shows as the
official package from agntcy/slim-bindings). Record the exact command and
result. Do NOT spend more than ~20 minutes.
- If it installs AND a minimal pub/send-receive example works: implement
  `src/forensics/messaging/slim_transport.py` wrapping it, and record a
  GENUINE message exchange in your tests (mock-free) — then you may claim
  SLIM transport.
- If not (likely): send a BLOCKER to coordinator with the exact error, and
  proceed with Step 2+3. Never claim SLIM/AGNTCY compliance you did not run.

### Step 2 — transport-agnostic council messaging core
`src/forensics/messaging/`:
- `base.py`: `Transport` ABC (`send(msg: CouncilMessage)`,
  `receive(...) -> CouncilMessage`, `subscribe(incident_id)`, `close()`),
  plus `CouncilBus`/`Session` abstractions keyed by incident.
- All inputs/outputs validate through `contracts.messages.CouncilMessage`
  (reject invalid envelopes with clear errors). Correlation IDs thread
  replies to origins; every message belongs to an incident + round.
- `history.py`: auditable debate history for an incident (ordered, queryable
  by correlation_id/round/type; persists to a caller-provided path, default
  `/home/asus/forensics-agent-coordination/debate-history/<incident_id>.jsonl`).

### Step 3 — transports
- `memory.py`: reliable in-process transport (the mock) for the rest of the
  team and for tests.
- `http_a2a.py`: A2A-style HTTP fallback — a small client + server using
  ONLY the stdlib (`http.server` + `urllib.request`), exchanging
  CouncilMessage JSON envelopes on 127.0.0.1, per-incident endpoints,
  ephemeral ports, clean shutdown. This is what we can call "A2A-compatible
  envelopes over HTTP (fallback transport)" — describe it precisely in
  docstrings; do not call it SLIM or claim AGNTCY stack compliance.

### Step 4 — tests
- Unit: envelope validation (invalid rejected), correlation threading,
  subscribe-per-incident isolation, history ordering/persistence.
- Integration: a REAL loopback HTTP exchange between two endpoints on
  127.0.0.1 (two processes or two ports in-process): INCIDENT_ALERT ->
  EVIDENCE_REQUEST -> EVIDENCE_RESPONSE -> FINDING, verified from both sides
  and present in the debate history. Print nothing secret; use ephemeral ports.

## FINAL HANDOFF (mandatory)
1. Commit everything on `feat/agntcy`.
2. READY_FOR_INTEGRATION to `integration-qa` (--branch feat/agntcy
   --commit <SHA> --body '<JSON: implemented_features, test_commands,
   test_results, known_limitations>'). State plainly whether SLIM worked
   (with the recorded exchange) or the HTTP/A2A fallback is what ships.
3. PROGRESS summary to `coordinator`, including the SLIM investigation result.
