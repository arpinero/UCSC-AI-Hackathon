"""Loader tests: every committed scenario validates against the frozen contracts."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from simulations.loader import (
    DEFAULT_SCENARIOS_ROOT,
    EvidenceStore,
    ScenarioFormatError,
    discover_scenario_dirs,
    load_all_bundles,
    load_evidence_store,
    load_scenario_bundle,
)

EXPECTED_SCENARIOS = {"ransom01", "lateral01", "exfil01"}
EXPECTED_SOURCES = {"syslog", "zeek", "edr", "auth"}


@pytest.fixture(scope="module")
def bundles():
    return load_all_bundles()


def test_all_committed_scenarios_present():
    dirs = discover_scenario_dirs()
    assert {p.name for p in dirs} == EXPECTED_SCENARIOS


def test_every_fixture_passes_contracts(bundles):
    assert {b.scenario_id for b in bundles} == EXPECTED_SCENARIOS
    for bundle in bundles:
        assert bundle.incident.severity in {"CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"}
        for item in bundle.evidence:
            # strict contract re-validation of the loaded objects
            assert item.model_validate_json(item.model_dump_json()) == item
        assert bundle.ground_truth.scenario_id == bundle.scenario_id


def test_scenario_shape(bundles):
    for bundle in bundles:
        assert 8 <= len(bundle.evidence) <= 15
        hosts = {e.host_id for e in bundle.evidence}
        assert 2 <= len(hosts) <= 3
        assert hosts.issubset(set(bundle.incident.affected_hosts))
        sources = {e.source for e in bundle.evidence}
        assert sources & EXPECTED_SOURCES, f"{bundle.scenario_id}: expected log sources"
        # timeline is reconstructable: strictly ordered timestamps exist
        timestamps = sorted(e.timestamp for e in bundle.evidence)
        assert len(set(timestamps)) >= len(timestamps) - 3  # nearly collision-free


def test_evidence_id_convention_unique_and_stable(bundles):
    for bundle in bundles:
        ids = bundle.evidence_ids
        assert len(set(ids)) == len(ids)
        for index, eid in enumerate(ids, start=1):
            assert eid == f"EV-{bundle.scenario_id}-{index:02d}"


def test_reveal_rounds_complete_and_monotonic(bundles):
    for bundle in bundles:
        rounds = bundle.ground_truth.evidence_reveal_rounds
        assert set(rounds) == set(bundle.evidence_ids)
        assert all(r >= 1 for r in rounds.values())


def test_progressive_revelation_hides_later_rounds(bundles):
    by_id = {b.scenario_id: b for b in bundles}
    exfil = by_id["exfil01"]
    round1 = exfil.available_evidence(1)
    round2 = exfil.available_evidence(2)
    assert len(round1) == 8
    assert len(round2) == 12
    hidden = {"EV-exfil01-09", "EV-exfil01-10", "EV-exfil01-11", "EV-exfil01-12"}
    assert hidden & {e.evidence_id for e in round1} == set()
    assert hidden <= {e.evidence_id for e in round2}


def test_get_evidence_respects_round():
    store = load_evidence_store(DEFAULT_SCENARIOS_ROOT / "exfil01")
    assert store.get_evidence("EV-exfil01-09", round_=1) is None
    assert store.get_evidence("EV-exfil01-09", round_=2) is not None
    with pytest.raises(ValueError):
        store.available_evidence(0)


def test_ground_truth_never_exposed_to_investigators(bundles):
    for bundle in bundles:
        store = load_evidence_store(bundle.scenario_dir)
        assert isinstance(store, EvidenceStore)
        # no attribute holds (or can yield) ground truth
        for name, value in vars(store).items():
            assert "truth" not in name.lower()
        # serializing everything an investigator can see must not leak gt keys
        visible = json.dumps(
            {
                "incident": store.incident.model_dump(mode="json"),
                "evidence": [
                    e.model_dump(mode="json") for r in range(1, store.max_round + 1)
                    for e in store.available_evidence(r)
                ],
            }
        )
        for secret in ("expected_stance", "must_cite", "ground_truth", "expected_severity"):
            assert secret not in visible


def _copy_scenario(tmp_path: Path, scenario_id: str) -> Path:
    src = DEFAULT_SCENARIOS_ROOT / scenario_id
    dst = tmp_path / scenario_id
    shutil.copytree(src, dst)
    return dst


def test_invalid_evidence_payload_fails_loudly(tmp_path):
    scenario = _copy_scenario(tmp_path, "ransom01")
    target = scenario / "evidence" / "evidence-03.json"
    payload = json.loads(target.read_text())
    del payload["source"]  # provenance is required by contracts.Evidence
    target.write_text(json.dumps(payload))
    with pytest.raises(ScenarioFormatError, match="contracts.Evidence"):
        load_scenario_bundle(scenario)


def test_naive_timestamp_fails_loudly(tmp_path):
    scenario = _copy_scenario(tmp_path, "ransom01")
    target = scenario / "evidence" / "evidence-03.json"
    payload = json.loads(target.read_text())
    payload["timestamp"] = "2026-09-18T04:11:03"  # naive: rejected by contracts
    target.write_text(json.dumps(payload))
    with pytest.raises(ScenarioFormatError, match="contracts.Evidence"):
        load_scenario_bundle(scenario)


def test_wrong_evidence_id_convention_fails_loudly(tmp_path):
    scenario = _copy_scenario(tmp_path, "ransom01")
    target = scenario / "evidence" / "evidence-03.json"
    payload = json.loads(target.read_text())
    payload["evidence_id"] = "EV-WRONG-03"
    target.write_text(json.dumps(payload))
    with pytest.raises(ScenarioFormatError, match="convention"):
        load_scenario_bundle(scenario)


def test_missing_reveal_round_fails_loudly(tmp_path):
    scenario = _copy_scenario(tmp_path, "ransom01")
    target = scenario / "ground_truth.json"
    payload = json.loads(target.read_text())
    del payload["evidence_reveal_rounds"]["EV-ransom01-13"]
    target.write_text(json.dumps(payload))
    with pytest.raises(ScenarioFormatError, match="missing"):
        load_scenario_bundle(scenario)


def test_mismatched_scenario_id_fails_loudly(tmp_path):
    scenario = _copy_scenario(tmp_path, "ransom01")
    target = scenario / "ground_truth.json"
    payload = json.loads(target.read_text())
    payload["scenario_id"] = "not-the-directory-name"
    target.write_text(json.dumps(payload))
    with pytest.raises(ScenarioFormatError, match="scenario_id"):
        load_scenario_bundle(scenario)


def test_missing_scenario_directory():
    with pytest.raises(ScenarioFormatError, match="not found"):
        load_scenario_bundle("/nonexistent/path/ransom01")

