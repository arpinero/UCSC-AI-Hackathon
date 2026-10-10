"""Council message contract: runtime inter-agent messaging envelopes.

These are RUNTIME cybersecurity-council messages, entirely separate from the
coding-agent coordination bus in the `coordination/` package.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from contracts.common import FrozenModelConfig, NonEmptyString, UTCDateTime


class CouncilMessageType(str, Enum):
    """Message types exchanged by council agents at runtime."""

    INCIDENT_ALERT = "INCIDENT_ALERT"
    EVIDENCE_REQUEST = "EVIDENCE_REQUEST"
    EVIDENCE_RESPONSE = "EVIDENCE_RESPONSE"
    FINDING = "FINDING"
    PROPOSAL = "PROPOSAL"
    CHALLENGE = "CHALLENGE"
    REVISION = "REVISION"
    VOTE = "VOTE"
    ESCALATION = "ESCALATION"


class CouncilMessage(BaseModel):
    """Envelope for one runtime council message.

    REQUIRES TEAM AGREEMENT: envelope shape and message-type semantics must
    be shared by Containment/Recovery/Compliance agents.
    """

    model_config = FrozenModelConfig.model_config

    message_id: NonEmptyString
    incident_id: NonEmptyString
    round: int = Field(ge=0, description="Debate round this message belongs to")
    sender: NonEmptyString = Field(description="Sending agent identity")
    recipients: list[NonEmptyString] = Field(min_length=1)
    message_type: CouncilMessageType
    timestamp: UTCDateTime
    payload: dict[str, Any] = Field(
        default_factory=dict, description="Type-specific structured payload"
    )
    correlation_id: NonEmptyString | None = Field(
        default=None, description="Links replies to the message they answer"
    )
    delivered_at: datetime | None = Field(default=None)
