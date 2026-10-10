"""Investigation contracts: requests, findings, timeline, and debate positions."""

from __future__ import annotations

from pydantic import BaseModel, Field

from contracts.common import (
    Confidence,
    FrozenModelConfig,
    NonEmptyString,
    NonNegativeInt,
    Position,
    Severity,
    UTCDateTime,
)


class InvestigationRequest(BaseModel):
    """A question the council asks the forensics agent to investigate."""

    model_config = FrozenModelConfig.model_config

    request_id: NonEmptyString
    incident_id: NonEmptyString
    round: NonNegativeInt
    question: NonEmptyString
    available_evidence_ids: list[NonEmptyString] = Field(default_factory=list)
    requested_by: NonEmptyString


class TimelineEvent(BaseModel):
    """One reconstructed event on the incident timeline."""

    model_config = FrozenModelConfig.model_config

    timestamp: UTCDateTime
    description: NonEmptyString
    evidence_ids: list[NonEmptyString] = Field(default_factory=list)
    host_id: NonEmptyString | None = None
    event_type: NonEmptyString | None = None


class InvestigationFindings(BaseModel):
    """Findings published by the forensics agent after investigating."""

    model_config = FrozenModelConfig.model_config

    agent_id: NonEmptyString
    incident_id: NonEmptyString
    round: NonNegativeInt
    findings: NonEmptyString = Field(description="Summary of what was determined")
    cited_evidence_ids: list[NonEmptyString] = Field(default_factory=list)
    confidence: Confidence
    uncertainties: list[str] = Field(default_factory=list)
    timeline: list[TimelineEvent] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)
    severity_assessment: Severity | None = None


class DebatePosition(BaseModel):
    """The forensics agent's position on a proposal under debate."""

    model_config = FrozenModelConfig.model_config

    agent_id: NonEmptyString
    incident_id: NonEmptyString
    round: NonNegativeInt
    position: Position
    supporting_evidence_ids: list[NonEmptyString] = Field(default_factory=list)
    opposing_evidence_ids: list[NonEmptyString] = Field(default_factory=list)
    reasoning: NonEmptyString
    confidence: Confidence
    conditions_to_change_position: list[str] = Field(
        default_factory=list,
        description="What new evidence/fact would change this position",
    )


class PositionRevision(BaseModel):
    """An explicit revision of a previously published debate position.

    Preserves the audit trail: previous position, new position, the evidence
    that triggered the change, and an explanation.
    """

    model_config = FrozenModelConfig.model_config

    agent_id: NonEmptyString
    incident_id: NonEmptyString
    round: NonNegativeInt
    previous_position: DebatePosition
    new_position: DebatePosition
    triggering_evidence_ids: list[NonEmptyString] = Field(default_factory=list)
    explanation: NonEmptyString
