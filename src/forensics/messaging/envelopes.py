"""Strict envelope validation and correlation-threaded message construction.

Every message entering or leaving ``forensics.messaging`` — on any
transport — must be a valid ``contracts.messages.CouncilMessage``. These
helpers centralize that validation with clear, actionable errors, and build
replies whose ``correlation_id`` threads them back to the message that
originated the exchange (thread == correlation ID).

Owner: agntcy-engineer (Stage B).
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any

from pydantic import ValidationError

from contracts.common import utc_now
from contracts.messages import CouncilMessage, CouncilMessageType


class MessagingError(RuntimeError):
    """Base class for all runtime messaging errors."""


class InvalidEnvelopeError(MessagingError):
    """A message failed validation against the CouncilMessage contract."""

    def __init__(self, detail: str) -> None:
        super().__init__(f"invalid council message envelope: {detail}")
        self.detail = detail


class TransportTimeoutError(MessagingError):
    """No message arrived within the configured receive timeout."""


class NotSubscribedError(MessagingError):
    """The transport has no subscription for the requested incident."""


class TransportClosedError(MessagingError):
    """The transport (or its underlying resources) has been closed."""


def validate_envelope(
    message: CouncilMessage | dict[str, Any] | str | bytes | bytearray,
) -> CouncilMessage:
    """Validate ``message`` into a ``CouncilMessage``, rejecting bad envelopes.

    Accepts an already-validated model, a mapping, or a JSON string/bytes
    payload. Raises ``InvalidEnvelopeError`` with a concise explanation on
    any contract violation: missing fields, wrong types, naive timestamps,
    unknown message types, extra fields, negative rounds, and so on.
    """
    if isinstance(message, CouncilMessage):
        return CouncilMessage.model_validate(message.model_dump())
    if isinstance(message, (bytes, bytearray)):
        try:
            message = message.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise InvalidEnvelopeError(f"envelope is not valid UTF-8: {exc}") from exc
    if isinstance(message, str):
        try:
            message = json.loads(message)
        except json.JSONDecodeError as exc:
            raise InvalidEnvelopeError(f"envelope is not valid JSON: {exc}") from exc
    if not isinstance(message, dict):
        raise InvalidEnvelopeError(
            f"expected a CouncilMessage, dict, or JSON envelope, got {type(message).__name__}"
        )
    try:
        return CouncilMessage.model_validate(message)
    except ValidationError as exc:
        problems = "; ".join(
            f"{'.'.join(str(part) for part in error['loc']) or '<root>'}: {error['msg']}"
            for error in exc.errors()
        )
        raise InvalidEnvelopeError(problems) from exc


def build_message(
    *,
    incident_id: str,
    message_type: CouncilMessageType | str,
    sender: str,
    recipients: list[str],
    payload: dict[str, Any] | None = None,
    round: int = 0,
    correlation_id: str | None = None,
    message_id: str | None = None,
    timestamp: datetime | None = None,
) -> CouncilMessage:
    """Build a validated ``CouncilMessage`` envelope (fresh id, UTC timestamp).

    When ``correlation_id`` is not given, the message self-correlates: its
    correlation id equals its message id, marking it as the origin of a new
    thread (thread == correlation id). Replies built with ``build_reply``
    inherit the thread root, so querying a history by a thread's correlation
    id returns the complete exchange, origin included.
    """
    resolved_id = message_id if message_id is not None else f"cm-{uuid.uuid4()}"
    return validate_envelope(
        {
            "message_id": resolved_id,
            "incident_id": incident_id,
            "round": round,
            "sender": sender,
            "recipients": recipients,
            "message_type": (
                message_type.value
                if isinstance(message_type, CouncilMessageType)
                else message_type
            ),
            "timestamp": (timestamp if timestamp is not None else utc_now()).isoformat(),
            "payload": payload if payload is not None else {},
            "correlation_id": correlation_id if correlation_id is not None else resolved_id,
        }
    )


def build_reply(
    original: CouncilMessage,
    *,
    message_type: CouncilMessageType | str,
    sender: str,
    payload: dict[str, Any] | None = None,
    recipients: list[str] | None = None,
    round: int | None = None,
    message_id: str | None = None,
) -> CouncilMessage:
    """Build a reply that threads the originating conversation.

    The reply's ``correlation_id`` is the root of the thread: the original's
    ``correlation_id`` when it was itself a reply, otherwise the original's
    ``message_id``. Replies default to answering the original sender on the
    same incident and round.
    """
    return build_message(
        incident_id=original.incident_id,
        message_type=message_type,
        sender=sender,
        recipients=recipients if recipients is not None else [original.sender],
        payload=payload,
        round=original.round if round is None else round,
        correlation_id=original.correlation_id or original.message_id,
        message_id=message_id,
    )
