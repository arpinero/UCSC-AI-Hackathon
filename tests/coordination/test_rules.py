"""Protocol rules: structured bodies, contract-change governance, secrets."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from coordination.database import connect, resolve_db_path
from coordination.models import CoordValidationError, DatabaseUnavailable, PermissionDenied
from coordination.service import CoordinationService

CCR_BODY = json.dumps(
    {
        "contract": "contracts/tools.py",
        "proposed_change": "add optional field `limit` to BuildTimelineArgs",
        "rationale": "timelines can be very long",
    }
)


def _ccr(svc: CoordinationService) -> object:
    return svc.send(
        sender="tools-engineer",
        recipient="coordinator",
        message_type="CONTRACT_CHANGE_REQUEST",
        subject="amend BuildTimelineArgs",
        body=CCR_BODY,
    )[0]


def test_contract_change_request_must_go_to_coordinator(svc: CoordinationService):
    with pytest.raises(CoordValidationError):
        svc.send(
            sender="tools-engineer",
            recipient="reasoning-engineer",
            message_type="CONTRACT_CHANGE_REQUEST",
            subject="x",
            body=CCR_BODY,
        )


def test_decision_only_by_coordinator_and_only_answering_a_request(svc: CoordinationService):
    req = _ccr(svc)
    decision = json.dumps(
        {"decision": "APPROVED", "rationale": "ok", "contract_version": "1.1.0"}
    )
    with pytest.raises(PermissionDenied):
        svc.send(
            sender="reasoning-engineer",
            recipient="tools-engineer",
            message_type="CONTRACT_CHANGE_DECISION",
            subject="approved?",
            body=decision,
            correlation_id=req.correlation_id,
        )
    with pytest.raises(CoordValidationError):  # no request with this correlation id
        svc.send(
            sender="coordinator",
            recipient="tools-engineer",
            message_type="CONTRACT_CHANGE_DECISION",
            subject="d",
            body=decision,
            correlation_id="no-such-request",
        )
    msg, _ = svc.reply(
        to_message_id=req.message_id,
        sender="coordinator",
        message_type="CONTRACT_CHANGE_DECISION",
        body=decision,
    )
    assert msg.recipient == "tools-engineer" and msg.correlation_id == req.correlation_id


def test_decision_must_be_valid_and_carry_version(svc: CoordinationService):
    req = _ccr(svc)
    no_version = json.dumps({"decision": "APPROVED", "rationale": "ok"})
    with pytest.raises(CoordValidationError):
        svc.reply(
            to_message_id=req.message_id,
            sender="coordinator",
            message_type="CONTRACT_CHANGE_DECISION",
            body=no_version,
        )
    bad = json.dumps({"decision": "MAYBE", "rationale": "ok"})
    with pytest.raises(CoordValidationError):
        svc.reply(
            to_message_id=req.message_id,
            sender="coordinator",
            message_type="CONTRACT_CHANGE_DECISION",
            body=bad,
        )


def test_blocker_requires_structured_body(svc: CoordinationService):
    with pytest.raises(CoordValidationError):
        svc.send(
            sender="agntcy-engineer",
            recipient="coordinator",
            message_type="BLOCKER",
            subject="SLIM",
            body="it does not work",
        )
    body = json.dumps(
        {
            "component": "slim-bindings",
            "reproduction": "pip install slim-bindings",
            "affected_workstream": "feat/agntcy",
            "suggested_fix": "build from source",
            "can_continue": True,
        }
    )
    msg, _ = svc.send(
        sender="agntcy-engineer",
        recipient="coordinator",
        message_type="BLOCKER",
        subject="SLIM install",
        body=body,
    )
    parsed = msg.body_json()
    assert parsed is not None and parsed["can_continue"] is True


def test_ready_for_integration_requires_branch_commit_and_fields(svc: CoordinationService):
    body = json.dumps(
        {
            "implemented_features": ["search_logs"],
            "test_commands": ["pytest tests/unit"],
            "test_results": "12 passed",
            "known_limitations": [],
        }
    )
    kwargs = dict(
        sender="tools-engineer",
        recipient="integration-qa",
        message_type="READY_FOR_INTEGRATION",
        subject="tools ready",
        body=body,
    )
    with pytest.raises(CoordValidationError):  # no branch/commit
        svc.send(**kwargs)
    with pytest.raises(CoordValidationError):  # malformed commit sha
        svc.send(**kwargs, related_branch="feat/forensic-tools", related_commit="zzz")
    msg, _ = svc.send(**kwargs, related_branch="feat/forensic-tools", related_commit="abc1234")
    assert msg.related_commit == "abc1234"


def test_secrets_and_oversized_bodies_rejected(svc: CoordinationService):
    base = dict(
        sender="tools-engineer", recipient="integration-qa", message_type="PROGRESS", subject="s"
    )
    for secret in ("password=hunter2hunter2", "hf_" + "a" * 30, "-----BEGIN PRIVATE KEY-----"):
        with pytest.raises(CoordValidationError):
            svc.send(**base, body=f"config: {secret}")
    with pytest.raises(CoordValidationError):
        svc.send(**base, body="x" * 20_001)
    with pytest.raises(CoordValidationError):
        svc.send(**base, body="   ")
    assert svc.history() == []


def test_missing_database_and_bad_path_errors(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("FORENSICS_COORD_DB", raising=False)
    with pytest.raises(DatabaseUnavailable):
        resolve_db_path(None)
    with pytest.raises(DatabaseUnavailable):
        resolve_db_path("relative/path.db")
    with pytest.raises(DatabaseUnavailable):
        connect(tmp_path / "missing.db")
    with pytest.raises(DatabaseUnavailable):
        CoordinationService(tmp_path / "missing.db").inbox("integration-qa")


def test_corrupt_database_reports_unavailable(tmp_path: Path):
    bad = tmp_path / "corrupt.db"
    bad.write_bytes(b"this is not a sqlite database" * 100)
    with pytest.raises(DatabaseUnavailable):
        CoordinationService(bad).status()
