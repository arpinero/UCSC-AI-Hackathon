"""Unit tests: Transport ABC contract and CouncilBus/Session behaviour."""

from __future__ import annotations

import pytest

from forensics.messaging.base import CouncilBus, Session, Transport
from forensics.messaging.envelopes import InvalidEnvelopeError, build_message
from forensics.messaging.memory import InMemoryNetwork, InMemoryTransport


def test_transport_is_abstract():
    with pytest.raises(TypeError):
        Transport()  # type: ignore[abstract]


def test_bus_sessions_are_cached_and_subscribe(tmp_path):
    transport = InMemoryTransport("forensics", InMemoryNetwork())
    bus = CouncilBus(transport, history_dir=tmp_path)
    first = bus.session("INC-1")
    assert bus.session("INC-1") is first
    assert transport.is_subscribed("INC-1")
    second = bus.session("INC-2")
    assert second is not first
    assert transport.is_subscribed("INC-2")
    bus.close()


def test_bus_history_files_under_history_dir(tmp_path):
    transport = InMemoryTransport("forensics", InMemoryNetwork())
    bus = CouncilBus(transport, history_dir=tmp_path)
    session = bus.session("INC-BUS-1")
    message = session.build(
        message_type="FINDING",
        sender="forensics",
        recipients=["coordinator"],
    )
    session.send(message)
    expected = tmp_path / "INC-BUS-1.jsonl"
    assert expected.exists()
    assert json_line_count(expected) == 1
    bus.close()


def json_line_count(path):
    return len(path.read_text(encoding="utf-8").splitlines())


def test_session_send_validates_incident_and_records_history(tmp_path):
    network = InMemoryNetwork()
    alice = InMemoryTransport("alice", network)
    bob = InMemoryTransport("bob", network)
    bus = CouncilBus(alice, history_dir=tmp_path)
    session = bus.session("INC-1")
    bob.subscribe("INC-1")

    message = session.build(
        message_type="INCIDENT_ALERT",
        sender="alice",
        recipients=["bob"],
    )
    sent = session.send(message)
    received = bob.receive("INC-1", timeout_s=1.0)
    assert received.message_id == sent.message_id
    assert [m.message_id for m in session.history.query()] == [sent.message_id]

    foreign = build_message(
        incident_id="INC-OTHER",
        message_type="FINDING",
        sender="alice",
        recipients=["bob"],
    )
    with pytest.raises(InvalidEnvelopeError, match="does not match session incident"):
        session.send(foreign)
    assert session.history.count() == 1
    bus.close()


def test_session_receive_records_history(tmp_path):
    network = InMemoryNetwork()
    alice = InMemoryTransport("alice", network)
    bob = InMemoryTransport("bob", network)
    bus = CouncilBus(alice, history_dir=tmp_path)
    session = bus.session("INC-1")
    bob.subscribe("INC-1")
    session.send(
        session.build(
            message_type="FINDING",
            sender="alice",
            recipients=["bob"],
        )
    )
    bob.receive("INC-1", timeout_s=1.0)

    incoming_bus = CouncilBus(bob, history_dir=tmp_path / "bob")
    incoming_session = incoming_bus.session("INC-1")
    # Re-deliver a copy: build a second message to receive on bob's session.
    session.send(
        session.build(
            message_type="ESCALATION",
            sender="alice",
            recipients=["bob"],
        )
    )
    received = incoming_session.receive(timeout_s=1.0)
    assert received.message_type.value == "ESCALATION"
    assert [m.message_id for m in incoming_session.history.query()] == [
        received.message_id
    ]
    bus.close()
    incoming_bus.close()


def test_session_round_tracking(tmp_path):
    transport = InMemoryTransport("forensics", InMemoryNetwork())
    bus = CouncilBus(transport, history_dir=tmp_path)
    session = bus.session("INC-1")
    assert session.round == 0
    message = session.build(
        message_type="FINDING",
        sender="forensics",
        recipients=["coordinator"],
    )
    assert message.round == 0
    assert session.advance_round() == 1
    later = session.build(
        message_type="VOTE",
        sender="forensics",
        recipients=["coordinator"],
    )
    assert later.round == 1
    bus.close()


def test_session_build_reply_threads_correlation(tmp_path):
    transport = InMemoryTransport("forensics", InMemoryNetwork())
    bus = CouncilBus(transport, history_dir=tmp_path)
    session = bus.session("INC-1")
    alert = session.build(
        message_type="INCIDENT_ALERT",
        sender="monitor",
        recipients=["forensics"],
    )
    sent = session.send(alert)
    reply = session.build_reply(
        sent,
        message_type="EVIDENCE_REQUEST",
        sender="forensics",
    )
    assert reply.correlation_id == sent.message_id
    assert reply.incident_id == "INC-1"
    bus.close()


def test_session_type_check():
    assert issubclass(InMemoryTransport, Transport)
    assert Session is not None
