"""Minimal localhost JSON service for the Forensics / Investigation Agent.

Standard library only (http.server — no new dependencies). Binds
127.0.0.1 on a configurable port (env FORENSICS_API_PORT, default 8747)
and wires *injected* backend / tools / engine components behind the
documented endpoints (see src/forensics/api/README.md):

    GET  /health          liveness + contracts version
    POST /incidents       receive an incident   (emits INCIDENT_ALERT)
    POST /investigations  request investigation (returns findings, emits FINDING)
    POST /proposals       receive a proposal    (returns position, emits VOTE)
    POST /evidence        receive evidence      (returns PositionRevision or no-change)

Every council-facing action is also emitted as a CouncilMessage envelope
through an injected transport callable, so the real AGNTCY transport
(feat/agntcy) can replace the test transport without touching this module.
"""

from __future__ import annotations

import json
import os
import threading
import uuid
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, ClassVar, cast

from pydantic import ValidationError

from contracts.common import CONTRACTS_VERSION, utc_now
from contracts.evidence import Evidence
from contracts.incident import Incident
from contracts.investigation import (
    DebatePosition,
    InvestigationFindings,
    InvestigationRequest,
    PositionRevision,
)
from contracts.messages import CouncilMessage, CouncilMessageType
from forensics.inference.base import InferenceBackendError

DEFAULT_PORT = 8747

#: Injected transport for council messages (e.g. AGNTCY topic writer).
MessageTransport = Callable[[CouncilMessage], None]


def _null_transport(message: CouncilMessage) -> None:
    """Default transport: drop messages silently (used when none is injected)."""


def _env_port() -> int:
    raw = os.environ.get("FORENSICS_API_PORT", "")
    try:
        return int(raw)
    except ValueError:
        return DEFAULT_PORT


def _print_transport(message: CouncilMessage) -> None:
    """Human-readable transport used by the demo / standalone startup."""
    print(
        f"[council->] {message.message_type.value} round={message.round} "
        f"incident={message.incident_id} id={message.message_id}"
    )


class _Handler(BaseHTTPRequestHandler):
    """Thin HTTP adapter: parse, dispatch to ForensicsService, serialize."""

    service: ClassVar[ForensicsService]

    def log_message(self, fmt: str, *args: Any) -> None:
        """Keep the console quiet; the service is not a logging endpoint."""

    def _respond(self, status: int, payload: dict[str, Any]) -> None:
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:
        path = self.path.split("?", 1)[0]
        if path == "/health":
            self._respond(
                200,
                {"status": "ok", "service": "forensics-api",
                 "contracts_version": CONTRACTS_VERSION},
            )
        else:
            self._respond(404, {"error": f"no such path: {path}"})

    def do_POST(self) -> None:
        path = self.path.split("?", 1)[0]
        try:
            length = int(self.headers.get("Content-Length", "0") or 0)
            raw = self.rfile.read(length) if length > 0 else b""
            body: dict[str, Any] = json.loads(raw.decode("utf-8")) if raw else {}
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            self._respond(400, {"error": f"invalid JSON body: {exc}"})
            return
        if not isinstance(body, dict):
            self._respond(400, {"error": "request body must be a JSON object"})
            return
        try:
            status, payload = self.service.dispatch(path, body)
            self._respond(status, payload)
        except ValidationError as exc:
            self._respond(400, {"error": "validation failed", "detail": json.loads(exc.json())})
        except ValueError as exc:
            self._respond(400, {"error": str(exc)})
        except InferenceBackendError as exc:
            self._respond(503, {"error": f"engine/backend failure: {exc}"})
        except Exception as exc:  # noqa: BLE001 - never crash the service
            self._respond(500, {"error": f"internal error: {exc}"})


class ForensicsService:
    """Wires injected engine + transport components behind a localhost server.

    `engine` is any object implementing the `InvestigationEngine` protocol
    (see tests/end_to_end/harness.py): investigate / evaluate_proposal /
    consider_evidence. Nothing mock-specific is referenced here.
    """

    def __init__(
        self,
        engine: Any,
        transport: MessageTransport | None = None,
        *,
        host: str = "127.0.0.1",
        port: int | None = None,
        agent_id: str = "forensics-agent",
    ) -> None:
        self.engine = engine
        self.transport: MessageTransport = transport or _null_transport
        self.host = host
        self.port = port if port is not None else _env_port()
        self.agent_id = agent_id
        self.incidents: dict[str, Incident] = {}
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    # ------------------------------------------------------------- lifecycle

    @property
    def running(self) -> bool:
        return self._server is not None

    @property
    def bound_port(self) -> int:
        """Port actually bound (differs from `.port` when ephemeral port=0 was used)."""
        if self._server is not None:
            return int(self._server.server_address[1])
        return self.port

    def start(self) -> int:
        """Bind and serve on a daemon thread; returns the actual bound port."""
        if self._server is not None:
            raise RuntimeError("service already started")
        handler = cast(
            "type[BaseHTTPRequestHandler]",
            type("BoundHandler", (_Handler,), {"service": self}),
        )
        self._server = ThreadingHTTPServer((self.host, self.port), handler)
        self._thread = threading.Thread(
            target=self._server.serve_forever, name="forensics-api", daemon=True
        )
        self._thread.start()
        return int(self._server.server_address[1])

    def stop(self) -> None:
        """Shut down cleanly (idempotent)."""
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
        if self._thread is not None:
            self._thread.join(timeout=5)
        self._server = None
        self._thread = None

    def __enter__(self) -> ForensicsService:
        self.start()
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.stop()

    # ------------------------------------------------------------- messaging

    def _emit(
        self,
        incident_id: str,
        round: int,
        message_type: CouncilMessageType,
        payload: dict[str, Any],
        correlation_id: str | None = None,
        recipients: list[str] | None = None,
    ) -> None:
        self.transport(
            CouncilMessage(
                message_id=f"CM-{uuid.uuid4()}",
                incident_id=incident_id,
                round=round,
                sender=self.agent_id,
                recipients=recipients or ["council"],
                message_type=message_type,
                timestamp=utc_now(),
                payload=payload,
                correlation_id=correlation_id,
            )
        )

    # -------------------------------------------------------------- dispatch

    def dispatch(self, path: str, body: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        """Route one parsed JSON request body; returns (status, payload)."""
        if path == "/incidents":
            return self.receive_incident(body)
        if path == "/investigations":
            return self.request_investigation(body)
        if path == "/proposals":
            return self.receive_proposal(body)
        if path == "/evidence":
            return self.receive_evidence(body)
        raise ValueError(f"no such path: {path}")

    def receive_incident(self, body: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        incident = Incident.model_validate(body)
        self.incidents[incident.incident_id] = incident
        self._emit(
            incident.incident_id,
            0,
            CouncilMessageType.INCIDENT_ALERT,
            {"incident": incident.model_dump(mode="json")},
        )
        return 201, {"incident_id": incident.incident_id, "status": "accepted"}

    def request_investigation(self, body: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        request = InvestigationRequest.model_validate(body)
        findings = self.engine.investigate(request)
        if not isinstance(findings, InvestigationFindings):
            raise ValueError("engine returned invalid findings")
        self._emit(
            request.incident_id,
            request.round,
            CouncilMessageType.FINDING,
            {"findings": findings.model_dump(mode="json")},
            correlation_id=request.request_id,
        )
        return 200, {
            "request_id": request.request_id,
            "findings": findings.model_dump(mode="json"),
        }

    def receive_proposal(self, body: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        incident_id = body.get("incident_id")
        round = body.get("round", 0)
        proposal = body.get("proposal")
        if not isinstance(incident_id, str) or not incident_id.strip():
            raise ValueError("proposal submission requires non-empty 'incident_id'")
        if not isinstance(round, int) or isinstance(round, bool) or round < 0:
            raise ValueError("'round' must be a non-negative integer")
        if not isinstance(proposal, dict) or not proposal:
            raise ValueError("'proposal' must be a non-empty object")
        position = self.engine.evaluate_proposal(incident_id, round, proposal)
        if not isinstance(position, DebatePosition):
            raise ValueError("engine returned invalid position")
        self._emit(
            incident_id,
            round,
            CouncilMessageType.VOTE,
            {"position": position.model_dump(mode="json")},
        )
        return 200, {"position": position.model_dump(mode="json")}

    def receive_evidence(self, body: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        evidence = Evidence.model_validate(body)
        self._emit(
            evidence.incident_id,
            0,
            CouncilMessageType.EVIDENCE_RESPONSE,
            {"evidence_id": evidence.evidence_id, "acknowledged_by": self.agent_id},
        )
        revision = self.engine.consider_evidence(evidence)
        if revision is None:
            return 200, {"revised": False, "revision": None}
        if not isinstance(revision, PositionRevision):
            raise ValueError("engine returned invalid revision")
        self._emit(
            evidence.incident_id,
            revision.round,
            CouncilMessageType.REVISION,
            {"revision": revision.model_dump(mode="json")},
        )
        return 200, {"revised": True, "revision": revision.model_dump(mode="json")}


def build_default_service(transport: MessageTransport | None = None) -> ForensicsService:
    """Wire the Stage A mock components until the real branches merge.

    The engine protocol is the only contract; replacing this factory with
    real backend/tools/engine wiring requires no changes elsewhere.
    """
    from forensics.inference.mock import MockInferenceBackend
    from forensics.tools.mock import build_mock_registry
    from tests.end_to_end.harness import MockInvestigationEngine

    backend = MockInferenceBackend()
    engine = MockInvestigationEngine(backend=backend, registry=build_mock_registry())
    return ForensicsService(engine=engine, transport=transport or _print_transport)


def main() -> int:
    """Standalone startup: serve the mock-wired service on FORENSICS_API_PORT."""
    service = build_default_service()
    port = service.start()
    print(
        f"forensics-api listening on http://{service.host}:{port} "
        "(Stage A mock components; Ctrl+C to stop)"
    )
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        pass
    finally:
        service.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
