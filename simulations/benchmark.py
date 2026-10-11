"""Repeatable benchmark: run an investigator callable against all scenarios.

The investigator is injectable: any `Callable[[EvidenceStore], InvestigationRun]`
works, so the real reasoning engine can be dropped in after integration. The
shipped baseline (`simulations.baseline.baseline_investigator`) reads ground
truth ONLY through this module's scoring step — never through the investigation
path (it receives just an `EvidenceStore`).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from simulations.baseline import baseline_investigator
from simulations.ground_truth import GroundTruth
from simulations.loader import (
    DEFAULT_SCENARIOS_ROOT,
    EvidenceStore,
    ScenarioFormatError,
    discover_scenario_dirs,
    load_evidence_store,
    load_scenario_bundle,
)
from simulations.runs import InvestigationRun
from simulations.scoring import ScoreReport, score_run

Investigator = Callable[[EvidenceStore], InvestigationRun]

INVESTIGATORS: dict[str, Investigator] = {
    "baseline": baseline_investigator,
}


def get_investigator(name: str) -> Investigator:
    """Look up a registered investigator callable by name."""
    try:
        return INVESTIGATORS[name]
    except KeyError:
        raise KeyError(
            f"unknown investigator {name!r}; available: {sorted(INVESTIGATORS)}"
        ) from None


@dataclass
class ScenarioMetrics:
    """Per-scenario outcome: score plus efficiency metrics."""

    scenario_id: str
    score: ScoreReport
    tool_call_count: int
    durations_ms: list[int]
    mean_duration_ms: float
    max_duration_ms: int


@dataclass
class BenchmarkReport:
    """Aggregate benchmark result across all scenarios."""

    investigator: str
    scenarios: list[ScenarioMetrics] = field(default_factory=list)

    @property
    def mean_overall(self) -> float:
        if not self.scenarios:
            return 0.0
        return sum(s.score.overall for s in self.scenarios) / len(self.scenarios)

    @property
    def mean_findings_accuracy(self) -> float:
        if not self.scenarios:
            return 0.0
        return sum(s.score.findings_accuracy for s in self.scenarios) / len(self.scenarios)

    @property
    def stance_accuracy(self) -> float:
        if not self.scenarios:
            return 0.0
        return sum(s.score.stance_correctness for s in self.scenarios) / len(self.scenarios)

    @property
    def tool_call_count(self) -> int:
        return sum(s.tool_call_count for s in self.scenarios)

    @property
    def all_durations_ms(self) -> list[int]:
        return [d for s in self.scenarios for d in s.durations_ms]

    @property
    def mean_duration_ms(self) -> float:
        durations = self.all_durations_ms
        if not durations:
            return 0.0
        return sum(durations) / len(durations)

    @property
    def max_duration_ms(self) -> int:
        return max(self.all_durations_ms, default=0)



def score_scenario(
    investigator: Investigator, scenario_dir: Path
) -> ScenarioMetrics:
    """Run one investigator over one scenario and score it against ground truth.

    The investigator only sees the `EvidenceStore`; ground truth is read here,
    purely for scoring.
    """
    store = load_evidence_store(scenario_dir)
    run = investigator(store)
    bundle = load_scenario_bundle(scenario_dir)
    gt: GroundTruth = bundle.ground_truth
    report = score_run(gt, run)
    invocations = run.tool_invocations
    durations = [inv.duration_ms for inv in invocations]
    return ScenarioMetrics(
        scenario_id=bundle.scenario_id,
        score=report,
        tool_call_count=len(invocations),
        durations_ms=durations,
        mean_duration_ms=round(sum(durations) / len(durations), 2) if durations else 0.0,
        max_duration_ms=max(durations, default=0),
    )


def run_benchmark(
    investigator: Investigator,
    scenarios_root: Path | str = DEFAULT_SCENARIOS_ROOT,
    *,
    investigator_name: str = "custom",
) -> BenchmarkReport:
    """Run the investigator against every scenario under `scenarios_root`."""
    dirs = discover_scenario_dirs(scenarios_root)
    scenarios: list[ScenarioMetrics] = []
    for scenario_dir in dirs:
        try:
            scenarios.append(score_scenario(investigator, scenario_dir))
        except ScenarioFormatError as exc:
            raise ScenarioFormatError(f"benchmark cannot proceed: {exc}") from exc
    return BenchmarkReport(investigator=investigator_name, scenarios=scenarios)


def format_text_report(report: BenchmarkReport) -> str:
    """Human-readable metrics report."""
    lines: list[str] = []
    lines.append(f"benchmark — investigator: {report.investigator}")
    lines.append("=" * 72)
    header = (
        f"{'scenario':<12} {'overall':>7} {'findings':>9} {'stance':>7} "
        f"{'cites':>6} {'sev':>5} {'tline':>6} {'rev':>5} {'tools':>6} {'ms(mean/max)':>14}"
    )
    lines.append(header)
    lines.append("-" * len(header))
    for s in report.scenarios:
        r = s.score
        lines.append(
            f"{s.scenario_id:<12} {r.overall:>7.3f} {r.findings_accuracy:>9.3f} "
            f"{r.stance_correctness:>7.3f} {r.citation_validity:>6.3f} "
            f"{r.severity_match:>5.3f} {r.timeline_anchor_overlap:>6.3f} "
            f"{r.position_change_correctness:>5.3f} {s.tool_call_count:>6d} "
            f"{s.mean_duration_ms:>7.1f}/{s.max_duration_ms:<6d}"
        )
    lines.append("-" * len(header))
    lines.append(f"scenarios evaluated      : {len(report.scenarios)}")
    lines.append(f"mean overall score      : {report.mean_overall:.3f}")
    lines.append(f"mean findings accuracy  : {report.mean_findings_accuracy:.3f}")
    lines.append(f"stance accuracy         : {report.stance_accuracy:.3f}")
    lines.append(f"total tool calls        : {report.tool_call_count}")
    lines.append(
        f"tool duration ms mean/max: {report.mean_duration_ms:.1f} / {report.max_duration_ms}"
    )
    for s in report.scenarios:
        for flag in s.score.flags:
            lines.append(f"  [{s.scenario_id}] {flag}")
    return "\n".join(lines)


def format_json_report(report: BenchmarkReport) -> dict:
    """Machine-readable report (JSON-serializable dict)."""
    return {
        "investigator": report.investigator,
        "scenarios": [
            {
                "scenario_id": s.scenario_id,
                "score": s.score.model_dump(mode="json"),
                "tool_call_count": s.tool_call_count,
                "durations_ms": s.durations_ms,
                "mean_duration_ms": s.mean_duration_ms,
                "max_duration_ms": s.max_duration_ms,
            }
            for s in report.scenarios
        ],
        "aggregate": {
            "scenario_count": len(report.scenarios),
            "mean_overall": round(report.mean_overall, 4),
            "mean_findings_accuracy": round(report.mean_findings_accuracy, 4),
            "stance_accuracy": round(report.stance_accuracy, 4),
            "tool_call_count": report.tool_call_count,
            "mean_duration_ms": round(report.mean_duration_ms, 2),
            "max_duration_ms": report.max_duration_ms,
        },
    }
