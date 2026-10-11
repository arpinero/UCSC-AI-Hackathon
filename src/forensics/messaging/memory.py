"""Reliable in-process transport: the reference/mock transport for the team.

Delivers validated ``CouncilMessage`` envelopes between transports sharing
an ``InMemoryNetwork``. Delivery is incident-scoped: a transport receives
messages only for incidents it has subscribed to, which gives strict
per-incident isolation. Delivered copies carry ``delivered_at`` timestamps.

Owner: agntcy-engineer (Stage B).
"""

from __future__ import annotations

import queue
import threading
from typing import Any

from contracts.common import utc_now
from contracts.messages import CouncilMessage
from forensics.messaging.base import Transport
from forensics.messaging.envelopes import (
    MessagingError,
    NotSubscribedError,
    TransportClosedError,
    TransportTimeoutError,
    validate_envelope,
)


class InMemoryNetwork:
    """Registry of in-process transports that can exchange messages."""

    def __init__(self) -> None:
        self._transports: dict[str, InMemoryTransport] = {}
        self._lock = threading.Lock()

    def register(self, transport: InMemoryTransport) -> None:
        """Register a transport under its agent id (must be unique)."""
        with self._lock:
            if transport.agent_id in self._transports:
                raise MessagingError(f"duplicate agent id on network: {transport.agent_id!r}")
            self._transports[transport.agent_id] = transport

    def unregister(self, transport: InMemoryTransport) -> None:
        """Remove a transport from the network (idempotent)."""
        with self._lock:
            self._transports.pop(transport.agent_id, None)

    def deliver(self, message: CouncilMessage) -> None:
        """Offer a validated message to every subscribed transport."""
        with self._lock:
            transports = list(self._transports.values())
        for transport in transports:
            transport.offer(message)


class InMemoryTransport(Transport):
    """In-process transport; pair transports through a shared ``InMemoryNetwork``."""

    def __init__(self, agent_id: str, network: InMemoryNetwork | None = None) -> None:
        self.agent_id = agent_id
        self._network = network if network is not None else InMemoryNetwork()
        self._queues: dict[str, queue.Queue[CouncilMessage]] = {}
        self._lock = threading.Lock()
        self._closed = False
        self._network.register(self)

    def is_subscribed(self, incident_id: str) -> bool:
        """True if this transport subscribed to the incident."""
        with self._lock:
            return incident_id in self._queues

    def subscribe(self, incident_id: str) -> None:
        """Subscribe to an incident (idempotent)."""
        self._ensure_open()
        with self._lock:
            self._queues.setdefault(incident_id, queue.Queue())

    def offer(self, message: CouncilMessage) -> bool:
        """Delivery hook used by the network; returns True if accepted."""
        with self._lock:
            target = self._queues.get(message.incident_id)
        if target is None:
            return False
        target.put(message.model_copy(update={"delivered_at": utc_now()}))
        return True

    def send(
        self, message: CouncilMessage | dict[str, Any] | str
    ) -> None:
        """Validate the envelope and deliver it to subscribed transports."""
        self._ensure_open()
        validated = validate_envelope(message)
        self._network.deliver(validated)

    def receive(self, incident_id: str, timeout_s: float | None = None) -> CouncilMessage:
        """Return the next message for the incident (blocks up to ``timeout_s``)."""
        self._ensure_open()
        with self._lock:
            target = self._queues.get(incident_id)
        if target is None:
            raise NotSubscribedError(
                f"agent {self.agent_id!r} is not subscribed to incident {incident_id!r}"
            )
        try:
            return target.get(timeout=timeout_s if timeout_s is not None else None)
        except queue.Empty:
            raise TransportTimeoutError(
                f"no message for incident {incident_id!r} within {timeout_s}s"
            ) from None

    def close(self) -> None:
        """Close the transport and drop queued messages; idempotent."""
        with self._lock:
            self._closed = True
            self._queues.clear()

    def _ensure_open(self) -> None:
        if self._closed:
            raise TransportClosedError(f"transport for agent {self.agent_id!r} is closed")
