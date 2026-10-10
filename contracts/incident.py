"""Incident contract: the shared unit of work for the whole council."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from contracts.common import (
    FrozenModelConfig,
    IncidentStatus,
    NonEmptyString,
    Severity,
    UTCDateTime,
)


class Incident(BaseModel):
    """A cyber incident under investigation by the council.

    REQUIRES TEAM AGREEMENT: field names, severity levels, and status values
    must match what Containment/Recovery/Compliance agents emit.
    """

    model_config = FrozenModelConfig.model_config

    incident_id: NonEmptyString = Field(description="Stable unique incident identifier")
    scenario_id: NonEmptyString = Field(description="Synthetic scenario the incident belongs to")
    created_at: UTCDateTime = Field(description="UTC creation time of the incident record")
    severity: Severity = Field(description="Incident severity")
    affected_hosts: list[NonEmptyString] = Field(default_factory=list)
    initial_description: NonEmptyString
    current_status: IncidentStatus = IncidentStatus.OPEN
    updated_at: datetime | None = Field(
        default=None, description="Optional UTC time of last status change"
    )
