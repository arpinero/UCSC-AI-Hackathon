"""Business logic for the coding-agent coordination bus (stdlib only).

Identity note: agent identities are SELF-DECLARED (`--sender`, `--agent`).
The bus validates they are registered identities and enforces role rules,
but it cannot authenticate which process is speaking. It is a coordination
record, not a security boundary.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from coordination.database import connect, write_transaction
from coordination.models import (
    AGENT_ROLES,
    COORDINATOR,
    SCHEMA_VERSION,
    CoordinationError,
    CoordValidationError,
    IdempotencyConflict,
    Message,
    MessageType,
    NotFoundError,
    PermissionDenied,
    Priority,
    Status,
    check_agent,
    new_message_id,
    parse_enum,
    utc_now_iso,
    validate_content,
)

_COMPARE_FIELDS = (
    "sender",
    "recipient",
    "message_type",
    "priority",
    "subject",
    "body",
    "related_branch",
    "related_commit",
)


class CoordinationService:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path

    def _conn(self) -> sqlite3.Connection:
        return connect(self.db_path)

    # ---- helpers ---------------------------------------------------------

    @staticmethod
    def _get(conn: sqlite3.Connection, message_id: str) -> Message:
        row = conn.execute("SELECT * FROM messages WHERE message_id = ?", (message_id,)).fetchone()
        if row is None:
            raise NotFoundError(f"message '{message_id}' not found")
        return Message.from_row(row)

    def _enforce_role_rules(
        self, conn: sqlite3.Connection, sender: str, recipient: str,
        mtype: MessageType, correlation_id: str | None,
    ) -> None:
        if mtype is MessageType.CONTRACT_CHANGE_DECISION:
            if sender != COORDINATOR:
                raise PermissionDenied("only 'coordinator' may send CONTRACT_CHANGE_DECISION")
            row = conn.execute(
                "SELECT 1 FROM messages WHERE correlation_id = ? "
                "AND message_type = 'CONTRACT_CHANGE_REQUEST'",
                (correlation_id,),
            ).fetchone()
            if correlation_id is None or row is None:
                raise CoordValidationError(
                    "CONTRACT_CHANGE_DECISION must answer an existing CONTRACT_CHANGE_REQUEST "
                    "(use `reply` or pass its --correlation-id)"
                )
        if mtype is MessageType.CONTRACT_CHANGE_REQUEST and recipient != COORDINATOR:
            raise CoordValidationError("CONTRACT_CHANGE_REQUEST must be addressed to 'coordinator'")
        if mtype is MessageType.HEARTBEAT and sender != recipient and recipient != COORDINATOR:
            raise CoordValidationError("HEARTBEAT is sent to 'coordinator'")

    def _insert(
        self, conn: sqlite3.Connection, *, message_id: str, sender: str, recipient: str,
        mtype: MessageType, priority: Priority, subject: str, body: str,
        correlation_id: str | None, branch: str | None, commit: str | None,
    ) -> tuple[Message, bool]:
        """Insert inside an open write transaction; returns (message, created)."""
        existing = conn.execute(
            "SELECT * FROM messages WHERE message_id = ?", (message_id,)
        ).fetchone()
        candidate = {
            "sender": sender, "recipient": recipient, "message_type": mtype.value,
            "priority": priority.value, "subject": subject, "body": body,
            "related_branch": branch, "related_commit": commit,
        }
        if existing is not None:
            same = all(existing[k] == candidate[k] for k in _COMPARE_FIELDS)
            if correlation_id is not None and existing["correlation_id"] != correlation_id:
                same = False
            if not same:
                raise IdempotencyConflict(
                    f"message_id '{message_id}' already exists with different content"
                )
            return Message.from_row(existing), False

        self._enforce_role_rules(conn, sender, recipient, mtype, correlation_id)
        corr = correlation_id or message_id
        conn.execute(
            "INSERT INTO messages(message_id, schema_version, sender, recipient, message_type,"
            " priority, subject, body, created_at, correlation_id, related_branch,"
            " related_commit, status) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (message_id, SCHEMA_VERSION, sender, recipient, mtype.value, priority.value,
             subject, body, utc_now_iso(), corr, branch, commit, Status.PENDING.value),
        )
        return self._get(conn, message_id), True

    # ---- registration ------------------------------------------------------

    def register(self, agent_id: str, role: str | None = None) -> dict[str, Any]:
        check_agent(agent_id)
        conn = self._conn()
        try:
            with write_transaction(conn):
                conn.execute(
                    "INSERT INTO agents(agent_id, role, registered_at) VALUES (?,?,?) "
                    "ON CONFLICT(agent_id) DO UPDATE SET role = excluded.role",
                    (agent_id, role or AGENT_ROLES[agent_id], utc_now_iso()),
                )
            row = conn.execute("SELECT * FROM agents WHERE agent_id = ?", (agent_id,)).fetchone()
            return dict(row)
        finally:
            conn.close()

    # ---- sending -----------------------------------------------------------

    def send(
        self,
        *,
        sender: str,
        recipient: str,
        message_type: str,
        subject: str,
        body: str,
        priority: str = "NORMAL",
        correlation_id: str | None = None,
        related_branch: str | None = None,
        related_commit: str | None = None,
        message_id: str | None = None,
    ) -> tuple[Message, bool]:
        """Send one message. Returns (message, created); created=False on idempotent retry."""
        check_agent(sender, "sender")
        check_agent(recipient, "recipient")
        mtype = parse_enum(MessageType, message_type, "message type")
        prio = parse_enum(Priority, priority, "priority")
        validate_content(mtype, subject, body, related_branch, related_commit)
        conn = self._conn()
        try:
            with write_transaction(conn):
                return self._insert(
                    conn, message_id=message_id or new_message_id(), sender=sender,
                    recipient=recipient, mtype=mtype, priority=prio, subject=subject,
                    body=body, correlation_id=correlation_id, branch=related_branch,
                    commit=related_commit,
                )
        finally:
            conn.close()

    def reply(
        self,
        *,
        to_message_id: str,
        sender: str,
        body: str,
        subject: str | None = None,
        message_type: str = "RESPONSE",
        priority: str = "NORMAL",
        related_branch: str | None = None,
        related_commit: str | None = None,
        message_id: str | None = None,
    ) -> tuple[Message, bool]:
        """Reply to a message: same correlation_id, addressed to the original sender."""
        check_agent(sender, "sender")
        mtype = parse_enum(MessageType, message_type, "message type")
        prio = parse_enum(Priority, priority, "priority")
        conn = self._conn()
        try:
            original = self._get(conn, to_message_id)
            if sender != original.recipient and sender != COORDINATOR:
                raise PermissionDenied(
                    f"'{sender}' cannot reply to a message addressed to '{original.recipient}'"
                )
            subj = subject or f"Re: {original.subject}"[:200]
            validate_content(mtype, subj, body, related_branch, related_commit)
            with write_transaction(conn):
                return self._insert(
                    conn, message_id=message_id or new_message_id(), sender=sender,
                    recipient=original.sender, mtype=mtype, priority=prio, subject=subj,
                    body=body, correlation_id=original.correlation_id,
                    branch=related_branch, commit=related_commit,
                )
        finally:
            conn.close()

    def broadcast(
        self,
        *,
        sender: str,
        subject: str,
        body: str,
        priority: str = "NORMAL",
        message_id: str | None = None,
    ) -> list[Message]:
        """Send a BROADCAST to every other registered agent (one row each, shared correlation)."""
        check_agent(sender, "sender")
        prio = parse_enum(Priority, priority, "priority")
        validate_content(MessageType.BROADCAST, subject, body, None, None)
        base = message_id or new_message_id()
        conn = self._conn()
        try:
            out: list[Message] = []
            with write_transaction(conn):
                for agent in sorted(AGENT_ROLES):
                    if agent == sender:
                        continue
                    msg, _ = self._insert(
                        conn, message_id=f"{base}:{agent}", sender=sender, recipient=agent,
                        mtype=MessageType.BROADCAST, priority=prio, subject=subject, body=body,
                        correlation_id=base, branch=None, commit=None,
                    )
                    out.append(msg)
            return out
        finally:
            conn.close()

    def heartbeat(self, agent_id: str, note: str = "") -> Message:
        """Record agent liveness and send a HEARTBEAT message to the coordinator."""
        check_agent(agent_id)
        text = note.strip() or "alive"
        conn = self._conn()
        try:
            with write_transaction(conn):
                conn.execute(
                    "UPDATE agents SET last_heartbeat_at = ?, last_heartbeat_note = ? "
                    "WHERE agent_id = ?",
                    (utc_now_iso(), text[:500], agent_id),
                )
                msg, _ = self._insert(
                    conn, message_id=new_message_id(), sender=agent_id, recipient=COORDINATOR,
                    mtype=MessageType.HEARTBEAT, priority=Priority.LOW,
                    subject=f"heartbeat from {agent_id}", body=text[:2000],
                    correlation_id=None, branch=None, commit=None,
                )
            return msg
        finally:
            conn.close()

    # ---- receiving / status ------------------------------------------------

    def inbox(
        self, agent_id: str, *, include_all: bool = False, limit: int = 50
    ) -> list[Message]:
        """Messages addressed to `agent_id`. Default: PENDING only (unread)."""
        check_agent(agent_id)
        sql = "SELECT * FROM messages WHERE recipient = ?"
        params: list[Any] = [agent_id]
        if not include_all:
            sql += " AND status = 'PENDING'"
        sql += " ORDER BY seq ASC LIMIT ?"
        params.append(max(1, limit))
        conn = self._conn()
        try:
            return [Message.from_row(r) for r in conn.execute(sql, params).fetchall()]
        finally:
            conn.close()

    def read(self, message_id: str, agent_id: str) -> Message:
        """Return a message; if `agent_id` is the recipient, PENDING becomes READ."""
        check_agent(agent_id)
        conn = self._conn()
        try:
            with write_transaction(conn):
                msg = self._get(conn, message_id)
                if msg.recipient == agent_id and msg.status == Status.PENDING.value:
                    conn.execute(
                        "UPDATE messages SET status = 'READ', read_at = ? "
                        "WHERE message_id = ? AND status = 'PENDING'",
                        (utc_now_iso(), message_id),
                    )
                    msg = self._get(conn, message_id)
            return msg
        finally:
            conn.close()

    def acknowledge(self, message_id: str, agent_id: str) -> Message:
        """Recipient acknowledges a message (idempotent; never regresses a RESOLVED one)."""
        check_agent(agent_id)
        conn = self._conn()
        try:
            with write_transaction(conn):
                msg = self._get(conn, message_id)
                if msg.recipient != agent_id:
                    raise PermissionDenied(
                        f"only the recipient '{msg.recipient}' may acknowledge this message"
                    )
                if msg.status in (Status.PENDING.value, Status.READ.value):
                    now = utc_now_iso()
                    conn.execute(
                        "UPDATE messages SET status = 'ACKNOWLEDGED', acknowledged_at = ?, "
                        "read_at = COALESCE(read_at, ?) WHERE message_id = ?",
                        (now, now, message_id),
                    )
                    msg = self._get(conn, message_id)
            return msg
        finally:
            conn.close()

    def resolve(self, message_id: str, agent_id: str) -> Message:
        """Mark a message RESOLVED (recipient, sender, or coordinator)."""
        check_agent(agent_id)
        conn = self._conn()
        try:
            with write_transaction(conn):
                msg = self._get(conn, message_id)
                if agent_id not in (msg.recipient, msg.sender, COORDINATOR):
                    raise PermissionDenied("only sender, recipient or coordinator may resolve")
                if msg.status != Status.RESOLVED.value:
                    now = utc_now_iso()
                    conn.execute(
                        "UPDATE messages SET status = 'RESOLVED', resolved_at = ?, "
                        "read_at = COALESCE(read_at, ?), "
                        "acknowledged_at = COALESCE(acknowledged_at, ?) WHERE message_id = ?",
                        (now, now, now, message_id),
                    )
                    msg = self._get(conn, message_id)
            return msg
        finally:
            conn.close()

    def history(
        self,
        *,
        agent_id: str | None = None,
        sender: str | None = None,
        recipient: str | None = None,
        correlation_id: str | None = None,
        message_type: str | None = None,
        after_seq: int = 0,
        limit: int = 100,
    ) -> list[Message]:
        """Query message history in send order. `agent_id` matches sender OR recipient."""
        clauses = ["seq > ?"]
        params: list[Any] = [after_seq]
        for name, value in (("sender", sender), ("recipient", recipient)):
            if value:
                check_agent(value, name)
                clauses.append(f"{name} = ?")
                params.append(value)
        if agent_id:
            check_agent(agent_id)
            clauses.append("(sender = ? OR recipient = ?)")
            params += [agent_id, agent_id]
        if correlation_id:
            clauses.append("correlation_id = ?")
            params.append(correlation_id)
        if message_type:
            clauses.append("message_type = ?")
            params.append(parse_enum(MessageType, message_type, "message type").value)
        sql = f"SELECT * FROM messages WHERE {' AND '.join(clauses)} ORDER BY seq ASC LIMIT ?"
        params.append(max(1, limit))
        conn = self._conn()
        try:
            return [Message.from_row(r) for r in conn.execute(sql, params).fetchall()]
        finally:
            conn.close()

    def status(self) -> dict[str, Any]:
        """Bus-wide summary: per-agent message counts and last heartbeat."""
        conn = self._conn()
        try:
            agents = []
            for row in conn.execute("SELECT * FROM agents ORDER BY agent_id").fetchall():
                counts = {
                    r["status"]: r["n"]
                    for r in conn.execute(
                        "SELECT status, COUNT(*) AS n FROM messages WHERE recipient = ? "
                        "GROUP BY status",
                        (row["agent_id"],),
                    ).fetchall()
                }
                agents.append(
                    {
                        "agent_id": row["agent_id"],
                        "role": row["role"],
                        "pending": counts.get("PENDING", 0),
                        "read": counts.get("READ", 0),
                        "acknowledged": counts.get("ACKNOWLEDGED", 0),
                        "resolved": counts.get("RESOLVED", 0),
                        "last_heartbeat_at": row["last_heartbeat_at"],
                        "last_heartbeat_note": row["last_heartbeat_note"],
                    }
                )
            total = conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
            journal = conn.execute("PRAGMA journal_mode").fetchone()[0]
            return {
                "db_path": str(self.db_path),
                "schema_version": SCHEMA_VERSION,
                "journal_mode": journal,
                "total_messages": total,
                "agents": agents,
            }
        finally:
            conn.close()


__all__ = ["CoordinationError", "CoordinationService"]
