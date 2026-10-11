"""Integration tests: REAL loopback HTTP exchange of A2A-style envelopes.

Two endpoints on 127.0.0.1 (ephemeral ports, in-process) exchange the
mandated flow INCIDENT_ALERT -> EVIDENCE_REQUEST -> EVIDENCE_RESPONSE ->
FINDING, verified from both sides and present in both debate histories.
Pure stdlib client/server; no SLIM or AGNTCY stack compliance is claimed.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request

import pytest

from forensics.messaging.base import CouncilBus
from forensics.messaging.envelopes import (
    MessagingError,
    NotSubscribedError,
    build_message,
)
from forensics.messaging.http_a2a import A2AEndpoint, HTTPTransport

INCIDENT = "INC-HTTP-1"


def post(url: str, body: bytes):
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    return urllib.request.urlopen(request, timeout=5.0)


def test_endpoint_rejects_invalid_envelope_with_400():
    with A2AEndpoint("probe") as endpoint:
        endpoint.subscribe(INCIDENT)
        with pytest.raises(urllib.error.HTTPError) as excinfo:
            post(f"{endpoint.url}/a2a/{INCIDENT}/messages", b"{not json")
        assert excinfo.value.code == 400
        assert "not valid JSON" in excinfo.value.read().decode("utf-8")


def test_endpoint_health_and_unknown_paths():
    with A2AEndpoint("probe") as endpoint:
        with urllib.request.urlopen(f"{endpoint.url}/health", timeout=5.0) as response:
            assert response.status == 200
            assert json.loads(response.read().decode("utf-8"))["agent_id"] == "probe"
        with pytest.raises(urllib.error.HTTPError) as excinfo:
            urllib.request.urlopen(f"{endpoint.url}/nope", timeout=5.0)
        assert excinfo.value.code == 404


def test_endpoint_404_for_unsubscribed_incident():
    with A2AEndpoint("probe") as endpoint:
        message = build_message(
            incident_id=INCIDENT,
            message_type="FINDING",
            sender="x",
            recipients=["probe"],
        )
        with pytest.raises(urllib.error.HTTPError) as excinfo:
            post(
                f"{endpoint.url}/a2a/{INCIDENT}/messages",
                message.model_dump_json().encode("utf-8"),
            )
        assert excinfo.value.code == 404
        assert "not subscribed" in excinfo.value.read().decode("utf-8")


def test_send_to_unreachable_peer_rejected():
    transport = HTTPTransport("forensics", {"ghost": "http://127.0.0.1:9"})
    try:
        message = build_message(
            incident_id=INCIDENT,
            message_type="FINDING",
            sender="forensics",
            recipients=["ghost"],
        )
        with pytest.raises(MessagingError, match="ghost"):
            transport.send(message)
    finally:
        transport.close()


def test_http_incident_isolation():
    left = HTTPTransport("left", {})
    right = HTTPTransport("right", {"left": left.endpoint_url})
    left.add_peer("right", right.endpoint_url)
    try:
        left.subscribe("INC-A")
        right.subscribe("INC-A")
        message = build_message(
            incident_id="INC-A",
            message_type="FINDING",
            sender="left",
            recipients=["right"],
        )
        left.send(message)
        assert right.receive("INC-A", timeout_s=5.0).message_id == message.message_id
        with pytest.raises(NotSubscribedError):
            right.receive("INC-B")
    finally:
        left.close()
        right.close()


def test_real_loopback_exchange_full_flow(tmp_path):
    """Real HTTP exchange: ALERT -> EVIDENCE_REQUEST -> EVIDENCE_RESPONSE -> FINDING."""
    monitor = HTTPTransport("monitor", {})
    forensics = HTTPTransport("forensics", {"monitor": monitor.endpoint_url})
    monitor.add_peer("forensics", forensics.endpoint_url)
    # Two distinct ephemeral loopback ports, both on 127.0.0.1.
    assert monitor.endpoint_url.startswith("http://127.0.0.1:")
    assert forensics.endpoint_url.startswith("http://127.0.0.1:")
    assert monitor.port != forensics.port

    monitor_bus = CouncilBus(monitor, history_dir=tmp_path / "monitor")
    forensics_bus = CouncilBus(forensics, history_dir=tmp_path / "forensics")
    mon = monitor_bus.session(INCIDENT)
    inv = forensics_bus.session(INCIDENT)
    try:
        # 1. Monitor alerts the council.
        alert = mon.build(
            message_type="INCIDENT_ALERT",
            sender="monitor",
            recipients=["forensics"],
            payload={"severity": "HIGH", "summary": "synthetic suspicious login"},
        )
        sent_alert = mon.send(alert)
        received_alert = inv.receive(timeout_s=10.0)
        assert received_alert.message_id == sent_alert.message_id

        # 2. Forensics requests evidence (correlation-threaded reply).
        request = inv.build_reply(
            received_alert,
            message_type="EVIDENCE_REQUEST",
            sender="forensics",
            payload={"query": "authentication logs"},
        )
        sent_request = inv.send(request)
        received_request = mon.receive(timeout_s=10.0)
        assert received_request.message_id == sent_request.message_id

        # 3. Monitor responds with evidence.
        response = mon.build_reply(
            received_request,
            message_type="EVIDENCE_RESPONSE",
            sender="monitor",
            payload={"evidence_ids": ["EV-HTTP-1"]},
        )
        sent_response = mon.send(response)
        received_response = inv.receive(timeout_s=10.0)
        assert received_response.message_id == sent_response.message_id

        # 4. Forensics advances the round and publishes a finding.
        inv.advance_round()
        finding = inv.build_reply(
            received_response,
            message_type="FINDING",
            sender="forensics",
            payload={"summary": "credential misuse suspected", "confidence": 0.82},
        )
        sent_finding = inv.send(finding)
        received_finding = mon.receive(timeout_s=10.0)
        assert received_finding.message_id == sent_finding.message_id

        # Verified from both sides: full correlation-threaded exchange.
        expected_types = [
            "INCIDENT_ALERT",
            "EVIDENCE_REQUEST",
            "EVIDENCE_RESPONSE",
            "FINDING",
        ]
        for side in (mon, inv):
            thread = side.history.query(correlation_id=sent_alert.message_id)
            assert [m.message_type.value for m in thread] == expected_types
            assert all(m.incident_id == INCIDENT for m in thread)
        rounds = [m.round for m in mon.history.query(correlation_id=sent_alert.message_id)]
        assert rounds == [0, 0, 0, 1]

        # Both histories persisted the full exchange as JSONL.
        monitor_file = tmp_path / "monitor" / f"{INCIDENT}.jsonl"
        forensics_file = tmp_path / "forensics" / f"{INCIDENT}.jsonl"
        assert len(monitor_file.read_text(encoding="utf-8").splitlines()) == 4
        assert len(forensics_file.read_text(encoding="utf-8").splitlines()) == 4
    finally:
        monitor_bus.close()
        forensics_bus.close()
