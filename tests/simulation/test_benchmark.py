"""Benchmark tests: injectable investigator, metrics aggregation, CLI smoke."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from simulations.baseline import baseline_investigator
from simulations.benchmark import (
    format_json_report,
    format_text_report,
    get_investigator,
    run_benchmark,
)
from simulations.loader import DEFAULT_SCENARIOS_ROOT, EvidenceStore

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_baseline_benchmark_aggregates_metrics():
    report = run_benchmark(baseline_investigator, investigator_name="baseline")
    assert [s.scenario_id for s in report.scenarios] == ["exfil01", "lateral01", "ransom01"]
    assert report.stance_accuracy == 1.0
    assert report.tool_call_count >= 3 * 6
    assert report.max_duration_ms >= report.mean_duration_ms > 0
    for s in report.scenarios:
        assert s.tool_call_count == len(s.durations_ms) > 0
        assert s.score.overall == 1.0


def test_investigator_is_injectable():
    """Any Callable[[EvidenceStore], InvestigationRun] can be benchmarked."""

    def clumsy(store: EvidenceStore):
        run = baseline_investigator(store)
        for record in run.rounds:
            record.findings.cited_evidence_ids = []
            record.position.supporting_evidence_ids = []
            record.position.opposing_evidence_ids = []
            if record.revision is not None:
                record.revision.triggering_evidence_ids = []
                for pos in (record.revision.previous_position, record.revision.new_position):
                    pos.supporting_evidence_ids = []
                    pos.opposing_evidence_ids = []
        return run

    report = run_benchmark(clumsy, investigator_name="clumsy")
    assert report.investigator == "clumsy"
    for s in report.scenarios:
        assert s.score.citation_validity == 0.0
        assert s.score.overall < 1.0


def test_get_investigator_registry():
    assert get_investigator("baseline") is baseline_investigator
    with pytest.raises(KeyError, match="unknown investigator"):
        get_investigator("nope")


def test_report_formats():
    report = run_benchmark(baseline_investigator, investigator_name="baseline")
    text = format_text_report(report)
    assert "benchmark — investigator: baseline" in text
    for sid in ("exfil01", "lateral01", "ransom01"):
        assert sid in text
    assert "total tool calls" in text
    payload = json.loads(json.dumps(format_json_report(report)))
    assert payload["investigator"] == "baseline"
    assert len(payload["scenarios"]) == 3
    assert payload["aggregate"]["tool_call_count"] == report.tool_call_count


def test_cli_smoke():
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "benchmark.py")],
        capture_output=True,
        text=True,
        timeout=120,
        cwd=REPO_ROOT,
    )
    assert result.returncode == 0, result.stderr
    assert "ransom01" in result.stdout
    assert "total tool calls" in result.stdout


def test_cli_json_scenarios_dir():
    result = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "benchmark.py"),
            "--json",
            "--scenarios-dir",
            str(DEFAULT_SCENARIOS_ROOT),
        ],
        capture_output=True,
        text=True,
        timeout=120,
        cwd=REPO_ROOT,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["aggregate"]["scenario_count"] == 3
