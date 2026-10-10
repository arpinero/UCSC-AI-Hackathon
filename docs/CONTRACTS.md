# Shared Contracts (v1 — FROZEN)

Version: `CONTRACTS_VERSION = "1.0.0"` in `contracts/common.py`.

**Status:** authoritative inside this repository. Cross-team (Containment /
Recovery / Compliance / shared simulator) they are **PROPOSED** until the four
human developers agree. See `docs/TEAM_INTEGRATION_STAGE_A.md`.

## Modules

| File | Models | Notes |
|---|---|---|
| common.py | Severity, IncidentStatus, Position, Confidence, UTCDateTime, json_schema_export | shared vocabulary |
| incident.py | Incident | REQUIRES TEAM AGREEMENT: field names, severity/status values |
| evidence.py | Evidence, EvidenceAcknowledgement | stable IDs; explicit provenance (source, collected_at) |
| messages.py | CouncilMessageType (9 types), CouncilMessage | runtime envelope; REQUIRES TEAM AGREEMENT |
| investigation.py | InvestigationRequest, TimelineEvent, InvestigationFindings, DebatePosition, PositionRevision | revision keeps previous+new position, triggering evidence, explanation |
| inference.py | ChatMessage, ToolSpec, ToolCallRequest, FinishReason, InferenceRequest, InferenceResult, StructuredGenerationRequest, ModelMetadata | internal to forensics |
| tools.py | ToolError, ToolInvocation + args/result models for the 7 tools | ToolInvocation = audit record with duration_ms >= 0 |

## Validation guarantees (all enforced by tests)

- strict: `extra="forbid"`, non-empty strings, stripped whitespace
- timestamps: timezone-aware, normalized to UTC (naive timestamps rejected)
- confidence: 0.0..1.0; rounds and durations: non-negative integers
- enums: Severity (CRITICAL..INFO), IncidentStatus (OPEN..CLOSED),
  Position (SUPPORT/OPPOSE/ABSTAIN), CouncilMessageType (9 values),
  FinishReason
- JSON Schema export: `contracts.common.json_schema_export([...])`
- serialization: `model_validate_json(model_dump_json())` round-trips

## Changing a contract (governance)

1. Send `CONTRACT_CHANGE_REQUEST` (JSON body: contract, proposed_change,
   rationale) to `coordinator` via the coordination bus.
2. Coordinator reviews and replies with `CONTRACT_CHANGE_DECISION`
   (decision: APPROVED/REJECTED; APPROVED requires contract_version).
3. Only then: edit the contract, bump `CONTRACTS_VERSION`, broadcast.
4. Messages never mutate contracts; Git commits are the source of truth.
