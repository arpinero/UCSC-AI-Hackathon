"""All 9 CouncilMessage types: structured payload fixtures validate.

Each type gets a realistic structured payload (see
tests/integration/scenario.py) and must validate against the frozen
CouncilMessage contract, round-trip through JSON, and keep optional
envelope fields optional.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from contracts.messages import CouncilMessage, CouncilMessageType
from tests.integration.scenario import council_payload, make_council_message

ALL_TYPES = list(CouncilMessageType)


def test_exactly_nine_types():
    assert len(ALL_TYPES) == 9
    assert {t.value for t in ALL_TYPES} == {
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


@pytest.mark.parametrize("message_type", ALL_TYPES)
def test_council_message_fixture_validates_and_roundtrips(message_type):
    envelope = make_council_message(message_type, correlation_id="REQ-1")
    message = CouncilMessage.model_validate(envelope)
    assert message.message_type is message_type
    assert message.payload, "each type must carry a structured payload"
    assert CouncilMessage.model_validate_json(message.model_dump_json()) == message


@pytest.mark.parametrize("message_type", ALL_TYPES)
def test_council_payload_is_structured_and_serializable(message_type):
    payload = council_payload(message_type)
    assert isinstance(payload, dict) and payload
    assert all(isinstance(key, str) for key in payload)


def test_envelope_constraints_enforced():
    base = make_council_message(CouncilMessageType.FINDING)
    with pytest.raises(ValidationError):
        CouncilMessage.model_validate(dict(base, message_type="GOSSIP"))
    with pytest.raises(ValidationError):
        CouncilMessage.model_validate(dict(base, recipients=[]))
    with pytest.raises(ValidationError):
        CouncilMessage.model_validate(dict(base, round=-1))
    with pytest.raises(ValidationError):
        CouncilMessage.model_validate(dict(base, sender=""))
    with pytest.raises(ValidationError):
        CouncilMessage.model_validate(dict(base, incident_id=""))


def test_optional_fields_default():
    message = CouncilMessage.model_validate(make_council_message(CouncilMessageType.ESCALATION))
    assert message.correlation_id is None
    assert message.delivered_at is None
    assert message.recipients == ["containment-agent"]
