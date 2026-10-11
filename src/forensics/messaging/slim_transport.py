"""AGNTCY SLIM transport wrapping the official ``slim-bindings`` package.

VERIFIED on this machine: aarch64 + Python 3.12 with ``slim-bindings==2.2.0``
(PyPI manylinux aarch64 wheel) — a genuine, mock-free point-to-point
exchange is recorded in ``tests/messaging/test_messaging_slim.py``.

``slim_bindings`` is imported lazily: when the optional dependency is not
installed, constructing a transport raises ``MessagingError`` with install
instructions and the SLIM tests skip cleanly. Each transport owns a
dedicated asyncio loop thread (SLIM's async UniFFI surface requires one
service per loop). ``send`` opens and caches a POINT_TO_POINT session per
recipient agent and publishes the ``CouncilMessage`` JSON envelope;
inbound sessions are accepted by a background listener whose payloads are
validated into per-incident queues.

Owner: agntcy-engineer (Stage B).
"""

from __future__ import annotations

import asyncio
import datetime
import socket
import threading
from queue import Empty, Queue
from typing import Any

from contracts.common import utc_now
from contracts.messages import CouncilMessage
from forensics.messaging.base import Transport
from forensics.messaging.envelopes import (
    InvalidEnvelopeError,
    MessagingError,
    NotSubscribedError,
    TransportClosedError,
    TransportTimeoutError,
    validate_envelope,
)

MIN_SHARED_SECRET_BYTES = 32


def import_slim_bindings() -> Any:
    """Import and return the ``slim_bindings`` module or fail with instructions."""
    try:
        import slim_bindings  # noqa: PLC0415 - deliberate lazy import
    except ImportError as exc:  # pragma: no cover - exercised only without the wheel
        raise MessagingError(
            "the AGNTCY SLIM transport requires the optional 'slim-bindings' "
            "package (verified version: slim-bindings==2.2.0). Install it into "
            "the active environment to use this transport."
        ) from exc
    return slim_bindings


def _free_port() -> int:
    """Grab an ephemeral free TCP port on 127.0.0.1 (for local servers/tests)."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class SlimLocalServer:
    """In-process insecure SLIM gRPC server bound to 127.0.0.1 (ephemeral port).

    Development and test helper: real AGNTCY deployments run the SLIM
    server as a separate process with TLS. Insecure (no TLS) is
    intentional and safe for loopback-only use.
    """

    def __init__(self, host: str = "127.0.0.1") -> None:
        self._host = host
        self._port = 0
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._service: Any = None

    @property
    def url(self) -> str:
        """Client endpoint URL of this server."""
        if self._loop is None:
            raise MessagingError("SLIM local server is not started")
        return f"http://{self._host}:{self._port}"

    def start(self) -> None:
        """Start the server (idempotent)."""
        if self._loop is not None:
            return
        slim = import_slim_bindings()
        self._port = _free_port()
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(
            target=self._loop.run_forever, name="slim-local-server", daemon=True
        )
        self._thread.start()

        async def _start() -> None:
            self._service = slim.create_service("forensics-slim-local-server")
            await self._service.run_server_async(
                slim.new_insecure_server_config(f"{self._host}:{self._port}")
            )

        self._run(_start())

    def stop(self) -> None:
        """Stop the server and release the port; idempotent."""
        loop = self._loop
        thread = self._thread
        self._loop = None
        self._thread = None
        service = self._service
        self._service = None
        if loop is None or thread is None:
            return

        async def _stop() -> None:
            if service is not None:
                service.stop_server(f"{self._host}:{self._port}")
                await service.shutdown_async()

        try:
            self._run_on(loop, _stop(), timeout_s=10.0)
        finally:
            loop.call_soon_threadsafe(loop.stop)
            thread.join(timeout=10.0)
            loop.close()

    def __enter__(self) -> SlimLocalServer:
        self.start()
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.stop()

    def _run(self, coro: Any, timeout_s: float = 30.0) -> Any:
        assert self._loop is not None
        return self._run_on(self._loop, coro, timeout_s)

    @staticmethod
    def _run_on(loop: asyncio.AbstractEventLoop, coro: Any, timeout_s: float) -> Any:
        future = asyncio.run_coroutine_threadsafe(coro, loop)
        return future.result(timeout_s)


class SlimTransport(Transport):
    """Council transport over AGNTCY SLIM point-to-point sessions.

    ``agent_id`` is the local agent identity (mapped to the SLIM name
    ``<org>/<namespace>/<agent_id>``); ``endpoint_url`` points at a SLIM
    server; ``shared_secret`` authenticates apps (SLIM requires at least 32
    bytes). Received envelopes are validated against the CouncilMessage
    contract before delivery; invalid payloads are rejected with a recorded
    reason. Messages for incidents that were never subscribed are dropped.
    """

    def __init__(
        self,
        agent_id: str,
        endpoint_url: str,
        shared_secret: str,
        *,
        org: str = "forensics",
        namespace: str = "council",
        connect_timeout_s: float = 20.0,
        receive_poll_s: float = 0.25,
    ) -> None:
        if len(shared_secret.encode("utf-8")) < MIN_SHARED_SECRET_BYTES:
            raise MessagingError(
                "SLIM shared secret is too short: at least "
                f"{MIN_SHARED_SECRET_BYTES} bytes are required (HMAC)"
            )
        self._slim = import_slim_bindings()
        self.agent_id = agent_id
        self._org = org
        self._namespace = namespace
        self._connect_timeout_s = connect_timeout_s
        self._receive_poll_s = receive_poll_s
        self._queues: dict[str, Queue[CouncilMessage]] = {}
        self._sessions: dict[str, Any] = {}
        self._pumps: set[asyncio.Task[None]] = set()
        self._rejected: list[str] = []
        self._lock = threading.Lock()
        self._closed = False
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(
            target=self._loop.run_forever, name=f"slim-{agent_id}", daemon=True
        )
        self._thread.start()
        self._run(self._startup(endpoint_url, shared_secret))

    @property
    def rejected(self) -> list[str]:
        """Reasons for recently rejected inbound payloads (audit trail)."""
        with self._lock:
            return list(self._rejected)

    def _slim_name(self, agent_id: str) -> Any:
        return self._slim.Name.from_string(f"{self._org}/{self._namespace}/{agent_id}")

    def _run(self, coro: Any, timeout_s: float | None = None) -> Any:
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result(self._connect_timeout_s if timeout_s is None else timeout_s)

    async def _startup(self, endpoint_url: str, shared_secret: str) -> None:
        self._service = self._slim.create_service(f"forensics-{self.agent_id}")
        self._conn = await self._service.connect_async(
            self._slim.new_insecure_client_config(endpoint_url)
        )
        self._app = self._service.create_app_with_secret(
            self._slim_name(self.agent_id), shared_secret
        )
        await self._app.subscribe_async(self._slim_name(self.agent_id), self._conn)
        self._listener = asyncio.create_task(self._listen())

    async def _listen(self) -> None:
        while not self._closed:
            try:
                session = await self._app.listen_for_session_async(None)
            except Exception:  # noqa: BLE001 - service shutdown ends the loop
                return
            task = asyncio.create_task(self._pump(session))
            self._pumps.add(task)
            task.add_done_callback(self._pumps.discard)

    async def _pump(self, session: Any) -> None:
        while not self._closed:
            try:
                received = await session.get_message_async(
                    timeout=datetime.timedelta(seconds=self._receive_poll_s)
                )
            except Exception:  # noqa: BLE001 - poll timeout or shutdown; retry
                await asyncio.sleep(self._receive_poll_s)
                continue
            try:
                message = validate_envelope(bytes(received.payload))
            except InvalidEnvelopeError as exc:
                with self._lock:
                    self._rejected.append(exc.detail)
                    del self._rejected[:-100]
                continue
            with self._lock:
                target = self._queues.get(message.incident_id)
            if target is not None:
                target.put(message.model_copy(update={"delivered_at": utc_now()}))

    def subscribe(self, incident_id: str) -> None:
        """Subscribe to an incident (idempotent)."""
        self._ensure_open()
        with self._lock:
            self._queues.setdefault(incident_id, Queue())

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
        except Empty:
            raise TransportTimeoutError(
                f"no message for incident {incident_id!r} within {timeout_s}s"
            ) from None

    def send(self, message: CouncilMessage | dict[str, Any] | str) -> None:
        """Validate the envelope and publish it to each recipient over SLIM."""
        self._ensure_open()
        validated = validate_envelope(message)
        body = validated.model_dump_json().encode("utf-8")
        for recipient in validated.recipients:
            session = self._run(self._ensure_session(recipient))
            self._run(session.publish_async(body, None, None))

    async def _ensure_session(self, recipient: str) -> Any:
        session = self._sessions.get(recipient)
        if session is not None:
            return session
        remote = self._slim_name(recipient)
        await self._app.set_route_async(remote, self._conn)
        config = self._slim.SessionConfig(
            session_type=self._slim.SessionType.POINT_TO_POINT,
            max_retries=5,
            interval=datetime.timedelta(seconds=2),
            metadata={},
            mls_settings=None,
        )
        context = await self._app.create_session_async(config, remote)
        await context.completion.wait_async()
        self._sessions[recipient] = context.session
        return context.session

    def close(self) -> None:
        """Tear down sessions, the app, and the loop thread; idempotent."""
        if self._closed:
            return
        self._closed = True

        def _cancel() -> None:
            self._listener.cancel()
            for task in list(self._pumps):
                task.cancel()

        self._loop.call_soon_threadsafe(_cancel)

        async def _teardown() -> None:
            try:
                await self._service.shutdown_async()
            except Exception:  # noqa: BLE001 - best-effort shutdown
                pass

        try:
            self._run(_teardown(), timeout_s=10.0)
        except Exception:  # noqa: BLE001 - best-effort shutdown
            pass
        finally:
            self._loop.call_soon_threadsafe(self._loop.stop)
            self._thread.join(timeout=10.0)
            self._loop.close()

    def _ensure_open(self) -> None:
        if self._closed:
            raise TransportClosedError(f"transport for agent {self.agent_id!r} is closed")
