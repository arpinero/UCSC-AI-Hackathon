"""Investigation engine tests: happy path, weak model, bounds, escalation."""

from __future__ import annotations

import pytest

from contracts.tools import ToolInvocation
from forensics.inference.mock import MockInferenceBackend
from forensics.reasoning.investigation import InvestigationEngine
from forensics.reasoning.validation import EvidenceFabricationError, validate_findings
from forensics.tools.mock import build_mock_registry
from tests.unit.reasoning.helpers import (
    INCIDENT,
    ScriptedBackend,
    make_evidence,
    make_findings,
    make_request,
)


def _three_evidence():
    # Deliberately shuffled: timestamps are 12:00, 12:20, 12:10.
    return [
        make_evidence("EV-1003", minutes=10, description="Suspicious process on web-01"),
        make_evidence("EV-1001", minutes=0),
        make_evidence("EV-1002", minutes=20, description="web-01 reached db-01 over SSH"),
    ]


def test_happy_path_cites_only_real_evidence_and_orders_timeline():
    evidence = _three_evidence()
    valid_ids = {e.evidence_id for e in evidence}
    backend = ScriptedBackend(
        [
            # step 1: model directs a build_timeline call over one evidence id
            {
                "tool_name": "build_timeline",
                "arguments": {"incident_id": INCIDENT, "evidence_ids": ["EV-1001"]},
            },
            # step 2: model signals completion
            {"tool_name": "finish", "arguments": {}},
            # synthesis: valid model findings citing real evidence
            {
                "agent_id": "forensics-agent",
                "incident_id": INCIDENT,
                "round": 1,
                "findings": "Lateral movement from web-01 to db-01 confirmed.",
                "cited_evidence_ids": ["EV-1001", "EV-1002"],
                "confidence": 0.8,
                "uncertainties": [],
                "timeline": [],
                "recommended_actions": ["Isolate web-01 from the network"],
            },
        ]
    )
    engine = InvestigationEngine(backend, build_mock_registry())
    findings = engine.investigate(make_request(), evidence)

    assert findings.cited_evidence_ids == ["EV-1001", "EV-1002"]
    assert set(findings.cited_evidence_ids) <= valid_ids
    assert findings.incident_id == INCIDENT
    assert findings.agent_id == "forensics-agent"
    assert findings.round == 1
    assert findings.confidence == 0.8
    # model path taken: no fallback note
    assert not any("fallback" in u for u in findings.uncertainties)

    # timeline: strictly ordered, only real evidence ids
    timestamps = [e.timestamp for e in findings.timeline]
    assert timestamps == sorted(timestamps)
    assert len(findings.timeline) == 3
    for event in findings.timeline:
        assert set(event.evidence_ids) <= valid_ids

    # bounded, audited tool use
    invocations = engine.last_invocations
    assert len(invocations) == 1
    assert isinstance(invocations[0], ToolInvocation)
    assert invocations[0].tool_name == "build_timeline"
    assert invocations[0].incident_id == INCIDENT
    assert invocations[0].duration_ms >= 0
    assert invocations[0].error is None


def test_weak_model_fallback_still_produces_valid_findings():
    evidence = _three_evidence()
    backend = MockInferenceBackend(fail_structured=True)
    engine = InvestigationEngine(backend, build_mock_registry())
    findings = engine.investigate(make_request(), evidence)

    assert findings.cited_evidence_ids == ["EV-1001", "EV-1002", "EV-1003"]
    assert "Deterministic fallback" in findings.findings
    assert any("fallback" in u for u in findings.uncertainties)
    timestamps = [e.timestamp for e in findings.timeline]
    assert timestamps == sorted(timestamps)
    # deterministic plan ran: build_timeline then search_logs
    names = [i.tool_name for i in engine.last_invocations]
    assert names == ["build_timeline", "search_logs"]


def test_invalid_tool_selection_falls_back_to_rule_based_plan():
    evidence = _three_evidence()
    backend = ScriptedBackend([{"tool_name": "not_a_real_tool", "arguments": {}}])
    engine = InvestigationEngine(backend, build_mock_registry())
    findings = engine.investigate(make_request(), evidence)

    names = [i.tool_name for i in engine.last_invocations]
    assert names[0] == "build_timeline"  # rule-based fallback engaged
    assert set(findings.cited_evidence_ids) <= {e.evidence_id for e in evidence}


def test_no_evidence_means_low_confidence_and_escalation():
    engine = InvestigationEngine(
        MockInferenceBackend(fail_structured=True), build_mock_registry()
    )
    findings = engine.investigate(make_request(), [])

    assert findings.confidence <= 0.1
    assert findings.cited_evidence_ids == []
    assert findings.uncertainties
    assert any("scal" in a.lower() for a in findings.recommended_actions)
    assert findings.severity_assessment is not None
    assert findings.severity_assessment.value == "INFO"


def test_thin_evidence_is_low_confidence_with_uncertainties():
    evidence = [make_evidence("EV-1001")]
    engine = InvestigationEngine(
        MockInferenceBackend(fail_structured=True), build_mock_registry()
    )
    findings = engine.investigate(make_request(), evidence)

    assert findings.confidence <= 0.4
    assert findings.uncertainties
    assert any("scal" in a.lower() for a in findings.recommended_actions)


def test_tool_calls_are_bounded_by_max_steps():
    script = [
        {
            "tool_name": "search_logs",
            "arguments": {"incident_id": INCIDENT, "query": f"probe-{i}"},
        }
        for i in range(20)
    ]
    engine = InvestigationEngine(ScriptedBackend(script), build_mock_registry())
    engine.investigate(make_request(), _three_evidence())

    assert len(engine.last_invocations) == 8  # default max_steps


def test_fabricated_citation_fails_loudly_in_validation():
    findings = make_findings(cited=["EV-DOES-NOT-EXIST"])
    with pytest.raises(EvidenceFabricationError):
        validate_findings(findings, [make_evidence("EV-1001")])


def test_engine_never_publishes_fabricated_model_citations():
    evidence = _three_evidence()
    backend = ScriptedBackend(
        [
            {"tool_name": "finish", "arguments": {}},
            {
                "agent_id": "forensics-agent",
                "incident_id": INCIDENT,
                "round": 1,
                "findings": "Model hallucinated a conclusion.",
                "cited_evidence_ids": ["EV-MADE-UP"],
                "confidence": 0.9,
            },
        ]
    )
    engine = InvestigationEngine(backend, build_mock_registry())
    findings = engine.investigate(make_request(), evidence)

    assert "EV-MADE-UP" not in findings.cited_evidence_ids
    assert set(findings.cited_evidence_ids) <= {e.evidence_id for e in evidence}
    assert any("fallback" in u for u in findings.uncertainties)

