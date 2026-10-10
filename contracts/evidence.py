"""Evidence contract: security evidence with stable IDs and provenance."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from contracts.common import FrozenModelConfig, NonEmptyString, UTCDateTime


class Evidence(BaseModel):
    """A single piece of security evidence attached to an incident.

    Evidence IDs are stable: once published, an ID must always refer to the
    same evidence. `source` and `collected_at` provide explicit provenance.
    """

    model_config = FrozenModelConfig.model_config

    evidence_id: NonEmptyString = Field(description="Stable unique evidence identifier")
    incident_id: NonEmptyString
    source: NonEmptyString = Field(description="Provenance: where the evidence came from")
    event_type: NonEmptyString = Field(description="e.g. process_execution, network_flow")
    timestamp: UTCDateTime = Field(description="UTC time the underlying event occurred")
    host_id: NonEmptyString
    description: NonEmptyString
    raw_data: dict[str, Any] = Field(
        default_factory=dict, description="Structured raw payload (serializable)"
    )
    collected_at: UTCDateTime = Field(description="UTC time the evidence was collected")
    collection_tool: NonEmptyString | None = Field(
        default=None, description="Tool that produced this evidence, if any"
    )


class EvidenceAcknowledgement(BaseModel):
    """Optional receipt confirming evidence was received by an agent."""

    model_config = FrozenModelConfig.model_config

    evidence_id: NonEmptyString
    incident_id: NonEmptyString
    acknowledged_by: NonEmptyString
    acknowledged_at: datetime | None = None
