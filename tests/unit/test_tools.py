"""Forensic tool interface tests using mock tools."""

from __future__ import annotations

import pytest

from forensics.tools.base import ToolRegistry
from forensics.tools.mock import MockSlowTool, MockSubmitIncidentReport, build_mock_registry

EXPECTED = [
    "build_timeline",
    "enrich_ip",
    "get_host_context",
    "get_user_context",
    "lookup_mitre_technique",
    "search_logs",
    "submit_incident_report",
]

VALID_ARGS = {
    "search_logs": {"incident_id": "INC-1", "query": "powershell"},
    "get_host_context": {"host_id": "web-01"},
    "get_user_context": {"user_id": "jdoe"},
    "lookup_mitre_technique": {"technique_id": "T1003"},
    "enrich_ip": {"ip": "203.0.113.50"},
    "build_timeline": {"incident_id": "INC-1", "evidence_ids": ["EV-1"]},
    "submit_incident_report": {
        "incident_id": "INC-1",
        "findings_summary": "summary",
        "confidence": 0.7,
        "severity_assessment": "HIGH",
    },
}


def test_seven_tools_registered():
    assert build_mock_registry().names() == EXPECTED


@pytest.mark.parametrize("name", EXPECTED)
def test_valid_invocation(name):
    inv = build_mock_registry().get(name).invoke(VALID_ARGS[name], "INC-1")
    assert inv.error is None, inv.error
    assert inv.result is not None
    assert inv.tool_name == name
    assert inv.duration_ms >= 0


@pytest.mark.parametrize("name", EXPECTED)
def test_invalid_arguments_return_structured_error(name):
    inv = build_mock_registry().get(name).invoke({"bogus": 1}, "INC-1")
    assert inv.result is None
    assert inv.error is not None and inv.error.error_code == "INVALID_ARGUMENTS"


def test_search_logs_references_evidence():
    inv = build_mock_registry().get("search_logs").invoke(VALID_ARGS["search_logs"], "INC-1")
    assert inv.referenced_evidence_ids == ["EV-MOCK-0001"]


def test_only_report_tool_writes():
    registry = build_mock_registry()
    writers = [n for n in registry.names() if not registry.get(n).read_only]
    assert writers == ["submit_incident_report"]
    assert isinstance(registry.get("submit_incident_report"), MockSubmitIncidentReport)


def test_timeout_returns_retriable_error():
    inv = MockSlowTool().invoke(VALID_ARGS["search_logs"], "INC-1")
    assert inv.error is not None and inv.error.error_code == "TIMEOUT"
    assert inv.error.retriable is True


def test_registry_duplicate_and_unknown():
    registry = build_mock_registry()
    with pytest.raises(ValueError):
        registry.register(registry.get("search_logs"))
    with pytest.raises(KeyError):
        registry.get("nope")
    assert isinstance(registry, ToolRegistry)


def test_tool_specs_export():
    specs = build_mock_registry().as_tool_specs()
    assert [s["name"] for s in specs] == EXPECTED
    assert all("properties" in s["parameters"] for s in specs)
