"""Ground-truth schema for synthetic scenarios.

This is the scoring key for a scenario. It is deliberately NOT a frozen
contract: it lives under `simulations/` and is owned by `evaluation-engineer`.
The investigator-facing loader API never returns these objects.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from contracts.common import NonEmptyString, NonNegativeInt, Position, Severity, UTCDateTime

Classification = Literal["confirmed_incident", "suspicious_activity", "benign"]
"""Final classification of a scenario: was there really an incident?"""


class TimelineAnchor(BaseModel):
    """A timeline point a correct investigation should reconstruct (soft match)."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    timestamp: UTCDateTime
    host_id: str | None = None
    description_contains: str | None = None


class ExpectedPositionRevision(BaseModel):
    """A stance change a correct investigation must make (and only these)."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    previous_position: Position
    new_position: Position
    triggering_evidence_ids: list[NonEmptyString] = Field(default_factory=list)
    min_round: NonNegativeInt = 1


class GroundTruth(BaseModel):
    """The scoring key for one scenario (see simulations/FORMAT.md)."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    scenario_id: NonEmptyString
    incident_id: NonEmptyString
    classification: Classification
    expected_severity: Severity
    containment_proposal: NonEmptyString
    expected_stance: Position
    expected_findings: list[str] = Field(default_factory=list)
    must_cite_evidence_ids: list[NonEmptyString] = Field(default_factory=list)
    timeline_anchors: list[TimelineAnchor] = Field(default_factory=list)
    mitre_techniques: list[str] = Field(default_factory=list)
    evidence_reveal_rounds: dict[str, Annotated[int, Field(ge=1)]] = Field(
        default_factory=dict,
        description=(
            "evidence_id -> reveal_round; evidence is available in round N "
            "iff reveal_round <= N"
        ),
    )
    expected_position_revisions: list[ExpectedPositionRevision] = Field(default_factory=list)
    narrative: str = ""

    def reveal_round(self, evidence_id: str) -> int | None:
        """Round in which `evidence_id` becomes available, or None if unknown."""
        return self.evidence_reveal_rounds.get(evidence_id)

    @property
    def max_round(self) -> int:
        """Highest reveal round in the scenario (>= 1)."""
        return max(self.evidence_reveal_rounds.values(), default=1)
