"""Unit tests: envelope validation and correlation threading."""

from __future__ import annotations

import json

import pytest

from contracts.messages import CouncilMessage, CouncilMessageType
from forensics.messaging.envelopes import (
    InvalidEnvelopeError,
    build_message,
    build_reply,
    validate_envelope,
)


def valid_envelope_dict():
    return {
        "message_id": "cm-1",
        "incident_id": "INC-1",
        "round": 0,
        "sender": "forensics",
        "recipients": ["coordinator"],
        "message_type": "FINDING",
        "timestamp": "2026-10-10T00:00:00+00:00",
        "payload": {"finding": "synthetic"},
    }


def test_valid_dict_validates():
    message = validate_envelope(valid_envelope_dict())
    assert isinstance(message, CouncilMessage)
    assert message.message_type == CouncilMessageType.FINDING


def test_json_and_bytes_input_validate():
    as_json = json.dumps(valid_envelope_dict())
    assert validate_envelope(as_json).message_id == "cm-1"
    assert validate_envelope(as_json.encode("utf-8")).message_id == "cm-1"


def test_model_instance_revalidates():
    message = build_message(
        incident_id="INC-1",
        message_type="FINDING",
        sender="forensics",
        recipients=["coordinator"],
    )
    again = validate_envelope(message)
    assert again.message_id == message.message_id


def test_malformed_json_rejected():
    with pytest.raises(InvalidEnvelopeError, match="not valid JSON"):
        validate_envelope("{not json")


def test_non_dict_json_rejected():
    with pytest.raises(InvalidEnvelopeError, match="expected a CouncilMessage"):
        validate_envelope("[1, 2, 3]")


@pytest.mark.parametrize(
    ("mutation", "fragment"),
    [
        ({"message_id": ""}, "message_id"),
        ({"incident_id": ""}, "incident_id"),
        ({"round": -1}, "round"),
        ({"recipients": []}, "recipients"),
        ({"recipients": [""]}, "recipients"),
        ({"message_type": "NOT_A_TYPE"}, "message_type"),
        ({"timestamp": "2026-10-10T00:00:00"}, "timestamp"),
        ({"sender": "   "}, "sender"),
        ({"payload": "not-a-dict"}, "payload"),
        ({"extra_field": 1}, "extra_field"),
    ],
)
def test_invalid_envelopes_rejected_with_clear_errors(mutation, fragment):
    envelope = valid_envelope_dict() | mutation
    with pytest.raises(InvalidEnvelopeError) as excinfo:
        validate_envelope(envelope)
    assert fragment in str(excinfo.value)


def test_build_message_defaults():
    message = build_message(
        incident_id="INC-1",
        message_type="FINDING",
        sender="forensics",
        recipients=["coordinator"],
    )
    assert message.round == 0
    # Origins self-correlate: thread id == message id.
    assert message.correlation_id == message.message_id
    assert message.payload == {}
    assert message.message_id.startswith("cm-")
    assert message.timestamp.tzinfo is not None


def test_reply_threads_correlation_to_thread_root():
    alert = build_message(
        incident_id="INC-1",
        message_type="INCIDENT_ALERT",
        sender="monitor",
        recipients=["forensics"],
    )
    request = build_reply(alert, message_type="EVIDENCE_REQUEST", sender="forensics")
    assert request.correlation_id == alert.message_id
    response = build_reply(request, message_type="EVIDENCE_RESPONSE", sender="monitor")
    # The thread root is preserved across the whole chain.
    assert response.correlation_id == alert.message_id
    assert response.recipients == ["forensics"]
    assert response.round == alert.round


def test_reply_can_override_recipients_and_round():
    alert = build_message(
        incident_id="INC-1",
        message_type="INCIDENT_ALERT",
        sender="monitor",
        recipients=["forensics"],
    )
    reply = build_reply(
        alert,
        message_type="ESCALATION",
        sender="forensics",
        recipients=["commander", "compliance"],
        round=3,
    )
    assert reply.recipients == ["commander", "compliance"]
    assert reply.round == 3
    assert reply.correlation_id == alert.message_id
