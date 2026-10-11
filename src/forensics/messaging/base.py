"""Transport-agnostic council messaging core.

``Transport`` is the abstract wire: ``send``, ``receive``, ``subscribe``,
``close``. ``CouncilBus`` and ``Session`` key messaging by incident, enforce
the ``contracts.messages.CouncilMessage`` envelope on every input and
output, thread replies to origins via correlation IDs, and record every
exchange in an auditable per-incident debate history.

Transports provided by this package:

- ``forensics.messaging.memory`` — reliable in-process transport (reference).
- ``forensics.messaging.http_a2a`` — A2A-compatible envelopes over stdlib
  HTTP (fallback transport; NOT SLIM).
- ``forensics.messaging.slim_transport`` — AGNTCY SLIM (optional dependency,
  verified on this machine with slim-bindings==2.2.0).

Owner: agntcy-engineer (Stage B).
"""

from __future__ import annotations

import threading
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from contracts.messages import CouncilMessage, CouncilMessageType
from forensics.messaging.envelopes import (
    InvalidEnvelopeError,
    build_message,
    build_reply,
    validate_envelope,
)
from forensics.messaging.history import DebateHistory


class Transport(ABC):
    """Abstract message transport carrying ``CouncilMessage`` envelopes."""

    @abstractmethod
    def send(self, message: CouncilMessage) -> None:
        """Validate ``message`` and dispatch it to its recipients."""

    @abstractmethod
    def receive(self, incident_id: str, timeout_s: float | None = None) -> CouncilMessage:
        """Return the next message for ``incident_id`` (blocks up to ``timeout_s``).

        Raises ``NotSubscribedError`` if the incident was never subscribed and
        ``TransportTimeoutError`` when no message arrives in time.
        """

    @abstractmethod
    def subscribe(self, incident_id: str) -> None:
        """Register interest in an incident (per-incident delivery isolation)."""

    @abstractmethod
    def close(self) -> None:
        """Release all resources; must be idempotent."""


class Session:
    """Per-incident messaging session over one transport.

    Every message passing through a session is validated against the
    CouncilMessage contract, must belong to this session's incident, and is
    recorded in the incident's auditable debate history — on both send and
    receive, so each side keeps the full exchange.
    """

    def __init__(self, incident_id: str, transport: Transport, history: DebateHistory) -> None:
        self._incident_id = incident_id
        self._transport = transport
        self._history = history
        self._round = 0
        transport.subscribe(incident_id)

    @property
    def incident_id(self) -> str:
        """Incident this session is keyed to."""
        return self._incident_id

    @property
    def history(self) -> DebateHistory:
        """Auditable debate history for this incident."""
        return self._history

    @property
    def round(self) -> int:
        """Current debate round for this incident."""
        return self._round

    def advance_round(self) -> int:
        """Move the debate to the next round; returns the new round number."""
        self._round += 1
        return self._round

    def build(
        self,
        *,
        message_type: CouncilMessageType | str,
        sender: str,
        recipients: list[str],
        payload: dict[str, Any] | None = None,
        correlation_id: str | None = None,
        round: int | None = None,
    ) -> CouncilMessage:
        """Build a validated message bound to this incident and round."""
        return build_message(
            incident_id=self._incident_id,
            message_type=message_type,
            sender=sender,
            recipients=recipients,
            payload=payload,
            round=self._round if round is None else round,
            correlation_id=correlation_id,
        )

    def build_reply(
        self,
        original: CouncilMessage,
        *,
        message_type: CouncilMessageType | str,
        sender: str,
        payload: dict[str, Any] | None = None,
        recipients: list[str] | None = None,
    ) -> CouncilMessage:
        """Build a validated reply threading ``original``'s correlation ID.

        The reply carries this session's current round (the session is the
        authority on debate rounds for its incident).
        """
        reply = build_reply(
            original,
            message_type=message_type,
            sender=sender,
            payload=payload,
            recipients=recipients,
            round=self._round,
        )
        if reply.incident_id != self._incident_id:
            raise InvalidEnvelopeError(
                f"reply incident_id {reply.incident_id!r} does not match "
                f"session incident {self._incident_id!r}"
            )
        return reply

    def send(self, message: CouncilMessage | dict[str, Any] | str) -> CouncilMessage:
        """Validate, record, and dispatch one council message."""
        validated = validate_envelope(message)
        if validated.incident_id != self._incident_id:
            raise InvalidEnvelopeError(
                f"message incident_id {validated.incident_id!r} does not match "
                f"session incident {self._incident_id!r}"
            )
        self._history.record(validated)
        self._transport.send(validated)
        return validated

    def receive(self, timeout_s: float | None = None) -> CouncilMessage:
        """Receive, record, and return the next message for this incident."""
        message = self._transport.receive(self._incident_id, timeout_s)
        self._history.record(message)
        return message


class CouncilBus:
    """Entry point tying one transport to per-incident sessions and history."""

    def __init__(self, transport: Transport, history_dir: str | Path | None = None) -> None:
        self._transport = transport
        self._history_dir = Path(history_dir) if history_dir is not None else None
        self._sessions: dict[str, Session] = {}
        self._lock = threading.Lock()

    @property
    def transport(self) -> Transport:
        """The underlying transport shared by all sessions."""
        return self._transport

    def session(self, incident_id: str) -> Session:
        """Return (creating and subscribing if needed) the session for an incident."""
        with self._lock:
            existing = self._sessions.get(incident_id)
            if existing is not None:
                return existing
            path = (
                None
                if self._history_dir is None
                else self._history_dir / f"{incident_id.replace('/', '_')}.jsonl"
            )
            session = Session(
                incident_id, self._transport, DebateHistory(incident_id, path)
            )
            self._sessions[incident_id] = session
            return session

    def close(self) -> None:
        """Close the underlying transport; sessions become unusable afterwards."""
        self._transport.close()
