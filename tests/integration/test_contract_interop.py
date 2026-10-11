"""Cross-component integration tests against the frozen v1 contracts.

Proves the contracts interoperate using ONLY Stage A components available
on this branch (mock inference backend, mock tool registry): an
InvestigationRequest drives the registry, evidence ids flow across
contracts, findings/positions/revisions validate, and every tool call
produces a ToolInvocation audit record that round-trips.
"""

from __future__ import annotations

import pytest

from contracts.evidence import Evidence, EvidenceAcknowledgement
from contracts.incident import Incident
from contracts.inference import ToolSpec
from contracts.investigation import (
    DebatePosition,
    InvestigationFindings,
    InvestigationRequest,
    PositionRevision,
    TimelineEvent,
)
from contracts.tools import SubmitIncidentReportArgs, ToolInvocation
from tests.integration import scenario

ALL_TOOLS = [
    "build_timeline",
    "enrich_ip",
    "get_host_context",
    "get_user_context",
    "lookup_mitre_technique",
    "search_logs",
    "submit_incident_report",
]

VALID_ARGS = {
    "search_logs": {"incident_id": scenario.INCIDENT_ID, "query": "outbound 203.0.113.50"},
    "get_host_context": {"host_id": "web-01", "incident_id": scenario.INCIDENT_ID},
    "get_user_context": {"user_id": "jdoe", "incident_id": scenario.INCIDENT_ID},
    "lookup_mitre_technique": {"technique_id": "T1041"},
    "enrich_ip": {"ip": "203.0.113.50", "incident_id": scenario.INCIDENT_ID},
    "build_timeline": {
        "incident_id": scenario.INCIDENT_ID,
        "evidence_ids": [scenario.EVIDENCE_ID],
    },
    "submit_incident_report": {
        "incident_id": scenario.INCIDENT_ID,
        "findings_summary": "Confirmed exfiltration",
        "cited_evidence_ids": [scenario.EVIDENCE_ID],
        "confidence": 0.85,
        "severity_assessment": "HIGH",
    },
}


def test_incident_and_evidence_fixtures_validate():
    incident = Incident.model_validate(scenario.make_incident())
    evidence = Evidence.model_validate(scenario.make_evidence())
    assert incident.incident_id == evidence.incident_id
    ack = EvidenceAcknowledgement(
        evidence_id=evidence.evidence_id,
        incident_id=evidence.incident_id,
        acknowledged_by="forensics-agent",
    )
    assert EvidenceAcknowledgement.model_validate_json(ack.model_dump_json()) == ack


def test_request_drives_mock_registry_and_produces_audit_records(registry):
    request = InvestigationRequest.model_validate(scenario.make_request())
    invocation = registry.get("search_logs").invoke(
        {"incident_id": request.incident_id, "query": request.question}, request.incident_id
    )
    # Audit record validates and round-trips through the frozen contract.
    record = ToolInvocation.model_validate_json(invocation.model_dump_json())
    assert record.error is None
    assert record.tool_name == "search_logs"
    assert record.incident_id == request.incident_id
    assert record.duration_ms >= 0
    assert record.referenced_evidence_ids, "search_logs must reference evidence ids"


def test_tool_evidence_ids_flow_into_findings(registry):
    request = InvestigationRequest.model_validate(scenario.make_request())
    invocation = registry.get("search_logs").invoke(
        {"incident_id": request.incident_id, "query": request.question}, request.incident_id
    )
    cited = sorted(set(request.available_evidence_ids) | set(invocation.referenced_evidence_ids))
    findings = InvestigationFindings.model_validate(scenario.make_findings(cited))
    assert findings.cited_evidence_ids == cited
    assert scenario.EVIDENCE_ID in findings.cited_evidence_ids


def test_build_timeline_result_feeds_findings_timeline(registry):
    args = VALID_ARGS["build_timeline"]
    built = registry.get("build_timeline").invoke(args, scenario.INCIDENT_ID)
    assert built.error is None and built.result is not None
    events = [TimelineEvent.model_validate(event) for event in built.result["timeline"]]
    payload = scenario.make_findings([scenario.EVIDENCE_ID])
    payload["timeline"] = [event.model_dump(mode="json") for event in events]
    findings = InvestigationFindings.model_validate(payload)
    assert findings.timeline and findings.timeline[0].evidence_ids == [scenario.EVIDENCE_ID]


@pytest.mark.parametrize("tool_name", ALL_TOOLS)
def test_every_mock_tool_produces_valid_audit_record(registry, tool_name):
    invocation = registry.get(tool_name).invoke(VALID_ARGS[tool_name], scenario.INCIDENT_ID)
    assert invocation.error is None, invocation.error
    record = ToolInvocation.model_validate_json(invocation.model_dump_json())
    assert record.tool_name == tool_name


def test_registry_tool_specs_accepted_by_inference_contract(registry):
    specs = [ToolSpec.model_validate(spec) for spec in registry.as_tool_specs()]
    assert len(specs) == len(ALL_TOOLS)
    assert all(spec.parameters.get("type") == "object" for spec in specs)


def test_findings_flow_into_report_submission(registry):
    findings = InvestigationFindings.model_validate(scenario.make_findings([scenario.EVIDENCE_ID]))
    args = SubmitIncidentReportArgs.model_validate(
        {
            "incident_id": findings.incident_id,
            "findings_summary": findings.findings,
            "cited_evidence_ids": findings.cited_evidence_ids,
            "confidence": findings.confidence,
            "severity_assessment": findings.severity_assessment or "HIGH",
            "recommended_actions": findings.recommended_actions,
        }
    )
    invocation = registry.get("submit_incident_report").invoke(
        args.model_dump(mode="json"), findings.incident_id
    )
    assert invocation.error is None, invocation.error
    assert invocation.result is not None
    assert invocation.result["report_id"]


def test_evidence_ids_flow_through_position_and_revision():
    position = DebatePosition.model_validate(scenario.make_position_payload("SUPPORT", round=2))
    assert position.supporting_evidence_ids == [scenario.EVIDENCE_ID]
    revision = PositionRevision.model_validate(scenario.make_revision_payload())
    assert revision.previous_position.position.value == "SUPPORT"
    assert revision.new_position.position.value == "OPPOSE"
    assert revision.triggering_evidence_ids == [scenario.EVIDENCE_ID_2]
    assert PositionRevision.model_validate_json(revision.model_dump_json()) == revision
