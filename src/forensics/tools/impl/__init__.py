"""Real implementations of the seven forensic tools (Stage B, tools-engineer).

Unlike the Stage A mocks (``forensics.tools.mock``), these tools operate on a
constructor-injected :class:`~forensics.tools.evidence_store.EvidenceStore`
and, for ``submit_incident_report``, a constructor-injected output directory.
Tool names match the mocks exactly so downstream code does not change.
"""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from forensics.tools.base import ToolRegistry
from forensics.tools.evidence_store import EvidenceStore
from forensics.tools.impl.enrich_ip import EnrichIP
from forensics.tools.impl.mitre import LookupMitreTechnique
from forensics.tools.impl.report import DEFAULT_REPORT_DIR, SubmitIncidentReport
from forensics.tools.impl.store_tools import (
    BuildTimeline,
    GetHostContext,
    GetUserContext,
    SearchLogs,
)

__all__ = [
    "DEFAULT_REPORT_DIR",
    "BuildTimeline",
    "EnrichIP",
    "GetHostContext",
    "GetUserContext",
    "LookupMitreTechnique",
    "SearchLogs",
    "SubmitIncidentReport",
    "build_default_registry",
]


def build_default_registry(
    store: EvidenceStore,
    output_dir: str | Path = DEFAULT_REPORT_DIR,
    *,
    mitre_mapping_path: str | Path | None = None,
    ip_reputation_path: str | Path | None = None,
    gap_threshold: timedelta = timedelta(hours=6),
) -> ToolRegistry:
    """Registry with the seven REAL tools over ``store``.

    ``output_dir`` is where ``submit_incident_report`` writes artifacts
    (default: the shared coordination reports dir, outside git). The static
    data paths and the timeline gap threshold are injectable for tests.
    """
    registry = ToolRegistry()
    for tool in (
        SearchLogs(store),
        GetHostContext(store),
        GetUserContext(store),
        LookupMitreTechnique(mitre_mapping_path),
        EnrichIP(store, ip_reputation_path),
        BuildTimeline(store, gap_threshold=gap_threshold),
        SubmitIncidentReport(output_dir),
    ):
        registry.register(tool)
    return registry
