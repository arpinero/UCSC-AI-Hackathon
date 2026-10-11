"""Genuine (mock-free) SLIM exchange over the AGNTCY ``slim-bindings`` wheel.

VERIFIED on this machine: aarch64 + Python 3.12, slim-bindings==2.2.0 from
PyPI, insecure in-process SLIM server on 127.0.0.1 (ephemeral port) with
two point-to-point apps. The test skips cleanly when the optional wheel is
absent (e.g. in the shared dev venv) — run it in an environment where
``pip install slim-bindings`` succeeded to exercise it for real.
"""

from __future__ import annotations

import pytest

pytest.importorskip(
    "slim_bindings",
    reason="optional dependency 'slim-bindings' (verified: 2.2.0 on aarch64) not installed",
)

from forensics.messaging.base import CouncilBus  # noqa: E402
from forensics.messaging.envelopes import (  # noqa: E402
    MessagingError,
)
from forensics.messaging.slim_transport import (  # noqa: E402
    SlimLocalServer,
    SlimTransport,
)

# Synthetic, dev-only shared secret (>= 32 bytes required by SLIM HMAC).
SECRET = "synthetic-shared-secret-for-tests-only-0123456789abcdef"
INCIDENT = "INC-SLIM-1"


def test_short_shared_secret_rejected():
    with pytest.raises(MessagingError, match="too short"):
        SlimTransport("probe", "http://127.0.0.1:1", "short-secret")


def test_genuine_slim_exchange_full_flow(tmp_path):
    """Real SLIM exchange: INCIDENT_ALERT -> EVIDENCE_REQUEST -> EVIDENCE_RESPONSE -> FINDING."""
    with SlimLocalServer() as server:
        monitor = SlimTransport("monitor", server.url, SECRET)
        forensics = SlimTransport("forensics", server.url, SECRET)
        try:
            monitor_bus = CouncilBus(monitor, history_dir=tmp_path / "monitor")
            forensics_bus = CouncilBus(forensics, history_dir=tmp_path / "forensics")
            mon = monitor_bus.session(INCIDENT)
            inv = forensics_bus.session(INCIDENT)

            alert = mon.build(
                message_type="INCIDENT_ALERT",
                sender="monitor",
                recipients=["forensics"],
                payload={"severity": "HIGH", "summary": "synthetic suspicious login"},
            )
            sent_alert = mon.send(alert)
            received_alert = inv.receive(timeout_s=30.0)
            assert received_alert.message_id == sent_alert.message_id

            request = inv.build_reply(
                received_alert,
                message_type="EVIDENCE_REQUEST",
                sender="forensics",
                payload={"query": "authentication logs"},
            )
            sent_request = inv.send(request)
            received_request = mon.receive(timeout_s=30.0)
            assert received_request.message_id == sent_request.message_id

            response = mon.build_reply(
                received_request,
                message_type="EVIDENCE_RESPONSE",
                sender="monitor",
                payload={"evidence_ids": ["EV-SLIM-1"]},
            )
            sent_response = mon.send(response)
            received_response = inv.receive(timeout_s=30.0)
            assert received_response.message_id == sent_response.message_id

            inv.advance_round()
            finding = inv.build_reply(
                received_response,
                message_type="FINDING",
                sender="forensics",
                payload={"summary": "credential misuse suspected", "confidence": 0.82},
            )
            sent_finding = inv.send(finding)
            received_finding = mon.receive(timeout_s=30.0)
            assert received_finding.message_id == sent_finding.message_id

            expected_types = [
                "INCIDENT_ALERT",
                "EVIDENCE_REQUEST",
                "EVIDENCE_RESPONSE",
                "FINDING",
            ]
            for side in (mon, inv):
                thread = side.history.query(correlation_id=sent_alert.message_id)
                assert [m.message_type.value for m in thread] == expected_types
            assert (tmp_path / "forensics" / f"{INCIDENT}.jsonl").exists()
            assert (tmp_path / "monitor" / f"{INCIDENT}.jsonl").exists()
        finally:
            monitor.close()
            forensics.close()
