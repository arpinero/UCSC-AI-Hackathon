"""Mock implementations of the seven forensic tools (interface validation only).

These return fixed synthetic data. They are NOT investigation functionality.
The real implementations belong to tools-engineer in Stage B.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel

from contracts.investigation import TimelineEvent
from contracts.tools import (
    BuildTimelineArgs,
    BuildTimelineResult,
    EnrichIPArgs,
    EnrichIPResult,
    GetHostContextArgs,
    GetHostContextResult,
    GetUserContextArgs,
    GetUserContextResult,
    LogEntry,
    LookupMitreTechniqueArgs,
    LookupMitreTechniqueResult,
    MitreTechniqueInfo,
    SearchLogsArgs,
    SearchLogsResult,
    SubmitIncidentReportArgs,
    SubmitIncidentReportResult,
)
from forensics.tools.base import ForensicTool, ToolRegistry

_MOCK_TS = datetime(2026, 10, 10, 12, 0, 0, tzinfo=timezone.utc)


class MockSearchLogs(ForensicTool):
    name = "search_logs"
    description = "Search incident logs (mock)."
    args_model = SearchLogsArgs
    result_model = SearchLogsResult

    def run(self, args: Any) -> BaseModel:
        return SearchLogsResult(
            entries=[
                LogEntry(
                    timestamp=_MOCK_TS,
                    host_id=args.host_id or "web-01",
                    source="mock-syslog",
                    message=f"[mock] match for {args.query}",
                    evidence_id="EV-MOCK-0001",
                )
            ],
            matched_evidence_ids=["EV-MOCK-0001"],
        )


class MockGetHostContext(ForensicTool):
    name = "get_host_context"
    description = "Get host context (mock)."
    args_model = GetHostContextArgs
    result_model = GetHostContextResult

    def run(self, args: Any) -> BaseModel:
        return GetHostContextResult(host_id=args.host_id, hostname="mock-host", os="linux")


class MockGetUserContext(ForensicTool):
    name = "get_user_context"
    description = "Get user context (mock)."
    args_model = GetUserContextArgs
    result_model = GetUserContextResult

    def run(self, args: Any) -> BaseModel:
        return GetUserContextResult(user_id=args.user_id, display_name="Mock User")


class MockLookupMitre(ForensicTool):
    name = "lookup_mitre_technique"
    description = "Look up a MITRE ATT&CK technique (mock)."
    args_model = LookupMitreTechniqueArgs
    result_model = LookupMitreTechniqueResult

    def run(self, args: Any) -> BaseModel:
        return LookupMitreTechniqueResult(
            technique=MitreTechniqueInfo(
                technique_id=args.technique_id,
                name="Mock Technique",
                tactics=["credential-access"],
                description="[mock] technique description",
            )
        )


class MockEnrichIP(ForensicTool):
    name = "enrich_ip"
    description = "Enrich an IP address (mock)."
    args_model = EnrichIPArgs
    result_model = EnrichIPResult

    def run(self, args: Any) -> BaseModel:
        return EnrichIPResult(ip=args.ip, reputation="unknown", is_internal=False)


class MockBuildTimeline(ForensicTool):
    name = "build_timeline"
    description = "Build an incident timeline from evidence (mock)."
    args_model = BuildTimelineArgs
    result_model = BuildTimelineResult

    def run(self, args: Any) -> BaseModel:
        return BuildTimelineResult(
            timeline=[
                TimelineEvent(
                    timestamp=_MOCK_TS,
                    description="[mock] event",
                    evidence_ids=list(args.evidence_ids),
                )
            ]
        )


class MockSubmitIncidentReport(ForensicTool):
    name = "submit_incident_report"
    description = "Submit an incident report (mock; the only writing tool)."
    args_model = SubmitIncidentReportArgs
    result_model = SubmitIncidentReportResult
    read_only = False

    def run(self, args: Any) -> BaseModel:
        return SubmitIncidentReportResult(
            report_id=f"RPT-MOCK-{args.incident_id}", incident_id=args.incident_id
        )


class MockSlowTool(MockSearchLogs):
    """Sleeps longer than its timeout; used to test timeout handling."""

    name = "search_logs"
    timeout_s = 0.05

    def run(self, args: Any) -> BaseModel:
        time.sleep(0.5)
        return super().run(args)


def build_mock_registry() -> ToolRegistry:
    """Registry containing all seven mock tools."""
    registry = ToolRegistry()
    for tool in (
        MockSearchLogs(),
        MockGetHostContext(),
        MockGetUserContext(),
        MockLookupMitre(),
        MockEnrichIP(),
        MockBuildTimeline(),
        MockSubmitIncidentReport(),
    ):
        registry.register(tool)
    return registry
