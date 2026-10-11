"""A2A-compatible envelopes over HTTP — the fallback transport (stdlib only).

This is NOT SLIM and claims no AGNTCY stack compliance. It exchanges
``CouncilMessage`` JSON envelopes over plain HTTP between agent services:
each agent runs a small ``http.server``-based listener bound to 127.0.0.1 on
an ephemeral port, exposing one POST endpoint per incident
(``/a2a/<incident_id>/messages``), and sends envelopes with
``urllib.request``. Agents discover each other through explicit peer URL
mappings (agent id -> base URL).

Owner: agntcy-engineer (Stage B).
"""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Mapping
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from queue import Empty, Queue
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


def _make_handler(endpoint: A2AEndpoint) -> type[BaseHTTPRequestHandler]:
    """Build a request handler bound to one endpoint instance."""

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802 - stdlib naming
            parts = urllib.parse.urlparse(self.path).path.strip("/").split("/")
            if len(parts) != 3 or parts[0] != "a2a" or parts[2] != "messages":
                self._respond(404, {"error": f"unknown path {self.path!r}"})
                return
            incident_id = urllib.parse.unquote(parts[1])
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                self._respond(400, {"error": "invalid Content-Length header"})
                return
            body = self.rfile.read(length)
            status, payload = endpoint.accept(incident_id, body)
            self._respond(status, payload)

        def do_GET(self) -> None:  # noqa: N802 - stdlib naming
            path = urllib.parse.urlparse(self.path).path.strip("/")
            if path in ("health", "a2a/health"):
                self._respond(200, {"status": "ok", "agent_id": endpoint.agent_id})
            else:
                self._respond(404, {"error": f"unknown path {self.path!r}"})

        def _respond(self, status: int, payload: dict[str, Any]) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
            """Silence per-request logging (tests stay quiet)."""

    return Handler


class A2AEndpoint:
    """HTTP listener (127.0.0.1, ephemeral port) accepting council envelopes.

    POST ``/a2a/<incident_id>/messages`` validates the ``CouncilMessage``
    JSON body, checks it belongs to the incident in the path, and enqueues
    it for the incident's subscription. Invalid envelopes get a 400 with a
    clear error; unsubscribed incidents get a 404.
    """

    def __init__(self, agent_id: str, host: str = "127.0.0.1", port: int = 0) -> None:
        self.agent_id = agent_id
        self._host = host
        self._port = port
        self._queues: dict[str, Queue[CouncilMessage]] = {}
        self._lock = threading.Lock()
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    @property
    def url(self) -> str:
        """Base URL of this endpoint (valid after ``start()``)."""
        if self._server is None:
            raise MessagingError(f"endpoint for {self.agent_id!r} is not started")
        return f"http://{self._host}:{self._port}"

    @property
    def port(self) -> int:
        """Actual bound port (ephemeral when constructed with port=0)."""
        if self._server is None:
            raise MessagingError(f"endpoint for {self.agent_id!r} is not started")
        return self._port

    def start(self) -> None:
        """Bind and serve (idempotent). Binds 127.0.0.1 only."""
        if self._server is not None:
            return
        self._server = ThreadingHTTPServer((self._host, self._port), _make_handler(self))
        self._server.daemon_threads = True
        self._port = self._server.server_address[1]
        self._thread = threading.Thread(
            target=self._server.serve_forever, name=f"a2a-{self.agent_id}", daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        """Shut down cleanly; idempotent."""
        server = self._server
        thread = self._thread
        self._server = None
        self._thread = None
        if server is not None:
            server.shutdown()
            server.server_close()
        if thread is not None:
            thread.join(timeout=5.0)
        with self._lock:
            self._queues.clear()

    def __enter__(self) -> A2AEndpoint:
        self.start()
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.stop()

    def subscribe(self, incident_id: str) -> None:
        """Subscribe to an incident (idempotent)."""
        if self._server is None:
            raise MessagingError(f"endpoint for {self.agent_id!r} is not started")
        with self._lock:
            self._queues.setdefault(incident_id, Queue())

    def accept(self, incident_id: str, body: bytes) -> tuple[int, dict[str, Any]]:
        """Validate and enqueue one inbound envelope; returns (status, payload)."""
        try:
            message = validate_envelope(body)
        except MessagingError as exc:
            return 400, {"error": str(exc)}
        if message.incident_id != incident_id:
            return 400, {
                "error": (
                    f"path incident {incident_id!r} does not match envelope "
                    f"incident_id {message.incident_id!r}"
                )
            }
        with self._lock:
            target = self._queues.get(incident_id)
        if target is None:
            return 404, {
                "error": (
                    f"agent {self.agent_id!r} is not subscribed to incident {incident_id!r}"
                )
            }
        target.put(message.model_copy(update={"delivered_at": utc_now()}))
        return 200, {"status": "accepted", "message_id": message.message_id}

    def receive(self, incident_id: str, timeout_s: float | None = None) -> CouncilMessage:
        """Return the next message for the incident (blocks up to ``timeout_s``)."""
        with self._lock:
            target = self._queues.get(incident_id)
        if target is None:
            raise NotSubscribedError(
                f"agent {self.agent_id!r} is not subscribed to incident {incident_id!r}"
            )
        try:
            return target.get(timeout=timeout_s if timeout_s is not None else None)
        except Empty:
            raise TransportTimeoutError(
                f"no message for incident {incident_id!r} within {timeout_s}s"
            ) from None



class HTTPTransport(Transport):
    """A2A-over-HTTP transport: sends via ``urllib``, receives via an endpoint.

    ``peers`` maps agent ids to the base URL of the peer's ``A2AEndpoint``.
    ``send`` POSTs the validated ``CouncilMessage`` JSON envelope to every
    recipient's ``/a2a/<incident_id>/messages`` URL; ``receive`` pops the
    receiving endpoint's per-incident queue. Pure stdlib; loopback only.
    """

    def __init__(
        self,
        agent_id: str,
        peers: Mapping[str, str],
        *,
        host: str = "127.0.0.1",
        port: int = 0,
        request_timeout_s: float = 10.0,
    ) -> None:
        self.agent_id = agent_id
        self._peers = dict(peers)
        self._request_timeout_s = request_timeout_s
        self._closed = False
        self._endpoint = A2AEndpoint(agent_id, host=host, port=port)
        self._endpoint.start()

    @property
    def endpoint_url(self) -> str:
        """Base URL of the embedded receiving endpoint."""
        return self._endpoint.url

    @property
    def port(self) -> int:
        """Ephemeral port the embedded endpoint bound to."""
        return self._endpoint.port

    def add_peer(self, agent_id: str, base_url: str) -> None:
        """Register (or replace) the endpoint URL of a peer agent."""
        self._peers[agent_id] = base_url

    def subscribe(self, incident_id: str) -> None:
        """Subscribe the receiving endpoint to an incident."""
        self._ensure_open()
        self._endpoint.subscribe(incident_id)

    def receive(self, incident_id: str, timeout_s: float | None = None) -> CouncilMessage:
        """Return the next message for the incident (blocks up to ``timeout_s``)."""
        self._ensure_open()
        return self._endpoint.receive(incident_id, timeout_s)

    def send(self, message: CouncilMessage | dict[str, Any] | str) -> None:
        """Validate the envelope and POST it to each recipient's endpoint."""
        self._ensure_open()
        validated = validate_envelope(message)
        body = validated.model_dump_json().encode("utf-8")
        incident_path = urllib.parse.quote(validated.incident_id, safe="")
        for recipient in validated.recipients:
            base = self._peers.get(recipient)
            if base is None:
                raise MessagingError(f"no known A2A endpoint for recipient {recipient!r}")
            url = f"{base.rstrip('/')}/a2a/{incident_path}/messages"
            request = urllib.request.Request(
                url,
                data=body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            try:
                with urllib.request.urlopen(
                    request, timeout=self._request_timeout_s
                ) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                    if payload.get("status") != "accepted":
                        raise MessagingError(
                            f"A2A delivery to {recipient!r} not accepted: {payload}"
                        )
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", "replace")
                raise MessagingError(
                    f"A2A delivery to {recipient!r} failed: HTTP {exc.code}: {detail}"
                ) from exc
            except urllib.error.URLError as exc:
                raise MessagingError(
                    f"A2A delivery to {recipient!r} failed: {exc.reason}"
                ) from exc

    def close(self) -> None:
        """Stop the embedded endpoint; idempotent."""
        self._closed = True
        self._endpoint.stop()

    def _ensure_open(self) -> None:
        if self._closed:
            raise TransportClosedError(f"transport for agent {self.agent_id!r} is closed")
