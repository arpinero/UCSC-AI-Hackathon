# forensics-api — runnable local service (Stage B, integration-qa)

A minimal localhost JSON service wiring the Forensics / Investigation
Agent's injected components behind HTTP. **Standard library only**
(`http.server`) — no new dependencies. It binds `127.0.0.1` only (never
0.0.0.0) on a configurable port.

## Startup

```bash
source /home/asus/forensics-agent/.venv/bin/activate
export FORENSICS_API_PORT=8747          # optional; default 8747
PYTHONPATH=src python -m forensics.api.service
```

`PYTHONPATH=src` is required in worktrees: the shared venv's editable
install maps `forensics` to the main repo's `src/`, which does not (yet)
contain `forensics/api`. After merging into the main repo the plain
`python -m forensics.api.service` works.
```

Until the real workstreams merge, the standalone entry point wires the
Stage A mock components (`forensics.inference.mock`, `forensics.tools.mock`,
and the `tests/end_to_end/harness.py` engine). After the coordinator merges
`feat/inference`, `feat/forensic-tools`, and `feat/reasoning`, replace
`build_default_service()` with real wiring — nothing else changes.

## Injection interface

`ForensicsService(engine, transport, host="127.0.0.1", port=None)`:

- `engine` — any object implementing the `InvestigationEngine` protocol
  (defined in `tests/end_to_end/harness.py`):
  - `investigate(request: InvestigationRequest) -> InvestigationFindings`
  - `evaluate_proposal(incident_id: str, round: int, proposal: dict) -> DebatePosition`
  - `consider_evidence(evidence: Evidence) -> PositionRevision | None`
- `transport` — `Callable[[CouncilMessage], None]`; every council-facing
  action is emitted as a `CouncilMessage` envelope through it (the real
  AGNTCY transport from `feat/agntcy` plugs in here).
- `port=None` uses `FORENSICS_API_PORT` (default `8747`); pass `0` for an
  ephemeral port (used by tests). `service.bound_port` reports the actual
  bound port. `start()` returns it too.

## Routes

### `GET /health` -> 200

```json
{"status": "ok", "service": "forensics-api", "contracts_version": "1.0.0"}
```

### `POST /incidents` — receive an incident

Body: an `Incident` contract payload. Emits `INCIDENT_ALERT`.
Response `201`:

```json
{"incident_id": "INC-2026-001", "status": "accepted"}
```

### `POST /investigations` — request investigation

Body: an `InvestigationRequest` contract payload. Emits `FINDING`
(correlation_id = request_id). Response `200`:

```json
{"request_id": "REQ-INC-2026-001-1",
 "findings": {"agent_id": "forensics-agent", "incident_id": "INC-2026-001",
              "round": 1, "findings": "...", "cited_evidence_ids": ["EV-..."],
              "confidence": 0.85, "uncertainties": [], "timeline": [],
              "recommended_actions": [], "severity_assessment": null}}
```

### `POST /proposals` — receive a council proposal

Body: `{"incident_id": "INC-2026-001", "round": 2, "proposal": {...}}`.
Returns the engine's `DebatePosition` and emits `VOTE`. Response `200`:

```json
{"position": {"agent_id": "forensics-agent", "incident_id": "INC-2026-001",
              "round": 2, "position": "SUPPORT", "supporting_evidence_ids": [],
              "opposing_evidence_ids": [], "reasoning": "...", "confidence": 0.7,
              "conditions_to_change_position": []}}
```

### `POST /evidence` — receive new evidence

Body: an `Evidence` contract payload. Emits `EVIDENCE_RESPONSE` (ack);
emits `REVISION` only when the engine revises its position.
Response `200`:

```json
{"revised": true,
 "revision": {"agent_id": "forensics-agent", "incident_id": "INC-2026-001",
              "round": 3, "previous_position": {"...": "SUPPORT"},
              "new_position": {"...": "OPPOSE"},
              "triggering_evidence_ids": ["EV-INC-2026-001-0002"],
              "explanation": "New evidence changed the assessment: ..."}}
```

or, when no revision is warranted: `{"revised": false, "revision": null}`.

### Errors

- `400` — invalid JSON, contract validation failure, bad envelope fields,
  or unknown POST path (`{"error": "..."}`; validation failures add `"detail"`).
- `404` — unknown GET path.
- `503` — engine/backend failure (`InferenceBackendError`).
- `500` — unexpected internal error (never crashes the process).

## Tests

`tests/integration/test_api_service.py` starts the service on an ephemeral
127.0.0.1 port, exercises every route above, asserts the council message
sequence (`INCIDENT_ALERT`, `FINDING`, `VOTE`, `EVIDENCE_RESPONSE`,
`REVISION`), and shuts it down cleanly. All response examples in this README
come from those validated tests.

## Demo

`python scripts/demo_scenario.py` runs one synthetic incident through the
whole service (mock-powered) and prints the emitted message sequence.
