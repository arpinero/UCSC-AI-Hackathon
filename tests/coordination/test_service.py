"""Service-level tests: registration, send/receive, replies, acks, history."""

from __future__ import annotations

from pathlib import Path

import pytest

from coordination.models import (
    AGENT_ROLES,
    CoordValidationError,
    IdempotencyConflict,
    NotFoundError,
    PermissionDenied,
)
from coordination.service import CoordinationService

SEVEN = {
    "model-engineer",
    "tools-engineer",
    "agntcy-engineer",
    "reasoning-engineer",
    "evaluation-engineer",
    "integration-qa",
    "coordinator",
}


def _send(svc: CoordinationService, **over):
    kwargs = dict(
        sender="tools-engineer",
        recipient="integration-qa",
        message_type="PROGRESS",
        subject="s",
        body="b",
    )
    kwargs.update(over)
    return svc.send(**kwargs)


def test_seven_identities_registered(svc: CoordinationService):
    assert set(AGENT_ROLES) == SEVEN
    assert {a["agent_id"] for a in svc.status()["agents"]} == SEVEN


def test_register_is_idempotent_and_rejects_unknown(svc: CoordinationService):
    first = svc.register("tools-engineer")
    again = svc.register("tools-engineer", role="Forensic tools (updated)")
    assert first["agent_id"] == again["agent_id"]
    assert again["role"] == "Forensic tools (updated)"
    with pytest.raises(CoordValidationError):
        svc.register("rogue-agent")


def test_send_inbox_read_ack_resolve_transitions(svc: CoordinationService):
    msg, created = _send(
        svc, recipient="reasoning-engineer", message_type="REQUEST", subject="need schema"
    )
    assert created and msg.status == "PENDING" and msg.schema_version == "1.0"
    assert msg.correlation_id == msg.message_id  # a new thread starts at itself
    assert [m.message_id for m in svc.inbox("reasoning-engineer")] == [msg.message_id]
    assert svc.inbox("tools-engineer") == []

    read = svc.read(msg.message_id, "reasoning-engineer")
    assert read.status == "READ" and read.read_at
    assert svc.inbox("reasoning-engineer") == []  # no longer unread
    assert len(svc.inbox("reasoning-engineer", include_all=True)) == 1

    ack = svc.acknowledge(msg.message_id, "reasoning-engineer")
    assert ack.status == "ACKNOWLEDGED" and ack.acknowledged_at
    again = svc.acknowledge(msg.message_id, "reasoning-engineer")
    assert again.acknowledged_at == ack.acknowledged_at  # idempotent

    assert svc.resolve(msg.message_id, "tools-engineer").status == "RESOLVED"
    # acknowledging a resolved message must not regress its status
    assert svc.acknowledge(msg.message_id, "reasoning-engineer").status == "RESOLVED"


def test_sender_reading_does_not_change_status(svc: CoordinationService):
    msg, _ = _send(svc)
    assert svc.read(msg.message_id, "tools-engineer").status == "PENDING"


def test_only_recipient_may_acknowledge(svc: CoordinationService):
    msg, _ = _send(svc)
    with pytest.raises(PermissionDenied):
        svc.acknowledge(msg.message_id, "tools-engineer")
    with pytest.raises(NotFoundError):
        svc.acknowledge("does-not-exist", "integration-qa")


def test_reply_keeps_correlation_and_addresses_original_sender(svc: CoordinationService):
    req, _ = _send(svc, recipient="reasoning-engineer", message_type="REQUEST", body="question")
    resp, _ = svc.reply(to_message_id=req.message_id, sender="reasoning-engineer", body="answer")
    assert resp.message_type == "RESPONSE"
    assert resp.recipient == "tools-engineer" and resp.sender == "reasoning-engineer"
    assert resp.correlation_id == req.correlation_id
    assert resp.subject.startswith("Re:")
    thread = svc.history(correlation_id=req.correlation_id)
    assert [m.message_id for m in thread] == [req.message_id, resp.message_id]
    with pytest.raises(PermissionDenied):
        svc.reply(to_message_id=req.message_id, sender="model-engineer", body="butting in")


def test_broadcast_reaches_everyone_else(svc: CoordinationService):
    msgs = svc.broadcast(sender="coordinator", subject="freeze", body="Contracts frozen at v1.")
    assert len(msgs) == 6
    assert {m.recipient for m in msgs} == SEVEN - {"coordinator"}
    assert len({m.correlation_id for m in msgs}) == 1
    for agent in SEVEN - {"coordinator"}:
        assert len(svc.inbox(agent)) == 1
    assert svc.inbox("coordinator") == []


def test_history_filters_and_order(svc: CoordinationService):
    for i in range(3):
        _send(svc, subject=f"p{i}")
    _send(svc, sender="model-engineer", subject="m")
    all_msgs = svc.history()
    seqs = [m.seq for m in all_msgs]
    assert seqs == sorted(seqs)
    assert len(svc.history(sender="tools-engineer")) == 3
    assert len(svc.history(agent_id="integration-qa")) == 4
    assert len(svc.history(message_type="PROGRESS", limit=2)) == 2
    assert len(svc.history(after_seq=seqs[0] or 0)) == 3


def test_messages_persist_across_service_instances(db_path: Path):
    _send(CoordinationService(db_path), subject="persist")
    fresh = CoordinationService(db_path)
    assert [m.subject for m in fresh.inbox("integration-qa")] == ["persist"]


def test_duplicate_message_id_is_idempotent(svc: CoordinationService):
    first, created1 = _send(svc, message_id="fixed-id-1")
    second, created2 = _send(svc, message_id="fixed-id-1")
    assert created1 is True and created2 is False
    assert first.message_id == second.message_id and len(svc.history()) == 1
    with pytest.raises(IdempotencyConflict):
        _send(svc, message_id="fixed-id-1", body="different body")
    assert len(svc.history()) == 1


def test_invalid_sender_recipient_type_priority(svc: CoordinationService):
    with pytest.raises(CoordValidationError):
        _send(svc, sender="nobody")
    with pytest.raises(CoordValidationError):
        _send(svc, recipient="nobody")
    with pytest.raises(CoordValidationError):
        _send(svc, message_type="GOSSIP")
    with pytest.raises(CoordValidationError):
        _send(svc, priority="PANIC")
    assert svc.history() == []
