"""Forensic tool contracts: typed inputs/outputs for the seven forensic tools.

Interfaces only — no investigation functionality is implemented in Stage A.
All tools are read-only with respect to incident state, except
submit_incident_report which creates a report artifact.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from contracts.common import (
    Confidence,
    FrozenModelConfig,
    NonEmptyString,
    NonNegativeInt,
    Severity,
    UTCDateTime,
)
from contracts.investigation import TimelineEvent


class ToolError(BaseModel):
    """Structured error returned by a forensic tool invocation."""

    model_config = FrozenModelConfig.model_config

    error_code: NonEmptyString = Field(description="Machine-readable error code")
    message: NonEmptyString = Field(description="Human-readable explanation")
    retriable: bool = False


class ToolInvocation(BaseModel):
    """Audit record of one forensic tool invocation."""

    model_config = FrozenModelConfig.model_config

    invocation_id: NonEmptyString
    incident_id: NonEmptyString
    tool_name: NonEmptyString
    arguments: dict[str, Any] = Field(default_factory=dict)
    result: dict[str, Any] | None = None
    referenced_evidence_ids: list[NonEmptyString] = Field(default_factory=list)
    error: ToolError | None = None
    duration_ms: NonNegativeInt = Field(description="Wall-clock duration, must be >= 0")


# --- search_logs -----------------------------------------------------------


class SearchLogsArgs(BaseModel):
    model_config = FrozenModelConfig.model_config

    incident_id: NonEmptyString
    query: NonEmptyString
    host_id: NonEmptyString | None = None
    start: UTCDateTime | None = None
    end: UTCDateTime | None = None
    limit: int = Field(default=50, ge=1, le=1000)


class LogEntry(BaseModel):
    model_config = FrozenModelConfig.model_config

    timestamp: UTCDateTime
    host_id: NonEmptyString
    source: NonEmptyString
    message: NonEmptyString
    evidence_id: NonEmptyString | None = None


class SearchLogsResult(BaseModel):
    model_config = FrozenModelConfig.model_config

    entries: list[LogEntry] = Field(default_factory=list)
    matched_evidence_ids: list[NonEmptyString] = Field(default_factory=list)
    truncated: bool = False


# --- get_host_context ------------------------------------------------------


class GetHostContextArgs(BaseModel):
    model_config = FrozenModelConfig.model_config

    host_id: NonEmptyString
    incident_id: NonEmptyString | None = None


class GetHostContextResult(BaseModel):
    model_config = FrozenModelConfig.model_config

    host_id: NonEmptyString
    hostname: NonEmptyString | None = None
    os: NonEmptyString | None = None
    criticality: NonEmptyString | None = None
    services: list[str] = Field(default_factory=list)
    recent_alerts: list[str] = Field(default_factory=list)
    notes: str = ""


# --- get_user_context ------------------------------------------------------


class GetUserContextArgs(BaseModel):
    model_config = FrozenModelConfig.model_config

    user_id: NonEmptyString
    incident_id: NonEmptyString | None = None


class GetUserContextResult(BaseModel):
    model_config = FrozenModelConfig.model_config

    user_id: NonEmptyString
    display_name: NonEmptyString | None = None
    roles: list[str] = Field(default_factory=list)
    groups: list[str] = Field(default_factory=list)
    mfa_enabled: bool | None = None
    anomalies: list[str] = Field(default_factory=list)


# --- lookup_mitre_technique ------------------------------------------------


class LookupMitreTechniqueArgs(BaseModel):
    model_config = FrozenModelConfig.model_config

    technique_id: NonEmptyString = Field(description="e.g. T1003, T1566.001")


class MitreTechniqueInfo(BaseModel):
    model_config = FrozenModelConfig.model_config

    technique_id: NonEmptyString
    name: NonEmptyString
    tactics: list[str] = Field(default_factory=list)
    description: NonEmptyString
    platform: list[str] = Field(default_factory=list)


class LookupMitreTechniqueResult(BaseModel):
    model_config = FrozenModelConfig.model_config

    technique: MitreTechniqueInfo | None = None
    found: bool = True


# --- enrich_ip -------------------------------------------------------------


class EnrichIPArgs(BaseModel):
    model_config = FrozenModelConfig.model_config

    ip: NonEmptyString
    incident_id: NonEmptyString | None = None


class EnrichIPResult(BaseModel):
    model_config = FrozenModelConfig.model_config

    ip: NonEmptyString
    asn: NonEmptyString | None = None
    country: NonEmptyString | None = None
    reputation: NonEmptyString | None = Field(
        default=None, description="e.g. benign | suspicious | malicious | unknown"
    )
    known_threat_labels: list[str] = Field(default_factory=list)
    is_internal: bool | None = None


# --- build_timeline --------------------------------------------------------


class BuildTimelineArgs(BaseModel):
    model_config = FrozenModelConfig.model_config

    incident_id: NonEmptyString
    evidence_ids: list[NonEmptyString] = Field(min_length=1)


class BuildTimelineResult(BaseModel):
    model_config = FrozenModelConfig.model_config

    timeline: list[TimelineEvent] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list, description="Unexplained gaps/unknowns")


# --- submit_incident_report ------------------------------------------------


class SubmitIncidentReportArgs(BaseModel):
    """The only tool that writes: it creates a report artifact."""

    model_config = FrozenModelConfig.model_config

    incident_id: NonEmptyString
    findings_summary: NonEmptyString
    cited_evidence_ids: list[NonEmptyString] = Field(default_factory=list)
    confidence: Confidence
    severity_assessment: Severity
    recommended_actions: list[str] = Field(default_factory=list)


class SubmitIncidentReportResult(BaseModel):
    model_config = FrozenModelConfig.model_config

    report_id: NonEmptyString
    incident_id: NonEmptyString
    status: NonEmptyString = Field(default="SUBMITTED")

