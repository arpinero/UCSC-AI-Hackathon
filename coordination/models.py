"""Data model and validation rules for the CODING-AGENT coordination bus.

Stdlib only. These are DEVELOPMENT coordination messages, entirely separate
from the runtime council messages in `contracts.messages` (AGNTCY runtime).
"""

from __future__ import annotations

import json
import re
import sqlite3
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any

SCHEMA_VERSION = "1.0"
MAX_BODY_CHARS = 20_000
MAX_SUBJECT_CHARS = 200

AGENT_ROLES: dict[str, str] = {
    "model-engineer": "Model inference",
    "tools-engineer": "Forensic tools",
    "agntcy-engineer": "Runtime agent messaging",
    "reasoning-engineer": "Investigation and debate",
    "evaluation-engineer": "Simulation and evaluation",
    "integration-qa": "Integration and QA",
    "coordinator": "Shared contract approvals and coordination",
}
COORDINATOR = "coordinator"


class MessageType(str, Enum):
    PROGRESS = "PROGRESS"
    REQUEST = "REQUEST"
    RESPONSE = "RESPONSE"
    BLOCKER = "BLOCKER"
    CONTRACT_CHANGE_REQUEST = "CONTRACT_CHANGE_REQUEST"
    CONTRACT_CHANGE_DECISION = "CONTRACT_CHANGE_DECISION"
    READY_FOR_INTEGRATION = "READY_FOR_INTEGRATION"
    TEST_FAILURE = "TEST_FAILURE"
    BROADCAST = "BROADCAST"
    HEARTBEAT = "HEARTBEAT"


class Priority(str, Enum):
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    URGENT = "URGENT"


class Status(str, Enum):
    PENDING = "PENDING"
    READ = "READ"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RESOLVED = "RESOLVED"


# Structured JSON bodies required for these types (coordination rules 2, 4, 5).
REQUIRED_BODY_KEYS: dict[MessageType, tuple[str, ...]] = {
    MessageType.BLOCKER: (
        "component",
        "reproduction",
        "affected_workstream",
        "suggested_fix",
        "can_continue",
    ),
    MessageType.READY_FOR_INTEGRATION: (
        "implemented_features",
        "test_commands",
        "test_results",
        "known_limitations",
    ),
    MessageType.CONTRACT_CHANGE_REQUEST: ("contract", "proposed_change", "rationale"),
    MessageType.CONTRACT_CHANGE_DECISION: ("decision", "rationale"),
}


class CoordinationError(Exception):
    """Base class; `exit_code` is used by the CLI."""

    exit_code = 1


class CoordValidationError(CoordinationError):
    exit_code = 2


class DatabaseUnavailable(CoordinationError):
    exit_code = 3


class NotFoundError(CoordinationError):
    exit_code = 4


class PermissionDenied(CoordinationError):
    exit_code = 5


class IdempotencyConflict(CoordinationError):
    exit_code = 6


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_message_id() -> str:
    return str(uuid.uuid4())


@dataclass(frozen=True)
class Message:
    message_id: str
    schema_version: str
    sender: str
    recipient: str
    message_type: str
    priority: str
    subject: str
    body: str
    created_at: str
    correlation_id: str
    related_branch: str | None
    related_commit: str | None
    status: str
    acknowledged_at: str | None
    read_at: str | None = None
    resolved_at: str | None = None
    seq: int | None = None

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> Message:
        return cls(**{k: row[k] for k in row.keys()})

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def body_json(self) -> dict[str, Any] | None:
        try:
            parsed = json.loads(self.body)
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, dict) else None


_SECRET_PATTERNS = [
    re.compile(r"(?i)\b(api[_-]?key|secret|password|passwd|token)\b\s*[=:]\s*\S{8,}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\bhf_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b"),
]
_BRANCH_RE = re.compile(r"^[A-Za-z0-9._/-]{1,100}$")
_COMMIT_RE = re.compile(r"^[0-9a-fA-F]{7,40}$")

def check_agent(agent_id: str, what: str = "agent") -> str:
    if agent_id not in AGENT_ROLES:
        raise CoordValidationError(
            f"unknown {what} '{agent_id}'; valid identities: {', '.join(sorted(AGENT_ROLES))}"
        )
    return agent_id


def parse_enum(enum_cls: type[Enum], value: str, what: str) -> Any:
    try:
        return enum_cls(value.upper() if isinstance(value, str) else value)
    except ValueError:
        valid = ", ".join(m.value for m in enum_cls)
        raise CoordValidationError(f"invalid {what} '{value}'; valid: {valid}") from None


def _check_structured_body(message_type: MessageType, body: str) -> None:
    required = REQUIRED_BODY_KEYS.get(message_type)
    if not required:
        return
    try:
        parsed = json.loads(body)
    except json.JSONDecodeError:
        raise CoordValidationError(
            f"{message_type.value} requires a JSON object body with keys: {', '.join(required)}"
        ) from None
    if not isinstance(parsed, dict):
        raise CoordValidationError(f"{message_type.value} body must be a JSON object")
    missing = [k for k in required if k not in parsed]
    if missing:
        raise CoordValidationError(
            f"{message_type.value} body missing required keys: {', '.join(missing)}"
        )
    if message_type is MessageType.CONTRACT_CHANGE_DECISION:
        decision = str(parsed["decision"]).upper()
        if decision not in ("APPROVED", "REJECTED"):
            raise CoordValidationError("decision must be APPROVED or REJECTED")
        if decision == "APPROVED" and not parsed.get("contract_version"):
            raise CoordValidationError("APPROVED decisions must include contract_version")


def validate_content(
    message_type: MessageType,
    subject: str,
    body: str,
    related_branch: str | None,
    related_commit: str | None,
) -> None:
    """Validate subject/body/branch/commit and structured-body requirements."""
    if not subject or not subject.strip():
        raise CoordValidationError("subject must not be empty")
    if len(subject) > MAX_SUBJECT_CHARS:
        raise CoordValidationError(f"subject exceeds {MAX_SUBJECT_CHARS} characters")
    if body is None or not body.strip():
        raise CoordValidationError("body must not be empty")
    if len(body) > MAX_BODY_CHARS:
        raise CoordValidationError(
            f"body exceeds {MAX_BODY_CHARS} characters; reference a file path or commit instead"
        )
    for pattern in _SECRET_PATTERNS:
        if pattern.search(subject) or pattern.search(body):
            raise CoordValidationError(
                "message looks like it contains a secret/credential; refusing to store it"
            )
    if related_branch is not None and not _BRANCH_RE.match(related_branch):
        raise CoordValidationError(f"invalid related_branch '{related_branch}'")
    if related_commit is not None and not _COMMIT_RE.match(related_commit):
        raise CoordValidationError(f"invalid related_commit '{related_commit}' (need 7-40 hex)")
    _check_structured_body(message_type, body)
    if message_type is MessageType.READY_FOR_INTEGRATION and not (
        related_branch and related_commit
    ):
        raise CoordValidationError("READY_FOR_INTEGRATION requires --branch and --commit")
