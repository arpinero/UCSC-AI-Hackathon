"""Score an investigation run against a scenario's ground truth.

Core metrics (each 0.0-1.0):

* `citation_validity` — every cited/triggering evidence id exists in the scenario.
* `stance_correctness` — the run's final position matches the expected stance.
* `severity_match` — the run's final severity assessment matches expectations.
* `timeline_anchor_overlap` — soft overlap of the run's timeline with the
  ground-truth anchors (timestamp tolerance + host + description keyword).
* `position_change_correctness` — the run made the expected position revision(s)
  when contradictory evidence arrived, and no unexpected ones.

`findings_accuracy` is reported as an informational metric (weight 0): soft
keyword overlap of the final findings text with `expected_findings`.

`overall` is the weighted blend of the five core metrics.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, Field

from contracts.common import Severity
from contracts.investigation import PositionRevision
from simulations.ground_truth import GroundTruth
from simulations.runs import InvestigationRun

WEIGHTS: dict[str, float] = {
    "citation_validity": 0.25,
    "stance_correctness": 0.25,
    "severity_match": 0.15,
    "timeline_anchor_overlap": 0.15,
    "position_change_correctness": 0.20,
}

SEVERITY_ORDER = [
    Severity.INFO,
    Severity.LOW,
    Severity.MEDIUM,
    Severity.HIGH,
    Severity.CRITICAL,
]

DEFAULT_ANCHOR_TOLERANCE_S = 300
_WORD_RE = re.compile(r"[a-z0-9]{4,}")
_FINDINGS_MATCH_RATIO = 0.6


class ScoreReport(BaseModel):
    """Result of scoring one run against one scenario's ground truth."""

    scenario_id: str
    incident_id: str
    overall: float = Field(ge=0.0, le=1.0)
    citation_validity: float = Field(ge=0.0, le=1.0)
    stance_correctness: float = Field(ge=0.0, le=1.0)
    severity_match: float = Field(ge=0.0, le=1.0)
    timeline_anchor_overlap: float = Field(ge=0.0, le=1.0)
    position_change_correctness: float = Field(ge=0.0, le=1.0)
    findings_accuracy: float = Field(ge=0.0, le=1.0)
    flags: list[str] = Field(default_factory=list)


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def _score_citations(gt: GroundTruth, run: InvestigationRun, flags: list[str]) -> float:
    valid_ids = set(gt.evidence_reveal_rounds)
    cited = run.all_cited_evidence_ids
    if not cited:
        flags.append("no evidence was cited anywhere in the run")
        return 0.0
    invalid = [eid for eid in cited if eid not in valid_ids]
    for eid in invalid:
        flags.append(f"cited nonexistent evidence: {eid}")
    missing_must_cite = [eid for eid in gt.must_cite_evidence_ids if eid not in cited]
    if missing_must_cite:
        flags.append(f"missing required citations: {missing_must_cite}")
    return _clamp((len(cited) - len(invalid)) / len(cited))


def _score_stance(gt: GroundTruth, run: InvestigationRun, flags: list[str]) -> float:
    final = run.final_position
    if final is None:
        flags.append("run has no final position")
        return 0.0
    if final == gt.expected_stance:
        return 1.0
    flags.append(
        f"final stance {final.value} != expected {gt.expected_stance.value} "
        f"on proposal: {gt.containment_proposal!r}"
    )
    return 0.0


def _score_severity(gt: GroundTruth, run: InvestigationRun, flags: list[str]) -> float:
    assessed = run.final_findings.severity_assessment
    if assessed is None:
        flags.append("no severity assessment in final findings")
        return 0.0
    if assessed == gt.expected_severity:
        return 1.0
    distance = abs(SEVERITY_ORDER.index(assessed) - SEVERITY_ORDER.index(gt.expected_severity))
    if distance == 1:
        flags.append(f"severity {assessed.value} adjacent to expected {gt.expected_severity.value}")
        return 0.5
    flags.append(f"severity {assessed.value} != expected {gt.expected_severity.value}")
    return 0.0


def _anchor_matched(anchor, events, tolerance_s: int) -> bool:
    for event in events:
        delta = abs((event.timestamp - anchor.timestamp).total_seconds())
        if delta > tolerance_s:
            continue
        if anchor.host_id is not None and event.host_id != anchor.host_id:
            continue
        if anchor.description_contains is not None:
            if anchor.description_contains.casefold() not in event.description.casefold():
                continue
        return True
    return False


def _score_timeline(
    gt: GroundTruth, run: InvestigationRun, tolerance_s: int, flags: list[str]
) -> float:
    anchors = gt.timeline_anchors
    if not anchors:
        return 1.0
    events = run.timeline_events
    if not events:
        flags.append("run produced no timeline events")
        return 0.0
    matched = sum(1 for a in anchors if _anchor_matched(a, events, tolerance_s))
    if matched < len(anchors):
        flags.append(f"timeline anchors unmatched: {len(anchors) - matched}/{len(anchors)}")
    return _clamp(matched / len(anchors))



def _revision_matches(expected, revision: PositionRevision) -> bool:
    if revision.previous_position.position != expected.previous_position:
        return False
    if revision.new_position.position != expected.new_position:
        return False
    if revision.round < expected.min_round:
        return False
    return bool(set(revision.triggering_evidence_ids) & set(expected.triggering_evidence_ids))


def _score_revisions(gt: GroundTruth, run: InvestigationRun, flags: list[str]) -> float:
    expected = gt.expected_position_revisions
    actual = run.revisions
    if not expected:
        if actual:
            flags.append(f"unexpected position revision(s) in round(s) {[r.round for r in actual]}")
            return 0.0
        return 1.0
    matched = sum(1 for exp in expected if any(_revision_matches(exp, rev) for rev in actual))
    if len(actual) > len(expected):
        flags.append(f"more revisions than expected: {len(actual)} > {len(expected)}")
    if matched < len(expected):
        flags.append(f"expected position revision(s) not made: {len(expected) - matched}")
        return _clamp(matched / len(expected))
    return 1.0


def _significant_words(text: str) -> set[str]:
    return set(_WORD_RE.findall(text.casefold()))


def _findings_accuracy(gt: GroundTruth, run: InvestigationRun) -> float:
    if not gt.expected_findings:
        return 1.0
    text = run.final_findings.findings.casefold()
    found = 0
    for expected in gt.expected_findings:
        words = _significant_words(expected)
        if not words:
            found += 1
            continue
        overlap = sum(1 for w in words if w in text)
        if overlap / len(words) >= _FINDINGS_MATCH_RATIO:
            found += 1
    return _clamp(found / len(gt.expected_findings))


def score_run(
    gt: GroundTruth,
    run: InvestigationRun,
    *,
    anchor_tolerance_s: int = DEFAULT_ANCHOR_TOLERANCE_S,
) -> ScoreReport:
    """Score one investigation run against one scenario's ground truth."""
    if run.scenario_id != gt.scenario_id or run.incident_id != gt.incident_id:
        raise ValueError(
            f"run {run.scenario_id}/{run.incident_id} does not match ground truth "
            f"{gt.scenario_id}/{gt.incident_id}"
        )
    flags: list[str] = []
    metrics: dict[str, float] = {
        "citation_validity": _score_citations(gt, run, flags),
        "stance_correctness": _score_stance(gt, run, flags),
        "severity_match": _score_severity(gt, run, flags),
        "timeline_anchor_overlap": _score_timeline(gt, run, anchor_tolerance_s, flags),
        "position_change_correctness": _score_revisions(gt, run, flags),
    }
    overall = round(
        sum(metrics[name] * weight for name, weight in WEIGHTS.items()) / sum(WEIGHTS.values()),
        4,
    )
    return ScoreReport(
        scenario_id=gt.scenario_id,
        incident_id=gt.incident_id,
        overall=overall,
        findings_accuracy=_findings_accuracy(gt, run),
        flags=flags,
        **metrics,
    )
