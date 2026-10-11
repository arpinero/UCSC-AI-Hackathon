#!/usr/bin/env python3
"""Reproducible demonstration of one synthetic incident investigation cycle.

Wires the injected components (Stage A mock inference backend + mock tool
registry + engine harness) through the forensics-api HTTP service on an
ephemeral 127.0.0.1 port and prints the council message sequence. After
the coordinator merges the real components, re-point `build_engine()` at
the real backend/registry/engine and this demo runs unchanged.

Usage (from the repository root, venv activated):
    python scripts/demo_scenario.py
"""

from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from contracts.messages import CouncilMessage  # noqa: E402
from forensics.api.service import ForensicsService  # noqa: E402
from forensics.inference.mock import MockInferenceBackend  # noqa: E402
from forensics.tools.mock import build_mock_registry  # noqa: E402
from tests.end_to_end.harness import MockInvestigationEngine  # noqa: E402
from tests.integration.scenario import (  # noqa: E402
    EVIDENCE_ID_2,
    INCIDENT_ID,
    make_evidence,
    make_incident,
    make_request,
)


def build_engine() -> MockInvestigationEngine:
    """Swap point: Stage A mocks now, real components after merges."""
    return MockInvestigationEngine(
        backend=MockInferenceBackend(), registry=build_mock_registry()
    )


def main() -> int:
    print("== forensics-agent demo scenario (synthetic data only) ==")
    sequence: list[CouncilMessage] = []

    def record(message: CouncilMessage) -> None:
        sequence.append(message)
        print(
            f"  [{len(sequence):02d}] {message.message_type.value:<16}"
            f" round={message.round} incident={message.incident_id}"
            f" correlation={message.correlation_id or '-'}"
        )

    engine = build_engine()
    service = ForensicsService(engine=engine, transport=record, port=0)
    base = f"http://127.0.0.1:{service.start()}"

    def post(path: str, payload: dict[str, Any]) -> dict[str, Any]:
        request = urllib.request.Request(
            base + path,
            data=json.dumps(payload).encode("utf-8"),
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            body: dict[str, Any] = json.loads(response.read().decode("utf-8"))
            return body

    try:
        print("step 1: incident alert received")
        post("/incidents", make_incident())

        print("step 2: council requests an investigation")
        findings = post("/investigations", make_request())["findings"]
        print(f"    findings: {findings['findings']}")
        print(f"    cited evidence: {findings['cited_evidence_ids']}")

        print("step 3: council proposes isolating web-01")
        position = post(
            "/proposals",
            {"incident_id": INCIDENT_ID, "round": 2, "proposal": {"action": "isolate web-01"}},
        )["position"]
        print(f"    position: {position['position']} (confidence {position['confidence']})")

        print("step 4: contradicting evidence arrives")
        outcome = post(
            "/evidence",
            make_evidence(
                EVIDENCE_ID_2, description="Backup schedule shows transfer was sanctioned"
            ),
        )
        if outcome["revised"]:
            revision = outcome["revision"]
            print(
                f"    revision: {revision['previous_position']['position']} ->"
                f" {revision['new_position']['position']}"
                f" (triggered by {revision['triggering_evidence_ids']})"
            )
        else:
            print("    no position change")

        print("step 5: tool invocation audit trail")
        for invocation in engine.tool_audit:
            status = "ok" if invocation.error is None else f"error:{invocation.error.error_code}"
            print(
                f"    {invocation.tool_name:<22} {status:<8}"
                f" {invocation.duration_ms}ms evidence={invocation.referenced_evidence_ids}"
            )
    finally:
        service.stop()

    print(f"== council message sequence: {len(sequence)} messages, service shut down ==")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
