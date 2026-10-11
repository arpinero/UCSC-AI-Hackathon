"""HTTP service integration tests: start on an ephemeral 127.0.0.1 port,
exercise every documented endpoint, verify council message emission, and
shut down cleanly. Validated response shapes are mirrored in
src/forensics/api/README.md.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from collections.abc import Iterator
from typing import Any

import pytest

from contracts.investigation import (
    DebatePosition,
    InvestigationFindings,
    PositionRevision,
)
from contracts.messages import CouncilMessage
from forensics.api.service import DEFAULT_PORT, ForensicsService
from tests.end_to_end.harness import MockInvestigationEngine
from tests.integration.scenario import (
    EVIDENCE_ID_2,
    INCIDENT_ID,
    make_evidence,
    make_incident,
    make_request,
)


def _post(url: str, payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url, data=data, method="POST", headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


def _get(url: str) -> tuple[int, dict[str, Any]]:
    try:
        with urllib.request.urlopen(url, timeout=5) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


class RunningService:
    """Test helper bundling the service, its base URL, and emitted messages."""

    def __init__(self, service: ForensicsService, messages: list[CouncilMessage]) -> None:
        self.service = service
        self.messages = messages
        self.base = f"http://{service.host}:{service.bound_port}"

    def post(self, path: str, payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        return _post(self.base + path, payload)

    def get(self, path: str) -> tuple[int, dict[str, Any]]:
        return _get(self.base + path)

    @property
    def types(self) -> list[str]:
        return [message.message_type.value for message in self.messages]


@pytest.fixture
def running(backend, registry) -> Iterator[RunningService]:
    messages: list[CouncilMessage] = []
    engine = MockInvestigationEngine(backend=backend, registry=registry)
    service = ForensicsService(engine=engine, transport=messages.append, port=0)
    service.start()
    yield RunningService(service, messages)
    service.stop()


def test_health(running):
    status, body = running.get("/health")
    assert status == 200
    assert body == {
        "status": "ok",
        "service": "forensics-api",
        "contracts_version": "1.0.0",
    }


def test_receive_incident_emits_incident_alert(running):
    status, body = running.post("/incidents", make_incident())
    assert status == 201
    assert body == {"incident_id": INCIDENT_ID, "status": "accepted"}
    assert running.types == ["INCIDENT_ALERT"]
    assert running.messages[0].payload["incident"]["incident_id"] == INCIDENT_ID


def test_investigation_returns_validated_findings(running):
    running.post("/incidents", make_incident())
    status, body = running.post("/investigations", make_request())
    assert status == 200
    assert body["request_id"] == "REQ-INC-2026-001-1"
    findings = InvestigationFindings.model_validate(body["findings"])
    assert findings.incident_id == INCIDENT_ID
    assert findings.cited_evidence_ids  # evidence ids flowed into findings
    assert "FINDING" in running.types


def test_proposal_returns_position(running):
    running.post("/incidents", make_incident())
    status, body = running.post(
        "/proposals",
        {"incident_id": INCIDENT_ID, "round": 2, "proposal": {"action": "isolate web-01"}},
    )
    assert status == 200
    position = DebatePosition.model_validate(body["position"])
    assert position.incident_id == INCIDENT_ID
    assert position.position.value in {"SUPPORT", "OPPOSE", "ABSTAIN"}
    assert "VOTE" in running.types


def test_evidence_returns_position_revision(running):
    running.post("/incidents", make_incident())
    running.post(
        "/proposals",
        {"incident_id": INCIDENT_ID, "round": 2, "proposal": {"action": "isolate web-01"}},
    )
    status, body = running.post(
        "/evidence",
        make_evidence(EVIDENCE_ID_2, description="Backup schedule shows transfer was sanctioned"),
    )
    assert status == 200
    assert body["revised"] is True
    revision = PositionRevision.model_validate(body["revision"])
    assert revision.previous_position.position.value == "SUPPORT"
    assert revision.new_position.position.value == "OPPOSE"
    assert revision.triggering_evidence_ids == [EVIDENCE_ID_2]
    assert running.types[-2:] == ["EVIDENCE_RESPONSE", "REVISION"]


def test_full_cycle_message_sequence(running):
    running.post("/incidents", make_incident())
    running.post("/investigations", make_request())
    running.post(
        "/proposals",
        {"incident_id": INCIDENT_ID, "round": 2, "proposal": {"action": "isolate web-01"}},
    )
    running.post("/evidence", make_evidence(EVIDENCE_ID_2, description="Contradicting evidence"))
    assert running.types == [
        "INCIDENT_ALERT",
        "FINDING",
        "VOTE",
        "EVIDENCE_RESPONSE",
        "REVISION",
    ]


def test_evidence_without_prior_position_is_no_change(running):
    running.post("/incidents", make_incident())
    status, body = running.post("/evidence", make_evidence())
    assert status == 200
    assert body == {"revised": False, "revision": None}


def test_evidence_no_change_when_decider_declines(backend, registry):
    messages: list[CouncilMessage] = []
    engine = MockInvestigationEngine(
        backend=backend,
        registry=registry,
        revision_decider=lambda evidence, position: False,
    )
    service = ForensicsService(engine=engine, transport=messages.append, port=0)
    service.start()
    try:
        helper = RunningService(service, messages)
        helper.post("/incidents", make_incident())
        helper.post(
            "/proposals",
            {"incident_id": INCIDENT_ID, "round": 2, "proposal": {"action": "isolate web-01"}},
        )
        status, body = helper.post("/evidence", make_evidence())
        assert status == 200
        assert body == {"revised": False, "revision": None}
        assert "REVISION" not in helper.types
    finally:
        service.stop()


def test_invalid_incident_returns_400(running):
    status, body = running.post("/incidents", {"incident_id": ""})
    assert status == 400
    assert "error" in body


def test_unknown_path_and_wrong_method(running):
    status, body = running.post("/nope", {})
    assert status == 400  # ValueError("no such path") maps to 400
    assert "no such path" in body["error"]
    status, _ = running.get("/nope")
    assert status == 404


def test_stop_shuts_down_cleanly(backend, registry):
    engine = MockInvestigationEngine(backend=backend, registry=registry)
    service = ForensicsService(engine=engine, port=0)
    port = service.start()
    base = f"http://127.0.0.1:{port}"
    status, _ = _get(base + "/health")
    assert status == 200
    service.stop()
    assert not service.running
    with pytest.raises(urllib.error.URLError):
        _get(base + "/health")


def test_env_port_configuration(monkeypatch):
    monkeypatch.setenv("FORENSICS_API_PORT", "9999")
    service = ForensicsService(engine=None)  # not started; engine never called
    assert service.port == 9999
    monkeypatch.setenv("FORENSICS_API_PORT", "not-a-number")
    assert ForensicsService(engine=None).port == DEFAULT_PORT
    monkeypatch.delenv("FORENSICS_API_PORT")
    assert ForensicsService(engine=None).port == DEFAULT_PORT


def test_service_uses_injected_transport_only(backend, registry):
    """No transport injected -> service still works and drops messages."""
    engine = MockInvestigationEngine(backend=backend, registry=registry)
    service = ForensicsService(engine=engine, port=0)
    service.start()
    try:
        status, body = _post(
            f"http://127.0.0.1:{service.bound_port}/incidents", make_incident()
        )
        assert status == 201
    finally:
        service.stop()
