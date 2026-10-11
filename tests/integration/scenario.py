"""Synthetic incident-scenario fixtures for integration and end-to-end tests.

All data is fully synthetic (mirrors docs/schema_export.json examples) and
validates against the frozen v1 contracts. No real systems are involved.
"""

from __future__ import annotations

from typing import Any

from contracts.messages import CouncilMessageType

TS = "2026-10-10T12:00:00+00:00"

INCIDENT_ID = "INC-2026-001"
EVIDENCE_ID = "EV-INC-2026-001-0001"
EVIDENCE_ID_2 = "EV-INC-2026-001-0002"
REQUEST_ID = "REQ-INC-2026-001-1"


def make_incident() -> dict[str, Any]:
    """Synthetic HIGH-severity exfiltration incident."""
    return {
        "incident_id": INCIDENT_ID,
        "scenario_id": "SCN-exfil-001",
        "created_at": TS,
        "severity": "HIGH",
        "affected_hosts": ["web-01"],
        "initial_description": "Suspicious 2.1GB outbound transfer from web-01",
        "current_status": "OPEN",
    }


def make_evidence(
    evidence_id: str = EVIDENCE_ID,
    description: str = "2.1GB outbound to 203.0.113.50 over 443",
) -> dict[str, Any]:
    """Synthetic zeek network-flow evidence attached to the incident."""
    return {
        "evidence_id": evidence_id,
        "incident_id": INCIDENT_ID,
        "source": "zeek-conn-log",
        "event_type": "network_flow",
        "timestamp": TS,
        "host_id": "web-01",
        "description": description,
        "raw_data": {"bytes": 2254857830, "dest_port": 443},
        "collected_at": TS,
        "collection_tool": "search_logs",
    }


def make_request() -> dict[str, Any]:
    """Investigation request from the containment agent."""
    return {
        "request_id": REQUEST_ID,
        "incident_id": INCIDENT_ID,
        "round": 1,
        "question": "Was data exfiltrated from web-01, and how?",
        "available_evidence_ids": [EVIDENCE_ID],
        "requested_by": "containment-agent",
    }


def make_findings(cited_evidence_ids: list[str]) -> dict[str, Any]:
    """Findings that cite the given evidence ids (validated downstream)."""
    return {
        "agent_id": "forensics-agent",
        "incident_id": INCIDENT_ID,
        "round": 1,
        "findings": "Confirmed exfiltration to 203.0.113.50 via HTTPS over 40 minutes",
        "cited_evidence_ids": cited_evidence_ids,
        "confidence": 0.85,
        "uncertainties": ["Destination ownership unconfirmed"],
        "timeline": [],
        "recommended_actions": ["Block 203.0.113.50 at egress"],
        "severity_assessment": "HIGH",
    }


def make_position_payload(position: str = "SUPPORT", round: int = 2) -> dict[str, Any]:  # noqa: A002
    """DebatePosition payload (also used inside REVISION council payloads)."""
    return {
        "agent_id": "forensics-agent",
        "incident_id": INCIDENT_ID,
        "round": round,
        "position": position,
        "supporting_evidence_ids": [EVIDENCE_ID] if position == "SUPPORT" else [],
        "opposing_evidence_ids": [EVIDENCE_ID_2] if position == "OPPOSE" else [],
        "reasoning": "Isolation preserves evidence and stops ongoing exfiltration",
        "confidence": 0.8,
        "conditions_to_change_position": ["Transfer proven to be a sanctioned backup"],
    }


def make_revision_payload() -> dict[str, Any]:
    """PositionRevision payload: SUPPORT -> OPPOSE after new evidence."""
    return {
        "agent_id": "forensics-agent",
        "incident_id": INCIDENT_ID,
        "round": 3,
        "previous_position": make_position_payload("SUPPORT", round=2),
        "new_position": make_position_payload("OPPOSE", round=3),
        "triggering_evidence_ids": [EVIDENCE_ID_2],
        "explanation": "Backup schedule evidence shows the transfer was sanctioned",
    }


def council_payload(message_type: CouncilMessageType) -> dict[str, Any]:
    """Type-specific structured payload for one council message type."""
    if message_type is CouncilMessageType.INCIDENT_ALERT:
        return {
            "incident": make_incident(),
            "summary": "Suspicious 2.1GB outbound transfer from web-01",
        }
    if message_type is CouncilMessageType.EVIDENCE_REQUEST:
        return {
            "question": "Was data exfiltrated from web-01, and how?",
            "requested_by": "containment-agent",
            "available_evidence_ids": [EVIDENCE_ID],
        }
    if message_type is CouncilMessageType.EVIDENCE_RESPONSE:
        return {"evidence": [make_evidence()], "acknowledged_by": "forensics-agent"}
    if message_type is CouncilMessageType.FINDING:
        return {
            "findings": "Confirmed exfiltration to 203.0.113.50 via HTTPS over 40 minutes",
            "cited_evidence_ids": [EVIDENCE_ID],
            "confidence": 0.85,
        }
    if message_type is CouncilMessageType.PROPOSAL:
        return {
            "proposal_id": "PRP-INC-2026-001-1",
            "proposed_by": "containment-agent",
            "action": "isolate web-01",
            "rationale": "Stop ongoing exfiltration",
        }
    if message_type is CouncilMessageType.CHALLENGE:
        return {
            "challenged_message_id": "PRP-INC-2026-001-1",
            "reason": "Isolation may destroy volatile evidence on web-01",
            "requested_evidence_ids": [EVIDENCE_ID_2],
        }
    if message_type is CouncilMessageType.REVISION:
        return {"revision": make_revision_payload()}
    if message_type is CouncilMessageType.VOTE:
        return {"position": "SUPPORT", "confidence": 0.8, "reasoning": "Exfiltration confirmed"}
    return {
        "reason": "Destination ownership unconfirmed; cannot rule out sanctioned backup",
        "escalated_to": ["human-on-call"],
        "urgency": "HIGH",
    }


def make_council_message(
    message_type: CouncilMessageType,
    *,
    message_id: str = "CM-2026-0001",
    round: int = 1,  # noqa: A002
    sender: str = "forensics-agent",
    recipients: list[str] | None = None,
    correlation_id: str | None = None,
) -> dict[str, Any]:
    """Full CouncilMessage envelope with a structured type-specific payload."""
    return {
        "message_id": message_id,
        "incident_id": INCIDENT_ID,
        "round": round,
        "sender": sender,
        "recipients": recipients or ["containment-agent"],
        "message_type": message_type.value,
        "timestamp": TS,
        "payload": council_payload(message_type),
        "correlation_id": correlation_id,
    }

