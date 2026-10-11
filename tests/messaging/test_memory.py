"""Unit tests: in-process transport delivery, isolation, and errors."""

from __future__ import annotations

import pytest

from forensics.messaging.envelopes import (
    InvalidEnvelopeError,
    MessagingError,
    NotSubscribedError,
    TransportClosedError,
    TransportTimeoutError,
    build_message,
)
from forensics.messaging.memory import InMemoryNetwork, InMemoryTransport


@pytest.fixture
def network():
    return InMemoryNetwork()


def make(incident_id="INC-1", sender="alice", recipients=("bob",)):
    return build_message(
        incident_id=incident_id,
        message_type="FINDING",
        sender=sender,
        recipients=list(recipients),
        payload={"note": "synthetic"},
    )


def test_delivery_between_transports_and_sender_copy(network):
    alice = InMemoryTransport("alice", network)
    bob = InMemoryTransport("bob", network)
    alice.subscribe("INC-1")
    bob.subscribe("INC-1")
    message = make()
    alice.send(message)

    delivered_bob = bob.receive("INC-1", timeout_s=1.0)
    assert delivered_bob.message_id == message.message_id
    assert delivered_bob.delivered_at is not None

    delivered_alice = alice.receive("INC-1", timeout_s=1.0)
    assert delivered_alice.message_id == message.message_id
    assert delivered_alice.sender == "alice"


def test_subscribe_per_incident_isolation(network):
    alpha = InMemoryTransport("alpha", network)
    beta = InMemoryTransport("beta", network)
    alpha.subscribe("INC-1")
    beta.subscribe("INC-2")
    alpha.send(make(incident_id="INC-1", sender="alpha", recipients=("beta",)))

    received = alpha.receive("INC-1", timeout_s=1.0)
    assert received.incident_id == "INC-1"

    with pytest.raises(TransportTimeoutError):
        beta.receive("INC-2", timeout_s=0.05)
    with pytest.raises(NotSubscribedError):
        beta.receive("INC-1")


def test_receive_without_subscription_rejected():
    transport = InMemoryTransport("solo")
    with pytest.raises(NotSubscribedError):
        transport.receive("INC-1")


def test_send_rejects_invalid_envelope(network):
    alice = InMemoryTransport("alice", network)
    bob = InMemoryTransport("bob", network)
    bob.subscribe("INC-1")
    with pytest.raises(InvalidEnvelopeError):
        alice.send({"message_id": "cm-bad"})
    with pytest.raises(TransportTimeoutError):
        bob.receive("INC-1", timeout_s=0.05)


def test_fifo_order_preserved(network):
    producer = InMemoryTransport("producer", network)
    consumer = InMemoryTransport("consumer", network)
    consumer.subscribe("INC-FIFO")
    sent = [make(incident_id="INC-FIFO") for _ in range(3)]
    for message in sent:
        producer.send(message)
    received_ids = [consumer.receive("INC-FIFO", timeout_s=1.0).message_id for _ in range(3)]
    assert received_ids == [m.message_id for m in sent]


def test_close_is_idempotent_and_blocks_operations(network):
    transport = InMemoryTransport("closing", network)
    transport.subscribe("INC-1")
    transport.close()
    transport.close()  # idempotent
    with pytest.raises(TransportClosedError):
        transport.send(make(sender="closing", recipients=("x",)))
    with pytest.raises(TransportClosedError):
        transport.receive("INC-1")
    with pytest.raises(TransportClosedError):
        transport.subscribe("INC-2")


def test_duplicate_agent_id_rejected(network):
    InMemoryTransport("dup", network)
    with pytest.raises(MessagingError, match="duplicate agent id"):
        InMemoryTransport("dup", network)


def test_unsubscribed_transport_declines_offer(network):
    quiet = InMemoryTransport("quiet", network)
    assert quiet.is_subscribed("INC-1") is False
    assert quiet.offer(make(sender="someone", recipients=("quiet",))) is False
    quiet.subscribe("INC-1")
    assert quiet.offer(make(sender="someone", recipients=("quiet",))) is True
