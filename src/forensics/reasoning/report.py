"""Final recommendation and incident-report payload assembly.

``ReportRecommender.recommend`` turns validated findings plus the forensics
agent's debate position into recommended actions and a report payload suitable
for the ``submit_incident_report`` tool, including explicit abstention and
escalation paths. ``submit`` executes the (only writing) tool through the
registry so every submission is an audited ``ToolInvocation``.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from contracts.common import Position, Severity
from contracts.inference import ChatMessage, InferenceRequest
from contracts.investigation import DebatePosition, InvestigationFindings
from contracts.tools import SubmitIncidentReportArgs, ToolError, ToolInvocation
from forensics.inference.base import InferenceBackend
from forensics.tools.base import ToolRegistry

_ESCALATION_ACTIONS = [
    "Escalate to human incident responders for manual analysis before any "
    "automated action",
    "Request additional evidence collection (host telemetry, network flows, "
    "identity logs)",
    "Take no irreversible containment action until the position is "
    "evidence-supported",
]


class RecommendedReport(BaseModel):
    """The output of a recommendation: actions + submit-ready payload."""

    incident_id: str
    position_taken: Position
    recommended_actions: list[str]
    report_payload: dict[str, Any]
    escalation: bool
    escalation_reason: str | None = None
    narrative: str = ""


class ReportRecommender:
    """Produces final recommendations and submit_incident_report payloads."""

    def __init__(
        self,
        backend: InferenceBackend,
        *,
        agent_id: str = "forensics-agent",
        escalation_confidence: float = 0.35,
    ) -> None:
        self.backend = backend
        self.agent_id = agent_id
        self.escalation_confidence = escalation_confidence

    def recommend(
        self, findings: InvestigationFindings, position: DebatePosition
    ) -> RecommendedReport:
        """Recommend actions and a report payload from findings + position."""
        escalate = (
            position.position == Position.ABSTAIN
            or findings.confidence <= self.escalation_confidence
            or not findings.cited_evidence_ids
        )
        if escalate:
            reasons: list[str] = []
            if position.position == Position.ABSTAIN:
                reasons.append("the forensics agent abstained (insufficient evidence)")
            if findings.confidence <= self.escalation_confidence:
                reasons.append(
                    f"investigation confidence is low ({findings.confidence})"
                )
            if not findings.cited_evidence_ids:
                reasons.append("no evidence is cited")
            escalation_reason = "Escalation required because " + "; ".join(reasons) + "."
            actions = list(_ESCALATION_ACTIONS)
            severity = findings.severity_assessment or Severity.INFO
        else:
            escalation_reason = None
            actions = [a for a in findings.recommended_actions if a.strip()]
            if not actions:
                actions = [
                    "Review the cited evidence and corroborate the findings "
                    "across additional telemetry sources"
                ]
            severity = findings.severity_assessment or Severity.MEDIUM
        cited = list(dict.fromkeys(findings.cited_evidence_ids))
        for evidence_id in position.supporting_evidence_ids:
            if evidence_id not in cited:
                cited.append(evidence_id)
        summary = f"{findings.findings} Position taken: {position.position.value}."
        report_payload: dict[str, Any] = {
            "incident_id": findings.incident_id,
            "findings_summary": summary,
            "cited_evidence_ids": cited,
            "confidence": findings.confidence,
            "severity_assessment": severity,
            "recommended_actions": actions,
        }
        # Guarantee the payload is a valid submit_incident_report request.
        SubmitIncidentReportArgs.model_validate(report_payload)
        return RecommendedReport(
            incident_id=findings.incident_id,
            position_taken=position.position,
            recommended_actions=actions,
            report_payload=report_payload,
            escalation=escalate,
            escalation_reason=escalation_reason,
            narrative=self._narrative(findings, position),
        )

    def submit(
        self, report: RecommendedReport, registry: ToolRegistry
    ) -> ToolInvocation:
        """Submit ``report`` via the ``submit_incident_report`` tool.

        The only writing tool; the invocation is recorded as an audit record.
        Raises ``KeyError`` if the registry has no such tool.
        """
        tool = registry.get("submit_incident_report")
        return tool.invoke(report.report_payload, report.incident_id)

    def _narrative(
        self, findings: InvestigationFindings, position: DebatePosition
    ) -> str:
        """Best-effort narrative summary; deterministic fallback on failure."""
        fallback = (
            f"Report assembled from validated findings and the "
            f"{position.position.value} debate position; all cited evidence "
            "was verified as provided."
        )
        try:
            result = self.backend.generate(
                InferenceRequest(
                    messages=[
                        ChatMessage(
                            role="user",
                            content=(
                                "Summarize this incident report in two factual "
                                f"sentences. Findings: {findings.findings[:1000]} "
                                f"Position: {position.position.value}. "
                                f"Reasoning: {position.reasoning[:500]}"
                            ),
                        )
                    ]
                )
            )
        except Exception:
            return fallback
        text = result.text.strip()
        return text if text else fallback


def ensure_submitted(invocation: ToolInvocation) -> None:
    """Raise ``ValueError`` if a report submission failed."""
    if invocation.error is not None:
        error: ToolError = invocation.error
        raise ValueError(
            f"submit_incident_report failed ({error.error_code}): {error.message}"
        )

