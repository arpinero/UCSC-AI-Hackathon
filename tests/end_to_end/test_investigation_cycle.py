"""End-to-end acceptance test: one complete investigation cycle.

incident -> InvestigationRequest -> engine-style loop (mock backend's
generate_structured + mock tool registry) -> validated InvestigationFindings
-> DebatePosition (SUPPORT) -> PositionRevision audit trail (OPPOSE) ->
report payload -> ToolInvocation audit.

The engine harness takes an *injected* backend and registry, so these
mocks are swappable for the real implementations arriving via
coordinator merges (feat/inference, feat/forensic-tools, feat/reasoning).
"""

from __future__ import annotations

import pytest

from contracts.common import Position
from contracts.evidence import Evidence
from contracts.incident import Incident
from contracts.inference import (
    InferenceRequest,
    InferenceResult,
    ModelMetadata,
    StructuredGenerationRequest,
)
from contracts.investigation import (
    DebatePosition,
    InvestigationFindings,
    InvestigationRequest,
    PositionRevision,
)
from contracts.tools import SubmitIncidentReportArgs, ToolInvocation
from forensics.inference.base import InferenceBackend, InferenceBackendError
from forensics.tools.base import ToolRegistry
from forensics.tools.mock import MockBuildTimeline, MockSearchLogs
from tests.end_to_end.harness import MockInvestigationEngine
from tests.integration.scenario import (
    EVIDENCE_ID,
    EVIDENCE_ID_2,
    INCIDENT_ID,
    make_evidence,
    make_incident,
    make_position_payload,
    make_request,
)


def test_complete_investigation_cycle(backend, registry):
    engine = MockInvestigationEngine(backend=backend, registry=registry)

    # 1. Incident arrives and validates against the frozen contract.
    incident = Incident.model_validate(make_incident())
    assert incident.incident_id == INCIDENT_ID

    # 2. Council asks a question; the request drives the mock tool registry.
    request = InvestigationRequest.model_validate(make_request())
    assert request.available_evidence_ids == [EVIDENCE_ID]

    # 3. Engine-style loop: tools + structured generation produce findings.
    findings = engine.investigate(request)
    assert isinstance(findings, InvestigationFindings)
    assert findings.incident_id == request.incident_id
    assert findings.round == request.round
    assert EVIDENCE_ID in findings.cited_evidence_ids
    # Findings round-trip through the frozen contract (wire format).
    assert InvestigationFindings.model_validate_json(findings.model_dump_json()) == findings
    assert "generate_structured" in backend.calls  # structured inference was used
    assert {record.tool_name for record in engine.tool_audit} >= {
        "search_logs",
        "build_timeline",
    }

    # 4. Council proposal: engine takes a debate position.
    position = engine.evaluate_proposal(
        INCIDENT_ID,
        2,
        {"proposal_id": "PRP-1", "action": "isolate web-01"},
    )
    assert isinstance(position, DebatePosition)
    assert position.position is Position.SUPPORT
    assert position.incident_id == INCIDENT_ID
    assert DebatePosition.model_validate_json(position.model_dump_json()) == position

    # 5. New contradicting evidence forces an explicit, auditable revision.
    evidence = Evidence.model_validate(
        make_evidence(EVIDENCE_ID_2, description="Backup schedule shows transfer was sanctioned")
    )
    revision = engine.consider_evidence(evidence)
    assert isinstance(revision, PositionRevision)
    assert revision.previous_position.position is Position.SUPPORT
    assert revision.new_position.position is Position.OPPOSE
    assert revision.triggering_evidence_ids == [EVIDENCE_ID_2]
    assert PositionRevision.model_validate_json(revision.model_dump_json()) == revision

    # 6. Report payload flows through submit_incident_report (the only writer).
    report_invocation = registry.get("submit_incident_report").invoke(
        SubmitIncidentReportArgs(
            incident_id=findings.incident_id,
            findings_summary=findings.findings,
            cited_evidence_ids=findings.cited_evidence_ids,
            confidence=findings.confidence,
            severity_assessment=findings.severity_assessment or "HIGH",
            recommended_actions=findings.recommended_actions,
        ).model_dump(mode="json"),
        findings.incident_id,
    )
    assert report_invocation.error is None, report_invocation.error
    assert report_invocation.result is not None
    assert report_invocation.result["report_id"]

    # 7. Every tool call left a valid audit record.
    for record in engine.tool_audit:
        assert ToolInvocation.model_validate_json(record.model_dump_json()) == record
        assert record.error is None
        assert record.duration_ms >= 0
    assert {record.tool_name for record in engine.tool_audit} == {
        "search_logs",
        "build_timeline",
    }


def test_engine_accepts_swapped_components():
    """The harness must not be hardwired to the Stage A mock classes."""
    stub_backend = _StubBackend(default_position=Position.OPPOSE)
    minimal_registry = ToolRegistry()
    minimal_registry.register(MockSearchLogs())
    minimal_registry.register(MockBuildTimeline())
    engine = MockInvestigationEngine(backend=stub_backend, registry=minimal_registry)

    request = InvestigationRequest.model_validate(make_request())
    findings = engine.investigate(request)
    assert isinstance(findings, InvestigationFindings)
    assert findings.confidence == 0.42  # from the stub, not the Stage A mock

    position = engine.evaluate_proposal(INCIDENT_ID, 2, {"action": "isolate web-01"})
    assert position.position is Position.OPPOSE  # stub disagrees with the mock's SUPPORT

    evidence = Evidence.model_validate(make_evidence(EVIDENCE_ID_2))
    revision = engine.consider_evidence(evidence)
    assert isinstance(revision, PositionRevision)
    assert revision.previous_position.position is Position.OPPOSE
    assert revision.new_position.position is Position.SUPPORT  # flips the other way


def test_no_change_without_prior_position(backend, registry):
    engine = MockInvestigationEngine(backend=backend, registry=registry)
    evidence = Evidence.model_validate(make_evidence())
    assert engine.consider_evidence(evidence) is None


def test_failing_backend_surfaces_as_backend_error(registry):
    from forensics.inference.mock import MockInferenceBackend

    engine = MockInvestigationEngine(
        backend=MockInferenceBackend(fail_structured=True), registry=registry
    )
    request = InvestigationRequest.model_validate(make_request())
    with pytest.raises(InferenceBackendError):
        engine.investigate(request)


class _StubBackend(InferenceBackend):
    """Minimal alternative backend proving the engine is backend-agnostic."""

    def __init__(self, default_position: Position) -> None:
        self.default_position = default_position

    def generate(self, request: InferenceRequest) -> InferenceResult:
        return InferenceResult(text="stub", backend_name="stub-backend")

    def generate_structured(
        self, request: StructuredGenerationRequest, response_model: type
    ) -> object:
        if response_model is InvestigationFindings:
            payload = make_request()
            return InvestigationFindings.model_validate(
                {
                    "agent_id": "forensics-agent",
                    "incident_id": payload["incident_id"],
                    "round": payload["round"],
                    "findings": "[stub] stubbed findings",
                    "cited_evidence_ids": payload["available_evidence_ids"],
                    "confidence": 0.42,
                }
            )
        if response_model is DebatePosition:
            return DebatePosition.model_validate(
                make_position_payload(self.default_position.value, round=1)
            )
        raise InferenceBackendError(f"stub backend cannot produce {response_model.__name__}")

    def health_check(self) -> bool:
        return True

    def get_model_metadata(self) -> ModelMetadata:
        return ModelMetadata(
            model_id="stub/stub-1",
            backend_name="stub-backend",
            context_window=1024,
            supports_native_tool_calls=False,
            supports_structured_output=True,
            is_mock=True,
        )
