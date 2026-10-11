"""Shared fixtures for the reasoning unit tests."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from contracts.common import Position, utc_now
from contracts.evidence import Evidence
from contracts.investigation import (
    DebatePosition,
    InvestigationFindings,
    InvestigationRequest,
)
from contracts.messages import CouncilMessage, CouncilMessageType
from forensics.inference.base import InferenceBackendError
from forensics.inference.mock import MockInferenceBackend

INCIDENT = "INC-TEST-001"
BASE_TS = datetime(2026, 10, 10, 12, 0, 0, tzinfo=timezone.utc)


def make_evidence(
    evidence_id: str,
    *,
    minutes: int = 0,
    description: str = "Lateral movement via SSH from web-01 to db-01",
    event_type: str = "lateral_movement",
    host_id: str = "web-01",
    raw_data: dict[str, Any] | None = None,
    incident_id: str = INCIDENT,
) -> Evidence:
    ts = BASE_TS + timedelta(minutes=minutes)
    return Evidence(
        evidence_id=evidence_id,
        incident_id=incident_id,
        source="test-collector",
        event_type=event_type,
        timestamp=ts,
        host_id=host_id,
        description=description,
        raw_data=raw_data or {},
        collected_at=BASE_TS,
        collection_tool="test-harness",
    )


def make_request(**overrides: Any) -> InvestigationRequest:
    base: dict[str, Any] = {
        "request_id": "REQ-001",
        "incident_id": INCIDENT,
        "round": 1,
        "question": "Was there lateral movement from web-01?",
        "requested_by": "council",
    }
    base.update(overrides)
    return InvestigationRequest(**base)


def make_findings(
    *,
    cited: list[str] | None = None,
    confidence: float = 0.8,
    findings: str = "Lateral movement from web-01 to db-01 confirmed.",
    incident_id: str = INCIDENT,
    round_: int = 1,
    actions: list[str] | None = None,
    severity: str | None = "HIGH",
    uncertainties: list[str] | None = None,
) -> InvestigationFindings:
    return InvestigationFindings(
        agent_id="forensics-agent",
        incident_id=incident_id,
        round=round_,
        findings=findings,
        cited_evidence_ids=cited if cited is not None else ["EV-1001"],
        confidence=confidence,
        uncertainties=uncertainties or [],
        timeline=[],
        recommended_actions=actions or ["Isolate web-01 from the network"],
        severity_assessment=severity,
    )


def make_position(
    position: Position,
    *,
    supporting: list[str] | None = None,
    opposing: list[str] | None = None,
    conditions: list[str] | None = None,
    confidence: float = 0.8,
    incident_id: str = INCIDENT,
    round_: int = 1,
    reasoning: str = "Evidence supports isolating the compromised host.",
) -> DebatePosition:
    return DebatePosition(
        agent_id="forensics-agent",
        incident_id=incident_id,
        round=round_,
        position=position,
        supporting_evidence_ids=supporting or [],
        opposing_evidence_ids=opposing or [],
        reasoning=reasoning,
        confidence=confidence,
        conditions_to_change_position=conditions
        or ["Evidence of data exfiltration to an external IP would change this position"],
    )


def make_message(
    message_type: CouncilMessageType,
    payload: dict[str, Any],
    *,
    sender: str = "containment-agent",
    message_id: str = "msg-chall-1",
    round_: int = 1,
    incident_id: str = INCIDENT,
) -> CouncilMessage:
    return CouncilMessage(
        message_id=message_id,
        incident_id=incident_id,
        round=round_,
        sender=sender,
        recipients=["forensics-agent"],
        message_type=message_type,
        timestamp=utc_now(),
        payload=payload,
    )


class ScriptedBackend(MockInferenceBackend):
    """Mock backend that replays a scripted sequence of structured payloads.

    Payloads are consumed in order (regardless of response model). An
    exhausted script raises ``InferenceBackendError``, simulating a weak
    model. An ``Exception`` instance in the script is raised instead.
    """

    def __init__(self, script: list[Any], **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.script = list(script)
        self.seen_prompts: list[str] = []

    def generate_structured(self, request: Any, response_model: type) -> Any:
        self.calls.append("generate_structured")
        self.seen_prompts.append(request.messages[-1].content)
        if not self.script:
            raise InferenceBackendError("script exhausted")
        payload = self.script.pop(0)
        if isinstance(payload, Exception):
            raise payload
        return response_model.model_validate(payload)
