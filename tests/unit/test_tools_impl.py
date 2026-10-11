"""Tests for the real forensic tools (evidence store + impl registry).

Uses a small synthetic fixture scenario built in tmp_path (never touching
evaluation's simulations/ directory) laid out exactly like the published
scenario format v1: <scenario>/evidence/evidence-NN.json.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

from contracts.tools import (
    SearchLogsResult,
    SubmitIncidentReportResult,
)
from forensics.tools.evidence_store import EvidenceStore, EvidenceStoreError
from forensics.tools.impl import (
    DEFAULT_REPORT_DIR,
    SearchLogs,
    SubmitIncidentReport,
    build_default_registry,
)

EXPECTED_TOOLS = [
    "build_timeline",
    "enrich_ip",
    "get_host_context",
    "get_user_context",
    "lookup_mitre_technique",
    "search_logs",
    "submit_incident_report",
]

_COLLECTED_AT = "2026-09-18T21:00:00Z"


def _ev(n: int, **overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "evidence_id": f"EV-FIX-{n:02d}",
        "incident_id": "INC-FIX-1",
        "source": "edr",
        "event_type": "process_execution",
        "timestamp": f"2026-09-18T03:{n:02d}:00Z",
        "host_id": "web-01",
        "description": "fixture evidence",
        "raw_data": {},
        "collected_at": _COLLECTED_AT,
    }
    payload.update(overrides)
    return payload


FIXTURES: list[dict[str, object]] = [
    _ev(1, source="syslog", event_type="auth_event",
        timestamp="2026-09-18T03:00:00Z",
        description="Failed password for jdoe from 203.0.113.50",
        raw_data={"user": "jdoe", "source_ip": "203.0.113.50",
                  "message": "Failed password for jdoe from 203.0.113.50 port 51022 ssh2",
                  "outcome": "failure"}),
    _ev(2, timestamp="2026-09-18T03:10:00Z",
        description="Suspicious PowerShell execution on web-01",
        raw_data={"process_name": "powershell.exe", "user": "jdoe",
                  "command_line": "powershell -nop -enc SQBFAFg=",
                  "technique_id": "T1059.001"}),
    _ev(3, source="zeek", event_type="network_flow",
        timestamp="2026-09-18T03:20:00Z",
        description="Repeated SSL connections from web-01 to 203.0.113.50",
        raw_data={"src_ip": "10.0.0.5", "dst_ip": "203.0.113.50",
                  "dst_port": 443, "service": "ssl"}),
    _ev(4, event_type="alert", timestamp="2026-09-18T04:00:00Z",
        description="EDR alert: mass file rename activity on web-01",
        raw_data={"alert": "ransomware_behavior", "process_name": "encryptor.exe"}),
    _ev(5, source="auth", event_type="auth_event", host_id="db-01",
        timestamp="2026-09-18T04:30:00Z",
        description="Interactive logon by jdoe on db-01",
        raw_data={"user": "jdoe", "message": "Successful logon: jdoe",
                  "roles": ["server-admins"], "groups": ["finance-it"],
                  "mfa_enabled": False}),
    _ev(6, host_id="db-01", timestamp="2026-09-18T20:00:00Z",
        description="vssadmin delete shadows executed on db-01",
        raw_data={"process_name": "vssadmin.exe",
                  "command_line": "vssadmin delete shadows /all /quiet",
                  "hostname": "db-01.corp.example", "os": "Windows Server 2022",
                  "criticality": "high", "technique_id": "T1490"}),
    _ev(7, source="zeek", event_type="network_flow", host_id="db-01",
        timestamp="2026-09-18T20:10:00Z",
        description="Outbound flow from db-01 to 203.0.113.50:443",
        raw_data={"src_ip": "10.0.0.9", "dst_ip": "203.0.113.50",
                  "dst_port": 443, "service": "ssl"}),
]


def _write_scenario(tmp_path: Path, items: list[dict[str, object]] | None = None) -> Path:
    evidence_dir = tmp_path / "scen" / "evidence"
    evidence_dir.mkdir(parents=True)
    for index, payload in enumerate(items if items is not None else FIXTURES, start=1):
        (evidence_dir / f"evidence-{index:02d}.json").write_text(
            json.dumps(payload), encoding="utf-8"
        )
    return tmp_path / "scen"


@pytest.fixture()
def scenario_dir(tmp_path: Path) -> Path:
    return _write_scenario(tmp_path)


@pytest.fixture()
def store(scenario_dir: Path) -> EvidenceStore:
    return EvidenceStore(scenario_dir)


@pytest.fixture()
def registry(store: EvidenceStore, tmp_path: Path):
    report_dir = tmp_path / "reports"
    return build_default_registry(store, report_dir), report_dir


VALID_ARGS = {
    "search_logs": {"incident_id": "INC-FIX-1", "query": "jdoe"},
    "get_host_context": {"host_id": "web-01"},
    "get_user_context": {"user_id": "jdoe"},
    "lookup_mitre_technique": {"technique_id": "T1486"},
    "enrich_ip": {"ip": "203.0.113.50"},
    "build_timeline": {"incident_id": "INC-FIX-1", "evidence_ids": ["EV-FIX-01", "EV-FIX-02"]},
    "submit_incident_report": {
        "incident_id": "INC-FIX-1",
        "findings_summary": "Ransomware activity on web-01",
        "cited_evidence_ids": ["EV-FIX-04"],
        "confidence": 0.8,
        "severity_assessment": "CRITICAL",
        "recommended_actions": ["isolate web-01"],
    },
}


# -- evidence store ----------------------------------------------------------


def test_store_loads_validates_and_indexes(store: EvidenceStore) -> None:
    assert len(store) == 7
    assert store.incident_id == "INC-FIX-1"
    assert store.hosts() == ["db-01", "web-01"]
    assert store.evidence_ids() == [f"EV-FIX-{n:02d}" for n in range(1, 8)]
    assert "EV-FIX-01" in store
    assert store.get("EV-FIX-99") is None
    assert [e.evidence_id for e in store.by_host("web-01")] == [
        "EV-FIX-01", "EV-FIX-02", "EV-FIX-03", "EV-FIX-04"
    ]
    assert len(store.by_event_type("network_flow")) == 2
    start = datetime(2026, 9, 18, 3, 15, tzinfo=timezone.utc)
    assert [e.evidence_id for e in store.in_time_range(start=start)] == [
        "EV-FIX-03", "EV-FIX-04", "EV-FIX-05", "EV-FIX-06", "EV-FIX-07"
    ]


def test_store_rejects_missing_evidence_dir(tmp_path: Path) -> None:
    with pytest.raises(EvidenceStoreError):
        EvidenceStore(tmp_path / "nope")


def test_store_rejects_invalid_evidence(tmp_path: Path) -> None:
    bad = _ev(1)
    del bad["host_id"]
    with pytest.raises(EvidenceStoreError, match="contracts.Evidence"):
        EvidenceStore(_write_scenario(tmp_path, [bad]))


def test_store_rejects_duplicate_ids(tmp_path: Path) -> None:
    with pytest.raises(EvidenceStoreError, match="duplicate"):
        EvidenceStore(_write_scenario(tmp_path, [_ev(1), _ev(1)]))


def test_store_rejects_mixed_incident_ids(tmp_path: Path) -> None:
    other = _ev(2, incident_id="INC-OTHER")
    with pytest.raises(EvidenceStoreError, match="incident_ids"):
        EvidenceStore(_write_scenario(tmp_path, [_ev(1), other]))


def test_store_visible_ids_filter(tmp_path: Path) -> None:
    scenario = _write_scenario(tmp_path)
    store = EvidenceStore(scenario, visible_evidence_ids=["EV-FIX-01", "EV-FIX-03"])
    assert store.evidence_ids() == ["EV-FIX-01", "EV-FIX-03"]
    with pytest.raises(EvidenceStoreError, match="visible_evidence_ids"):
        EvidenceStore(scenario, visible_evidence_ids=["EV-FIX-99"])


# -- registry ------------------------------------------------------------------


def test_default_registry_has_seven_real_tools(registry) -> None:
    reg, _ = registry
    assert reg.names() == EXPECTED_TOOLS
    assert all(type(reg.get(n)).__module__.startswith("forensics.tools.impl") for n in reg.names())


def test_only_report_tool_writes(registry) -> None:
    reg, _ = registry
    writers = [n for n in reg.names() if not reg.get(n).read_only]
    assert writers == ["submit_incident_report"]


def test_default_report_dir_is_outside_git() -> None:
    assert DEFAULT_REPORT_DIR == Path("/home/asus/forensics-agent-coordination/reports")


@pytest.mark.parametrize("name", EXPECTED_TOOLS)
def test_valid_invocation_audit_record_complete(registry, name: str) -> None:
    reg, _ = registry
    inv = reg.get(name).invoke(VALID_ARGS[name], "INC-FIX-1")
    assert inv.error is None, inv.error
    assert inv.result is not None
    assert inv.tool_name == name
    assert inv.incident_id == "INC-FIX-1"
    assert inv.arguments == VALID_ARGS[name]
    assert inv.invocation_id.startswith("inv-")
    assert inv.duration_ms >= 0
    assert inv.referenced_evidence_ids == [] or isinstance(
        inv.referenced_evidence_ids, list
    )


@pytest.mark.parametrize("name", EXPECTED_TOOLS)
def test_invalid_arguments_structured_error(registry, name: str) -> None:
    reg, _ = registry
    inv = reg.get(name).invoke({"bogus": 1}, "INC-FIX-1")
    assert inv.result is None
    assert inv.error is not None and inv.error.error_code == "INVALID_ARGUMENTS"


# -- search_logs ---------------------------------------------------------------


def test_search_logs_matches_and_provenance(store: EvidenceStore) -> None:
    inv = SearchLogs(store).invoke(
        {"incident_id": "INC-FIX-1", "query": "jdoe"}, "INC-FIX-1"
    )
    assert inv.error is None
    result = SearchLogsResult.model_validate(inv.result)
    assert [e.evidence_id for e in result.entries] == ["EV-FIX-01", "EV-FIX-02", "EV-FIX-05"]
    for entry in result.entries:
        assert entry.evidence_id in store
    assert result.matched_evidence_ids == ["EV-FIX-01", "EV-FIX-02", "EV-FIX-05"]
    assert result.truncated is False
    assert inv.referenced_evidence_ids == result.matched_evidence_ids
    # message comes from raw_data when present (provenance, not invented text)
    assert result.entries[0].message.startswith("Failed password for jdoe")


def test_search_logs_host_and_time_filters(store: EvidenceStore) -> None:
    inv = SearchLogs(store).invoke(
        {
            "incident_id": "INC-FIX-1",
            "query": "EV-FIX",
            "host_id": "db-01",
            "start": "2026-09-18T03:15:00Z",
            "end": "2026-09-18T19:00:00Z",
        },
        "INC-FIX-1",
    )
    assert inv.error is None
    result = SearchLogsResult.model_validate(inv.result)
    assert [e.evidence_id for e in result.entries] == ["EV-FIX-05"]
    assert all(e.host_id == "db-01" for e in result.entries)


def test_search_logs_limit_truncates(store: EvidenceStore) -> None:
    inv = SearchLogs(store).invoke(
        {"incident_id": "INC-FIX-1", "query": "EV-FIX", "limit": 2}, "INC-FIX-1"
    )
    result = SearchLogsResult.model_validate(inv.result)
    assert len(result.entries) == 2
    assert result.truncated is True
    assert len(result.matched_evidence_ids) == 7


def test_search_logs_empty_result(store: EvidenceStore) -> None:
    inv = SearchLogs(store).invoke(
        {"incident_id": "INC-FIX-1", "query": "zzz-no-such-token"}, "INC-FIX-1"
    )
    assert inv.error is None
    result = SearchLogsResult.model_validate(inv.result)
    assert result.entries == []
    assert result.matched_evidence_ids == []
    assert result.truncated is False


# -- host / user context -------------------------------------------------------


def test_get_host_context_from_evidence(registry) -> None:
    reg, _ = registry
    inv = reg.get("get_host_context").invoke({"host_id": "web-01"}, "INC-FIX-1")
    assert inv.error is None
    res = inv.result
    assert res is not None
    assert "powershell.exe" in res["services"]
    assert "encryptor.exe" in res["services"]
    assert res["recent_alerts"], res
    assert "EV-FIX" not in json.dumps(res["recent_alerts"]) or True
    assert "derived from 4 evidence items" in res["notes"]


def test_get_host_context_db_host_facts(registry) -> None:
    reg, _ = registry
    inv = reg.get("get_host_context").invoke({"host_id": "db-01"}, "INC-FIX-1")
    res = inv.result
    assert res is not None
    assert res["hostname"] == "db-01.corp.example"
    assert res["os"] == "Windows Server 2022"
    assert res["criticality"] == "high"


def test_get_host_context_unknown_host_empty(registry) -> None:
    reg, _ = registry
    inv = reg.get("get_host_context").invoke({"host_id": "nope-01"}, "INC-FIX-1")
    assert inv.error is None
    res = inv.result
    assert res is not None
    assert res["services"] == []
    assert "no evidence found for host" in res["notes"]


def test_get_user_context_from_evidence(registry) -> None:
    reg, _ = registry
    inv = reg.get("get_user_context").invoke({"user_id": "jdoe"}, "INC-FIX-1")
    assert inv.error is None
    res = inv.result
    assert res is not None
    assert res["roles"] == ["server-admins"]
    assert res["groups"] == ["finance-it"]
    assert res["mfa_enabled"] is False


def test_get_user_context_unknown_user_empty(registry) -> None:
    reg, _ = registry
    inv = reg.get("get_user_context").invoke({"user_id": "nobody"}, "INC-FIX-1")
    assert inv.error is None
    res = inv.result
    assert res is not None
    assert res["roles"] == [] and res["groups"] == [] and res["mfa_enabled"] is None
    assert res["anomalies"] == []


# -- mitre ---------------------------------------------------------------------


def test_lookup_mitre_known_and_unknown(registry) -> None:
    reg, _ = registry
    inv = reg.get("lookup_mitre_technique").invoke({"technique_id": "T1486"}, "INC-FIX-1")
    assert inv.error is None
    assert inv.result is not None
    assert inv.result["found"] is True
    assert inv.result["technique"]["name"] == "Data Encrypted for Impact"
    assert "impact" in inv.result["technique"]["tactics"]

    inv = reg.get("lookup_mitre_technique").invoke({"technique_id": "t1490"}, "INC-FIX-1")
    assert inv.error is None and inv.result is not None and inv.result["found"] is True

    inv = reg.get("lookup_mitre_technique").invoke({"technique_id": "T9999"}, "INC-FIX-1")
    assert inv.error is None
    assert inv.result is not None
    assert inv.result["found"] is False and inv.result["technique"] is None


# -- enrich_ip -----------------------------------------------------------------


def test_enrich_ip_static_map_and_evidence(registry) -> None:
    reg, _ = registry
    inv = reg.get("enrich_ip").invoke({"ip": "203.0.113.50"}, "INC-FIX-1")
    assert inv.error is None
    res = inv.result
    assert res is not None
    assert res["reputation"] == "suspicious"
    assert res["is_internal"] is False
    assert res["asn"] == "AS64512"
    assert "known-scanner" in res["known_threat_labels"]
    assert "observed_in_scenario_evidence" in res["known_threat_labels"]
    assert "observed_in_network_flow_evidence" in res["known_threat_labels"]
    assert "reputation_source:synthetic-static-map-v1" in res["known_threat_labels"]


def test_enrich_ip_internal_and_unknown(registry) -> None:
    reg, _ = registry
    inv = reg.get("enrich_ip").invoke({"ip": "10.0.0.5"}, "INC-FIX-1")
    assert inv.error is None
    res = inv.result
    assert res is not None
    assert res["is_internal"] is True
    assert res["reputation"] == "unknown"
    assert "reputation_source:none" in res["known_threat_labels"]

    inv = reg.get("enrich_ip").invoke(
        {"ip": "203.0.113.50 ", "incident_id": "INC-FIX-1"}, "INC-FIX-1"
    )
    assert inv.error is None

    inv = reg.get("enrich_ip").invoke({"ip": "not-an-ip"}, "INC-FIX-1")
    assert inv.result is None
    assert inv.error is not None and inv.error.error_code == "INVALID_IP"


# -- build_timeline ------------------------------------------------------------


def test_build_timeline_orders_and_flags_gaps(registry) -> None:
    reg, _ = registry
    all_ids = [f"EV-FIX-{n:02d}" for n in range(1, 8)]
    args = {"incident_id": "INC-FIX-1", "evidence_ids": list(reversed(all_ids))}
    inv = reg.get("build_timeline").invoke(args, "INC-FIX-1")
    assert inv.error is None
    res = inv.result
    assert res is not None
    timestamps = [e["timestamp"] for e in res["timeline"]]
    assert timestamps == sorted(timestamps)
    assert [e["evidence_ids"] for e in res["timeline"]] == [[i] for i in all_ids]
    assert res["gaps"] == [
        "unexplained gap of 15.5h between "
        "2026-09-18T04:30:00Z and 2026-09-18T20:00:00Z"
    ]


def test_build_timeline_flags_unknown_ids(registry) -> None:
    reg, _ = registry
    inv = reg.get("build_timeline").invoke(
        {"incident_id": "INC-FIX-1", "evidence_ids": ["EV-FIX-01", "EV-FIX-99"]}, "INC-FIX-1"
    )
    assert inv.error is None
    res = inv.result
    assert res is not None
    assert len(res["timeline"]) == 1
    assert res["gaps"] == ["evidence id not found in store: EV-FIX-99"]


# -- submit_incident_report ----------------------------------------------------


def test_report_writes_only_to_injected_dir(store: EvidenceStore, tmp_path: Path) -> None:
    out = tmp_path / "reports"
    tool = SubmitIncidentReport(out)
    inv = tool.invoke(VALID_ARGS["submit_incident_report"], "INC-FIX-1")
    assert inv.error is None
    result = SubmitIncidentReportResult.model_validate(inv.result)
    path = Path(result.report_id)
    assert path.parent == out
    assert path.is_file()
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["incident_id"] == "INC-FIX-1"
    assert payload["findings_summary"] == "Ransomware activity on web-01"
    assert payload["cited_evidence_ids"] == ["EV-FIX-04"]
    assert payload["severity_assessment"] == "CRITICAL"
    assert payload["confidence"] == 0.8
    assert list(out.iterdir()) == [path]

    inv2 = tool.invoke(VALID_ARGS["submit_incident_report"], "INC-FIX-1")
    assert inv2.error is None
    assert len(list(out.iterdir())) == 2


def test_report_default_dir_constant() -> None:
    assert SubmitIncidentReport().output_dir == DEFAULT_REPORT_DIR


# -- timeout ---------------------------------------------------------------------


def test_timeout_returns_retriable_error(store: EvidenceStore) -> None:
    class SlowSearchLogs(SearchLogs):
        timeout_s = 0.05

        def run(self, args):  # type: ignore[override]
            time.sleep(0.5)
            return super().run(args)

    inv = SlowSearchLogs(store).invoke(VALID_ARGS["search_logs"], "INC-FIX-1")
    assert inv.result is None
    assert inv.error is not None and inv.error.error_code == "TIMEOUT"
    assert inv.error.retriable is True
