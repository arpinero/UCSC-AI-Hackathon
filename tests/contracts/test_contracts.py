"""Contract validation: valid payloads accepted, invalid payloads rejected."""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from contracts import CONTRACTS_VERSION
from contracts.common import json_schema_export
from contracts.evidence import Evidence
from contracts.incident import Incident
from contracts.investigation import (
    DebatePosition,
    InvestigationFindings,
    InvestigationRequest,
    PositionRevision,
)
from contracts.messages import CouncilMessage, CouncilMessageType
from contracts.tools import ToolInvocation
from tests.contracts.payloads import (
    council_message_payload,
    evidence_payload,
    findings_payload,
    incident_payload,
    position_payload,
    request_payload,
    tool_invocation_payload,
)


def test_version_present():
    assert CONTRACTS_VERSION == "1.0.0"


def test_incident_valid_and_roundtrip():
    inc = Incident.model_validate(incident_payload())
    assert inc.created_at.tzinfo is not None
    assert Incident.model_validate_json(inc.model_dump_json()) == inc


def test_incident_rejects_naive_timestamp():
    p = incident_payload()
    p["created_at"] = "2026-10-10T12:00:00"
    with pytest.raises(ValidationError):
        Incident.model_validate(p)


def test_incident_rejects_bad_severity_and_extra_fields():
    with pytest.raises(ValidationError):
        Incident.model_validate(dict(incident_payload(), severity="SUPER"))
    with pytest.raises(ValidationError):
        Incident.model_validate(dict(incident_payload(), unexpected=1))


def test_incident_normalizes_to_utc():
    p = incident_payload()
    p["created_at"] = "2026-10-10T05:00:00-07:00"
    inc = Incident.model_validate(p)
    assert inc.created_at == datetime(2026, 10, 10, 12, 0, tzinfo=timezone.utc)
    assert inc.created_at.utcoffset().total_seconds() == 0


def test_evidence_valid_and_missing_provenance_rejected():
    assert Evidence.model_validate(evidence_payload()).evidence_id == "EV-0001"
    p = evidence_payload()
    del p["source"]
    with pytest.raises(ValidationError):
        Evidence.model_validate(p)
    with pytest.raises(ValidationError):
        Evidence.model_validate(dict(evidence_payload(), evidence_id=""))


def test_investigation_request_round_non_negative():
    assert InvestigationRequest.model_validate(request_payload()).round == 0
    with pytest.raises(ValidationError):
        InvestigationRequest.model_validate(dict(request_payload(), round=-1))


def test_findings_valid_and_confidence_bounds():
    assert InvestigationFindings.model_validate(findings_payload()).confidence == 0.85
    for bad in (-0.1, 1.1):
        with pytest.raises(ValidationError):
            InvestigationFindings.model_validate(dict(findings_payload(), confidence=bad))


def test_council_message_types_and_validation():
    assert {t.value for t in CouncilMessageType} == {
        "INCIDENT_ALERT",
        "EVIDENCE_REQUEST",
        "EVIDENCE_RESPONSE",
        "FINDING",
        "PROPOSAL",
        "CHALLENGE",
        "REVISION",
        "VOTE",
        "ESCALATION",
    }
    p = council_message_payload()
    assert CouncilMessage.model_validate(p).message_type is CouncilMessageType.FINDING
    with pytest.raises(ValidationError):
        CouncilMessage.model_validate(dict(p, message_type="GOSSIP"))
    with pytest.raises(ValidationError):
        CouncilMessage.model_validate(dict(p, recipients=[]))
    with pytest.raises(ValidationError):
        CouncilMessage.model_validate(dict(p, round=-1))


def test_debate_position_and_revision():
    pos = DebatePosition.model_validate(position_payload())
    new = DebatePosition.model_validate(dict(position_payload(), position="OPPOSE", round=2))
    rev = PositionRevision(
        agent_id="forensics-agent",
        incident_id="INC-001",
        round=2,
        previous_position=pos,
        new_position=new,
        triggering_evidence_ids=["EV-0002"],
        explanation="Backup schedule evidence contradicts exfiltration",
    )
    assert rev.previous_position.position.value == "SUPPORT"
    assert rev.new_position.position.value == "OPPOSE"
    with pytest.raises(ValidationError):
        DebatePosition.model_validate(dict(position_payload(), position="MAYBE"))
    with pytest.raises(ValidationError):
        DebatePosition.model_validate(dict(position_payload(), confidence=2))


def test_tool_invocation_duration_non_negative():
    assert ToolInvocation.model_validate(tool_invocation_payload()).duration_ms == 12
    with pytest.raises(ValidationError):
        ToolInvocation.model_validate(dict(tool_invocation_payload(), duration_ms=-1))


def test_json_schema_export_serializable():
    schemas = json_schema_export(
        [
            Incident,
            Evidence,
            InvestigationRequest,
            InvestigationFindings,
            CouncilMessage,
            DebatePosition,
            PositionRevision,
            ToolInvocation,
        ]
    )
    assert len(schemas) == 8
    json.dumps(schemas)
