#!/usr/bin/env python3
"""Export JSON Schemas and valid examples for every shared contract.

Writes docs/schema_export.json. Run from the repository root:
    python scripts/export_schemas.py   (needs pydantic; use the project venv)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from contracts.common import CONTRACTS_VERSION, json_schema_export  # noqa: E402
from contracts.evidence import Evidence  # noqa: E402
from contracts.incident import Incident  # noqa: E402
from contracts.investigation import (  # noqa: E402
    DebatePosition,
    InvestigationFindings,
    InvestigationRequest,
    PositionRevision,
)
from contracts.messages import CouncilMessage  # noqa: E402
from contracts.tools import ToolInvocation  # noqa: E402

TS = "2026-10-10T12:00:00+00:00"

EXAMPLES: dict[str, dict] = {
    "Incident": {
        "incident_id": "INC-2026-001",
        "scenario_id": "SCN-exfil-001",
        "created_at": TS,
        "severity": "HIGH",
        "affected_hosts": ["web-01"],
        "initial_description": "Suspicious 2.1GB outbound transfer from web-01",
        "current_status": "OPEN",
    },
    "Evidence": {
        "evidence_id": "EV-INC-2026-001-0001",
        "incident_id": "INC-2026-001",
        "source": "zeek-conn-log",
        "event_type": "network_flow",
        "timestamp": TS,
        "host_id": "web-01",
        "description": "2.1GB outbound to 203.0.113.50 over 443",
        "raw_data": {"bytes": 2254857830, "dest_port": 443},
        "collected_at": TS,
        "collection_tool": "search_logs",
    },
    "CouncilMessage": {
        "message_id": "CM-2026-0001",
        "incident_id": "INC-2026-001",
        "round": 1,
        "sender": "forensics-agent",
        "recipients": ["containment-agent"],
        "message_type": "FINDING",
        "timestamp": TS,
        "payload": {"summary": "Exfiltration confirmed; see cited evidence"},
        "correlation_id": "CM-2026-0000",
    },
    "InvestigationRequest": {
        "request_id": "REQ-INC-2026-001-1",
        "incident_id": "INC-2026-001",
        "round": 1,
        "question": "Was data exfiltrated from web-01, and how?",
        "available_evidence_ids": ["EV-INC-2026-001-0001"],
        "requested_by": "containment-agent",
    },
    "InvestigationFindings": {
        "agent_id": "forensics-agent",
        "incident_id": "INC-2026-001",
        "round": 1,
        "findings": "Confirmed exfiltration to 203.0.113.50 via HTTPS over 40 minutes",
        "cited_evidence_ids": ["EV-INC-2026-001-0001"],
        "confidence": 0.85,
        "uncertainties": ["Destination ownership unconfirmed"],
        "timeline": [
            {
                "timestamp": TS,
                "description": "Transfer began",
                "evidence_ids": ["EV-INC-2026-001-0001"],
            }
        ],
        "recommended_actions": ["Block 203.0.113.50 at egress"],
        "severity_assessment": "HIGH",
    },
    "DebatePosition": {
        "agent_id": "forensics-agent",
        "incident_id": "INC-2026-001",
        "round": 2,
        "position": "SUPPORT",
        "supporting_evidence_ids": ["EV-INC-2026-001-0001"],
        "opposing_evidence_ids": [],
        "reasoning": "Isolation preserves evidence and stops ongoing exfiltration",
        "confidence": 0.8,
        "conditions_to_change_position": ["Transfer proven to be a sanctioned backup"],
    },
    "PositionRevision": {
        "agent_id": "forensics-agent",
        "incident_id": "INC-2026-001",
        "round": 3,
        "previous_position": None,  # filled below to keep the example readable
        "new_position": None,
        "triggering_evidence_ids": ["EV-INC-2026-001-0002"],
        "explanation": "Backup schedule evidence shows the transfer was sanctioned",
    },
    "ToolInvocation": {
        "invocation_id": "inv-20261010-000001",
        "incident_id": "INC-2026-001",
        "tool_name": "search_logs",
        "arguments": {"incident_id": "INC-2026-001", "query": "outbound 203.0.113.50"},
        "result": {
            "entries": [],
            "matched_evidence_ids": ["EV-INC-2026-001-0001"],
            "truncated": False,
        },
        "referenced_evidence_ids": ["EV-INC-2026-001-0001"],
        "error": None,
        "duration_ms": 42,
    },
}

MODELS = [
    Incident, Evidence, CouncilMessage, InvestigationRequest, InvestigationFindings,
    DebatePosition, PositionRevision, ToolInvocation,
]


def main() -> int:
    examples = dict(EXAMPLES)
    position = dict(EXAMPLES["DebatePosition"])
    revision = dict(EXAMPLES["PositionRevision"])
    revision["previous_position"] = position
    revision["new_position"] = dict(position, position="OPPOSE", round=3)
    examples["PositionRevision"] = revision

    doc = {
        "contracts_version": CONTRACTS_VERSION,
        "status": "PROPOSED for cross-team integration; authoritative inside forensics-agent",
        "json_schemas": json_schema_export(MODELS),
        "valid_examples": {
            name: (MODELS[i].model_validate(examples[MODELS[i].__name__]).model_dump(mode="json"))
            for i, name in enumerate([m.__name__ for m in MODELS])
        },
    }
    out = Path(__file__).resolve().parents[1] / "docs" / "schema_export.json"
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n")
    print(f"wrote {out} ({out.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
