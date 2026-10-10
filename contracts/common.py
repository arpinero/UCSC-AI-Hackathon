"""Shared building blocks for all Forensics contracts.

CONTRACTS ARE FROZEN AT v1. Changes require a CONTRACT_CHANGE_REQUEST and
coordinator approval (see docs/OWNERSHIP.md).
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Annotated, Any

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints

# Version of the contract suite as a whole.
CONTRACTS_VERSION = "1.0.0"


class FrozenModelConfig:
    """Strict base config shared by every contract model."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")
    return value.astimezone(timezone.utc)


UTCDateTime = Annotated[datetime, AfterValidator(_ensure_utc)]

NonEmptyString = Annotated[str, StringConstraints(min_length=1)]

Confidence = Annotated[float, Field(ge=0.0, le=1.0)]

NonNegativeInt = Annotated[int, Field(ge=0)]


class Severity(str, Enum):
    """Incident severity levels."""

    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


class IncidentStatus(str, Enum):
    """Lifecycle of an incident from the council's point of view."""

    OPEN = "OPEN"
    INVESTIGATING = "INVESTIGATING"
    CONTAINED = "CONTAINED"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


class Position(str, Enum):
    """Stance an agent takes on a proposal under debate."""

    SUPPORT = "SUPPORT"
    OPPOSE = "OPPOSE"
    ABSTAIN = "ABSTAIN"


def utc_now() -> datetime:
    """Current UTC time (helper for deterministic tests)."""
    return datetime.now(timezone.utc)


def json_schema_export(models: list[type[BaseModel]]) -> dict[str, Any]:
    """Export JSON Schemas for a list of contract model classes."""
    return {model.__name__: model.model_json_schema() for model in models}
