"""Final recommendation and report submission tests."""

from __future__ import annotations

from contracts.common import Position
from contracts.tools import SubmitIncidentReportArgs
from forensics.inference.mock import MockInferenceBackend
from forensics.reasoning.report import ReportRecommender, ensure_submitted
from forensics.tools.mock import build_mock_registry
from tests.unit.reasoning.helpers import (
    INCIDENT,
    make_findings,
    make_position,
)


def test_supportive_position_produces_submit_ready_payload():
    findings = make_findings(cited=["EV-1001"], confidence=0.8, severity="HIGH")
    position = make_position(Position.SUPPORT, supporting=["EV-1001"])
    recommender = ReportRecommender(MockInferenceBackend())

    report = recommender.recommend(findings, position)

    assert report.escalation is False
    assert report.escalation_reason is None
    assert report.position_taken == Position.SUPPORT
    assert report.recommended_actions == ["Isolate web-01 from the network"]
    assert report.incident_id == INCIDENT
    # payload is a valid submit_incident_report request
    args = SubmitIncidentReportArgs.model_validate(report.report_payload)
    assert args.incident_id == INCIDENT
    assert args.severity_assessment.value == "HIGH"
    assert args.cited_evidence_ids == ["EV-1001"]
    assert args.recommended_actions == ["Isolate web-01 from the network"]


def test_abstention_path_escalates():
    findings = make_findings(cited=["EV-1001"], confidence=0.8)
    position = make_position(Position.ABSTAIN)
    recommender = ReportRecommender(MockInferenceBackend())

    report = recommender.recommend(findings, position)

    assert report.escalation is True
    assert report.escalation_reason is not None
    assert "abstained" in report.escalation_reason
    assert any("scal" in a.lower() for a in report.recommended_actions)
    SubmitIncidentReportArgs.model_validate(report.report_payload)


def test_low_confidence_findings_escalate():
    findings = make_findings(cited=["EV-1001"], confidence=0.1)
    position = make_position(Position.SUPPORT, supporting=["EV-1001"])
    recommender = ReportRecommender(MockInferenceBackend())

    report = recommender.recommend(findings, position)

    assert report.escalation is True
    assert "confidence is low" in (report.escalation_reason or "")


def test_uncited_findings_escalate():
    findings = make_findings(cited=[], confidence=0.8)
    position = make_position(Position.SUPPORT)
    recommender = ReportRecommender(MockInferenceBackend())

    report = recommender.recommend(findings, position)

    assert report.escalation is True
    assert "no evidence is cited" in (report.escalation_reason or "")


def test_submit_produces_audited_invocation():
    findings = make_findings(cited=["EV-1001"], confidence=0.8)
    position = make_position(Position.SUPPORT, supporting=["EV-1001"])
    recommender = ReportRecommender(MockInferenceBackend())
    report = recommender.recommend(findings, position)

    invocation = recommender.submit(report, build_mock_registry())

    assert invocation.error is None
    assert invocation.tool_name == "submit_incident_report"
    assert invocation.incident_id == INCIDENT
    assert invocation.result is not None
    assert invocation.result["report_id"] == f"RPT-MOCK-{INCIDENT}"
    assert invocation.duration_ms >= 0
    ensure_submitted(invocation)  # does not raise
