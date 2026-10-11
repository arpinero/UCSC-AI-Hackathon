"""Runtime council messaging: transport-agnostic core plus transports.

Components (owner: agntcy-engineer, Stage B):

- ``envelopes``: strict ``CouncilMessage`` validation + correlation-threaded
  reply builders.
- ``base``: ``Transport`` ABC, ``CouncilBus``/``Session`` keyed by incident.
- ``history``: auditable per-incident debate history (JSONL persistence).
- ``memory``: reliable in-process transport (reference for the team/tests).
- ``http_a2a``: A2A-compatible envelopes over stdlib HTTP (fallback
  transport; NOT SLIM).
- ``slim_transport``: AGNTCY SLIM transport (optional dependency
  ``slim-bindings``; verified genuine exchange on aarch64).
"""

from __future__ import annotations

from forensics.messaging.base import CouncilBus, Session, Transport
from forensics.messaging.envelopes import (
    InvalidEnvelopeError,
    MessagingError,
    NotSubscribedError,
    TransportClosedError,
    TransportTimeoutError,
    build_message,
    build_reply,
    validate_envelope,
)
from forensics.messaging.history import (
    DEFAULT_DEBATE_HISTORY_DIR,
    DebateHistory,
    default_history_path,
)
from forensics.messaging.http_a2a import A2AEndpoint, HTTPTransport
from forensics.messaging.memory import InMemoryNetwork, InMemoryTransport
from forensics.messaging.slim_transport import SlimLocalServer, SlimTransport

__all__ = [
    "A2AEndpoint",
    "CouncilBus",
    "DebateHistory",
    "DEFAULT_DEBATE_HISTORY_DIR",
    "HTTPTransport",
    "InMemoryNetwork",
    "InMemoryTransport",
    "InvalidEnvelopeError",
    "MessagingError",
    "NotSubscribedError",
    "Session",
    "SlimLocalServer",
    "SlimTransport",
    "Transport",
    "TransportClosedError",
    "TransportTimeoutError",
    "build_message",
    "build_reply",
    "default_history_path",
    "validate_envelope",
]
