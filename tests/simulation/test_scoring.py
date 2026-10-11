"""Scorer tests: a correct synthetic run scores 1.0; failures are flagged."""

from __future__ import annotations

import pytest

from contracts.common import Position, Severity
from contracts.investigation import (
    DebatePosition,
    InvestigationFindings,
    PositionRevision,
    TimelineEvent,
)
from simulations.ground_truth import GroundTruth
from simulations.loader import ScenarioBundle, load_all_bundles
from simulations.runs import InvestigationRun, RoundRecord
from simulations.scoring import ScoreReport, score_run

AGENT_ID = "test-investigator"


@pytest.fixture(scope="module")
def bundles() -> list[ScenarioBundle]:
    return load_all_bundles()


@pytest.fixture(scope="module")
def by_id(bundles) -> dict[str, ScenarioBundle]:
    return {b.scenario_id: b for b in bundles}


def _position(
    bundle: ScenarioBundle, round_: int, stance: Position, supporting: list[str]
) -> DebatePosition:
    return DebatePosition(
        agent_id=AGENT_ID,
        incident_id=bundle.incident_id,
        round=round_,
        position=stance,
        supporting_evidence_ids=supporting,
        reasoning="synthetic test position",
        confidence=0.9,
    )


def _round(
    bundle: ScenarioBundle,
    round_: int,
    stance: Position,
    *,
    cited: list[str],
    severity: Severity,
    timeline: list[TimelineEvent] | None = None,
    revision: PositionRevision | None = None,
) -> RoundRecord:
    gt = bundle.ground_truth
    findings = InvestigationFindings(
        agent_id=AGENT_ID,
        incident_id=bundle.incident_id,
        round=round_,
        findings=" ".join(gt.expected_findings),
        cited_evidence_ids=cited,
        confidence=0.9,
        timeline=timeline if timeline is not None else _anchor_events(gt),
        severity_assessment=severity,
    )
    return RoundRecord(
        round_=round_,
        findings=findings,
        position=_position(bundle, round_, stance, cited),
        revision=revision,
    )


def _anchor_events(gt: GroundTruth) -> list[TimelineEvent]:
    return [
        TimelineEvent(
            timestamp=a.timestamp,
            description=a.description_contains or gt.expected_findings[0],
            host_id=a.host_id,
            evidence_ids=gt.must_cite_evidence_ids[:1],
        )
        for a in gt.timeline_anchors
    ]


def build_run(
    bundle: ScenarioBundle,
    *,
    extra_cited: tuple[str, ...] = (),
    stance_override: Position | None = None,
    skip_revision: bool = False,
    severity_override: Severity | None = None,
    cite_only_round1: bool = False,
) -> InvestigationRun:
    """Synthesize the run a perfect investigator would produce for `bundle`."""
    gt = bundle.ground_truth
    expected = gt.expected_position_revisions[0] if gt.expected_position_revisions else None
    rounds: list[RoundRecord] = []
    previous: DebatePosition | None = None
    for round_ in range(1, gt.max_round + 1):
        if cite_only_round1:
            cited = [e.evidence_id for e in bundle.available_evidence(1)]
        else:
            cited = [e.evidence_id for e in bundle.available_evidence(round_)] + list(extra_cited)
        stance = gt.expected_stance
        if expected is not None and round_ < expected.min_round:
            stance = expected.previous_position
        if stance_override is not None:
            stance = stance_override
        severity = severity_override or gt.expected_severity

        revision: PositionRevision | None = None
        if (
            not skip_revision
            and stance_override is None
            and expected is not None
            and round_ >= expected.min_round
            and previous is not None
            and previous.position != stance
        ):
            revision = PositionRevision(
                agent_id=AGENT_ID,
                incident_id=bundle.incident_id,
                round=round_,
                previous_position=previous,
                new_position=_position(bundle, round_, stance, cited),
                triggering_evidence_ids=list(expected.triggering_evidence_ids),
                explanation="contradictory evidence arrived",
            )
        record = _round(
            bundle, round_, stance, cited=cited, severity=severity, revision=revision
        )
        rounds.append(record)
        previous = record.position
    return InvestigationRun(
        scenario_id=bundle.scenario_id, incident_id=bundle.incident_id, rounds=rounds
    )



CORE_METRICS = (
    "citation_validity",
    "stance_correctness",
    "severity_match",
    "timeline_anchor_overlap",
    "position_change_correctness",
)


def test_correct_synthetic_run_scores_perfectly(bundles):
    for bundle in bundles:
        report = score_run(bundle.ground_truth, build_run(bundle))
        assert isinstance(report, ScoreReport)
        assert report.overall == 1.0, f"{bundle.scenario_id}: {report.flags}"
        for metric in CORE_METRICS:
            assert getattr(report, metric) == 1.0, (bundle.scenario_id, metric)
        assert report.findings_accuracy == 1.0
        assert report.flags == [], report.flags


def test_scenario3_revision_is_scored_correctly(by_id):
    bundle = by_id["exfil01"]
    gt = bundle.ground_truth
    assert gt.expected_stance is Position.OPPOSE

    correct = score_run(gt, build_run(bundle))
    assert correct.position_change_correctness == 1.0
    assert correct.overall == 1.0

    # an investigator that never revises SUPPORT -> OPPOSE fails both metrics
    stubborn = build_run(bundle, stance_override=Position.SUPPORT, skip_revision=True)
    report = score_run(gt, stubborn)
    assert report.stance_correctness == 0.0
    assert report.position_change_correctness == 0.0
    assert any("expected position revision" in f for f in report.flags)
    assert report.overall < 0.6


def test_citing_nonexistent_evidence_is_flagged(by_id):
    bundle = by_id["exfil01"]
    run = build_run(bundle, extra_cited=("EV-exfil01-99", "EV-made-up-42"))
    report = score_run(bundle.ground_truth, run)
    assert report.citation_validity < 1.0
    assert "cited nonexistent evidence: EV-exfil01-99" in report.flags
    assert "cited nonexistent evidence: EV-made-up-42" in report.flags
    assert report.overall < 1.0


def test_missing_must_cite_is_flagged_but_valid(by_id):
    bundle = by_id["exfil01"]
    # cites only round-1 evidence and never revises, so the decisive round-2
    # evidence ids (the must-cite set) are never cited anywhere
    run = build_run(bundle, cite_only_round1=True, skip_revision=True)
    report = score_run(bundle.ground_truth, run)
    # every cited id exists, but the required citations are missing
    assert report.citation_validity == 1.0
    assert any("missing required citations" in f for f in report.flags)
    assert any("expected position revision" in f for f in report.flags)


def test_no_citations_score_zero(by_id):
    bundle = by_id["ransom01"]
    run = build_run(bundle)
    for record in run.rounds:
        record.findings.cited_evidence_ids = []
        record.position.supporting_evidence_ids = []
        record.position.opposing_evidence_ids = []
    report = score_run(bundle.ground_truth, run)
    assert report.citation_validity == 0.0
    assert any("no evidence was cited" in f for f in report.flags)


def test_wrong_stance_is_flagged(by_id):
    bundle = by_id["ransom01"]
    run = build_run(bundle, stance_override=Position.OPPOSE)
    report = score_run(bundle.ground_truth, run)
    assert report.stance_correctness == 0.0
    assert any("final stance OPPOSE != expected SUPPORT" in f for f in report.flags)


def test_adjacent_severity_scores_half(by_id):
    bundle = by_id["exfil01"]  # expected LOW
    run = build_run(bundle, severity_override=Severity.MEDIUM)
    report = score_run(bundle.ground_truth, run)
    assert report.severity_match == 0.5
    assert any("adjacent" in f for f in report.flags)


def test_unexpected_revision_is_penalized(by_id):
    bundle = by_id["ransom01"]  # expects NO revisions
    run = build_run(bundle)
    first = run.rounds[0]
    first.revision = PositionRevision(
        agent_id=AGENT_ID,
        incident_id=bundle.incident_id,
        round=first.round,
        previous_position=first.position,
        new_position=_position(bundle, first.round, Position.ABSTAIN, bundle.evidence_ids[:1]),
        triggering_evidence_ids=bundle.evidence_ids[:1],
        explanation="spurious",
    )
    report = score_run(bundle.ground_truth, run)
    assert report.position_change_correctness == 0.0
    assert any("unexpected position revision" in f for f in report.flags)


def test_run_ground_truth_mismatch_raises(by_id):
    with pytest.raises(ValueError, match="does not match ground truth"):
        score_run(by_id["ransom01"].ground_truth, build_run(by_id["lateral01"]))
