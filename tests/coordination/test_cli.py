"""CLI tests: every command exercised through real subprocess invocations."""

from __future__ import annotations

import json

from tests.coordination.conftest import run_cli


def test_init_registers_seven_identities(tmp_path):
    db = tmp_path / "coord" / "coordination.db"
    out = run_cli("init", db=db)
    assert out.returncode == 0, out.stderr
    info = json.loads(out.stdout)
    assert info["journal_mode"] == "wal"
    assert info["agents_registered"] == 7
    # re-init is idempotent
    assert run_cli("init", db=db).returncode == 0


def test_send_read_reply_ack_flow(db_path):
    out = run_cli(
        "send", "--sender", "tools-engineer", "--recipient", "reasoning-engineer",
        "--type", "REQUEST", "--subject", "need structured output",
        "--body", "Need structured output for position revisions.",
        db=db_path,
    )
    assert out.returncode == 0, out.stderr
    msg = json.loads(out.stdout)
    assert msg["created"] is True and msg["message"]["status"] == "PENDING"

    mid = msg["message"]["message_id"]
    out = run_cli("inbox", "--agent", "reasoning-engineer", db=db_path)
    assert mid in out.stdout
    out = run_cli("read", "--agent", "reasoning-engineer", "--message-id", mid, db=db_path)
    assert json.loads(out.stdout)[0]["status"] == "READ"

    out = run_cli(
        "reply", "--sender", "reasoning-engineer", "--to", mid,
        "--body", "Structured output contract added.", db=db_path,
    )
    reply = json.loads(out.stdout)["message"]
    assert reply["recipient"] == "tools-engineer"
    assert reply["correlation_id"] == msg["message"]["correlation_id"]

    out = run_cli(
        "ack", "--agent", "tools-engineer", "--message-id", reply["message_id"], db=db_path
    )
    assert json.loads(out.stdout)["status"] == "ACKNOWLEDGED"

    out = run_cli("history", "--correlation-id", msg["message"]["correlation_id"], db=db_path)
    assert len(json.loads(out.stdout)) == 2


def test_broadcast_and_status(db_path):
    out = run_cli(
        "broadcast", "--sender", "coordinator", "--subject", "freeze",
        "--body", "Contracts are frozen at v1.", db=db_path,
    )
    assert out.returncode == 0, out.stderr
    assert len(json.loads(out.stdout)) == 6
    status = json.loads(run_cli("status", db=db_path).stdout)
    pending = {a["agent_id"]: a["pending"] for a in status["agents"]}
    assert pending["coordinator"] == 0
    assert all(v == 1 for k, v in pending.items() if k != "coordinator")


def test_heartbeat(db_path):
    out = run_cli("heartbeat", "--agent", "tools-engineer", "--note", "mock tools done", db=db_path)
    assert out.returncode == 0
    status = json.loads(run_cli("status", db=db_path).stdout)
    agent = next(a for a in status["agents"] if a["agent_id"] == "tools-engineer")
    assert agent["pending"] == 0  # tools-engineer sent it; coordinator received it
    coord = next(a for a in status["agents"] if a["agent_id"] == "coordinator")
    assert coord["pending"] == 1
    assert agent["last_heartbeat_note"] == "mock tools done"


def test_watch_finds_message_and_times_out(db_path):
    run_cli(
        "send", "--sender", "model-engineer", "--recipient", "integration-qa",
        "--type", "PROGRESS", "--subject", "hi", "--body", "b", db=db_path,
    )
    out = run_cli("watch", "--agent", "integration-qa", "--timeout", "5", db=db_path)
    assert out.returncode == 0 and "hi" in out.stdout
    # watch is non-destructive (does not mark READ), so use an empty inbox for
    # the timeout case: bounded polling must exit cleanly with code 10.
    out = run_cli("watch", "--agent", "evaluation-engineer", "--timeout", "0.5", db=db_path)
    assert out.returncode == 10


def test_cli_error_cases(db_path, tmp_path):
    bad = run_cli(
        "send", "--sender", "rogue", "--recipient", "integration-qa",
        "--type", "PROGRESS", "--subject", "s", "--body", "b", db=db_path,
    )
    assert bad.returncode == 2 and "unknown sender" in bad.stderr
    bad = run_cli(
        "send", "--sender", "tools-engineer", "--recipient", "integration-qa",
        "--type", "NOPE", "--subject", "s", "--body", "b", db=db_path,
    )
    assert bad.returncode == 2
    bad = run_cli("inbox", "--agent", "tools-engineer", db=tmp_path / "missing.db")
    assert bad.returncode == 3 and "init" in bad.stderr
    bad = run_cli("send", "--sender", "tools-engineer", "--recipient", "integration-qa",
                  "--type", "PROGRESS", "--subject", "s", "--body", "b", db=None)
    assert bad.returncode == 3 and "FORENSICS_COORD_DB" in bad.stderr


def test_cli_duplicate_send_is_idempotent(db_path):
    args = (
        "send", "--sender", "tools-engineer", "--recipient", "integration-qa",
        "--type", "PROGRESS", "--subject", "s", "--body", "b", "--message-id", "idem-1",
    )
    first = run_cli(*args, db=db_path)
    second = run_cli(*args, db=db_path)
    assert json.loads(first.stdout)["created"] is True
    assert json.loads(second.stdout)["created"] is False
    history = json.loads(run_cli("history", "--limit", "10", db=db_path).stdout)
    assert len(history) == 1


def test_register_command(db_path):
    out = run_cli(
        "register", "--agent", "tools-engineer", "--role", "Forensic tools v2", db=db_path
    )
    assert out.returncode == 0
    status = json.loads(run_cli("status", db=db_path).stdout)
    agent = next(a for a in status["agents"] if a["agent_id"] == "tools-engineer")
    assert agent["role"] == "Forensic tools v2"
