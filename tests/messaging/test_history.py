"""Unit tests: debate history ordering, querying, and JSONL persistence."""

from __future__ import annotations

import json

import pytest

from forensics.messaging.envelopes import (
    InvalidEnvelopeError,
    build_message,
    build_reply,
)
from forensics.messaging.history import (
    DEFAULT_DEBATE_HISTORY_DIR,
    DebateHistory,
    default_history_path,
)

INCIDENT = "INC-HIST-1"


@pytest.fixture
def history(tmp_path):
    return DebateHistory(INCIDENT, tmp_path / f"{INCIDENT}.jsonl")


def _thread_of_three():
    alert = build_message(
        incident_id=INCIDENT,
        message_type="INCIDENT_ALERT",
        sender="monitor",
        recipients=["forensics"],
    )
    request = build_reply(
        alert,
        message_type="EVIDENCE_REQUEST",
        sender="forensics",
        payload={"query": "authentication logs"},
    )
    response = build_reply(
        request,
        message_type="EVIDENCE_RESPONSE",
        sender="monitor",
        payload={"evidence_ids": ["EV-1"]},
    )
    return alert, request, response


def test_record_persists_jsonl_in_order(history):
    alert, request, response = _thread_of_three()
    for message in (alert, request, response):
        history.record(message)
    assert history.count() == 3
    lines = history.path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 3
    assert [json.loads(line)["message_id"] for line in lines] == [
        message.message_id for message in (alert, request, response)
    ]


def test_query_by_correlation_round_type_sender_recipient(history):
    alert, request, response = _thread_of_three()
    other = build_message(
        incident_id=INCIDENT,
        message_type="FINDING",
        sender="forensics",
        recipients=["coordinator"],
        round=1,
    )
    for message in (alert, request, response, other):
        history.record(message)
    thread = history.query(correlation_id=alert.message_id)
    assert [m.message_type.value for m in thread] == [
        "INCIDENT_ALERT",
        "EVIDENCE_REQUEST",
        "EVIDENCE_RESPONSE",
    ]
    assert [m.message_id for m in history.query(round=1)] == [other.message_id]
    assert [m.message_id for m in history.query(message_type="FINDING")] == [
        other.message_id
    ]
    assert [m.message_id for m in history.query(sender="monitor")] == [
        alert.message_id,
        response.message_id,
    ]
    # build_reply defaults recipients to the original's sender.
    assert [m.message_id for m in history.query(recipient="forensics")] == [
        alert.message_id,
        response.message_id,
    ]
    assert [m.message_id for m in history.query(recipient="monitor")] == [
        request.message_id
    ]
    combined = history.query(correlation_id=alert.message_id, message_type="FINDING")
    assert combined == []


def test_rejects_wrong_incident(history):
    foreign = build_message(
        incident_id="INC-OTHER",
        message_type="FINDING",
        sender="forensics",
        recipients=["coordinator"],
    )
    with pytest.raises(InvalidEnvelopeError, match="does not match"):
        history.record(foreign)


def test_reload_and_load_roundtrip(history):
    alert, request, response = _thread_of_three()
    for message in (alert, request, response):
        history.record(message)
    reloaded = DebateHistory.load(INCIDENT, history.path)
    assert reloaded.count() == 3
    assert [m.message_id for m in reloaded.messages] == [
        m.message_id for m in (alert, request, response)
    ]
    assert reloaded.query(correlation_id=alert.message_id)


def test_reload_rejects_corrupted_line(history):
    history.record(
        build_message(
            incident_id=INCIDENT,
            message_type="FINDING",
            sender="forensics",
            recipients=["coordinator"],
        )
    )
    with history.path.open("a", encoding="utf-8") as handle:
        handle.write("not-json\n")
    with pytest.raises(InvalidEnvelopeError, match=":2:"):
        history.reload()


def test_default_history_path():
    assert default_history_path("INC-9") == DEFAULT_DEBATE_HISTORY_DIR / "INC-9.jsonl"
    assert "forensics-agent-coordination" in str(DEFAULT_DEBATE_HISTORY_DIR)
    # Path traversal safety: incident ids containing separators are sanitized.
    assert default_history_path("a/b").name == "a_b.jsonl"


def test_to_jsonl_matches_file(history):
    alert, _, _ = _thread_of_three()
    history.record(alert)
    assert history.to_jsonl() == history.path.read_text(encoding="utf-8")
