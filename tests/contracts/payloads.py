"""Shared valid example payloads for contract tests and documentation."""

from __future__ import annotations

TS = "2026-10-10T12:00:00+00:00"


def incident_payload() -> dict:
    return {
        "incident_id": "INC-001",
        "scenario_id": "SCN-exfil-001",
        "created_at": TS,
        "severity": "HIGH",
        "affected_hosts": ["web-01"],
        "initial_description": "Suspicious outbound transfer",
        "current_status": "OPEN",
    }


def evidence_payload() -> dict:
    return {
        "evidence_id": "EV-0001",
        "incident_id": "INC-001",
        "source": "zeek-conn-log",
        "event_type": "network_flow",
        "timestamp": TS,
        "host_id": "web-01",
        "description": "2.1GB outbound to 203.0.113.50",
        "raw_data": {"bytes": 2254857830},
        "collected_at": TS,
    }


def findings_payload() -> dict:
    return {
        "agent_id": "forensics-agent",
        "incident_id": "INC-001",
        "round": 1,
        "findings": "Data exfiltration from web-01",
        "cited_evidence_ids": ["EV-0001"],
        "confidence": 0.85,
        "uncertainties": ["Destination ownership unconfirmed"],
        "timeline": [
            {"timestamp": TS, "description": "Transfer began", "evidence_ids": ["EV-0001"]}
        ],
        "recommended_actions": ["Block 203.0.113.50"],
    }


def position_payload() -> dict:
    return {
        "agent_id": "forensics-agent",
        "incident_id": "INC-001",
        "round": 1,
        "position": "SUPPORT",
        "supporting_evidence_ids": ["EV-0001"],
        "reasoning": "Evidence confirms exfiltration",
        "confidence": 0.8,
        "conditions_to_change_position": ["Transfer proven to be a sanctioned backup"],
    }


def council_message_payload() -> dict:
    return {
        "message_id": "M-1",
        "incident_id": "INC-001",
        "round": 1,
        "sender": "forensics-agent",
        "recipients": ["containment-agent"],
        "message_type": "FINDING",
        "timestamp": TS,
        "payload": {"findings": "x"},
        "correlation_id": "REQ-1",
    }


def request_payload() -> dict:
    return {
        "request_id": "REQ-1",
        "incident_id": "INC-001",
        "round": 0,
        "question": "Was data exfiltrated?",
        "available_evidence_ids": ["EV-0001"],
        "requested_by": "containment-agent",
    }


def tool_invocation_payload() -> dict:
    return {
        "invocation_id": "inv-1",
        "incident_id": "INC-001",
        "tool_name": "search_logs",
        "arguments": {"query": "x"},
        "result": {"entries": []},
        "referenced_evidence_ids": [],
        "error": None,
        "duration_ms": 12,
    }
