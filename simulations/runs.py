"""Run records: what an investigator did, in a form the scorer can consume.

An `InvestigationRun` is produced by any investigator callable (the heuristic
baseline shipped here, or the real reasoning engine after integration) and
consumed by `simulations.scoring`.
"""

from __future__ import annotations

import uuid

from contracts.common import NonEmptyString, NonNegativeInt, Position
from contracts.investigation import (
    DebatePosition,
    InvestigationFindings,
    PositionRevision,
    TimelineEvent,
)
from contracts.tools import ToolInvocation


class RoundRecord:
    """One council round of an investigation: findings, stance, revision, tool calls."""

    def __init__(
        self,
        *,
        round_: int,
        findings: InvestigationFindings,
        position: DebatePosition,
        revision: PositionRevision | None = None,
        tool_invocations: list[ToolInvocation] | None = None,
    ) -> None:
        if round_ < 1:
            raise ValueError(f"round must be >= 1, got {round_}")
        self.round = round_
        self.findings = findings
        self.position = position
        self.revision = revision
        self.tool_invocations = list(tool_invocations or [])


class InvestigationRun:
    """The complete record of one investigator run against one scenario."""

    def __init__(self, *, scenario_id: str, incident_id: str, rounds: list[RoundRecord]) -> None:
        if not rounds:
            raise ValueError("an investigation run must contain at least one round")
        self.scenario_id = scenario_id
        self.incident_id = incident_id
        self.rounds = sorted(rounds, key=lambda r: r.round)
        seen = [r.round for r in self.rounds]
        if len(set(seen)) != len(seen):
            raise ValueError(f"duplicate round numbers in run: {seen}")

    @property
    def final_round(self) -> RoundRecord:
        return self.rounds[-1]

    @property
    def final_findings(self) -> InvestigationFindings:
        return self.final_round.findings

    @property
    def final_position(self) -> Position | None:
        """Stance after any revision in the final round."""
        last = self.final_round
        if last.revision is not None:
            return last.revision.new_position.position
        return last.position.position

    @property
    def revisions(self) -> list[PositionRevision]:
        return [r.revision for r in self.rounds if r.revision is not None]

    @property
    def all_cited_evidence_ids(self) -> list[str]:
        """Every evidence id cited anywhere (findings, positions, revisions), in order."""
        out: list[str] = []
        for rnd in self.rounds:
            out.extend(rnd.findings.cited_evidence_ids)
            out.extend(rnd.position.supporting_evidence_ids)
            out.extend(rnd.position.opposing_evidence_ids)
            if rnd.revision is not None:
                out.extend(rnd.revision.triggering_evidence_ids)
                out.extend(rnd.revision.previous_position.supporting_evidence_ids)
                out.extend(rnd.revision.previous_position.opposing_evidence_ids)
                out.extend(rnd.revision.new_position.supporting_evidence_ids)
                out.extend(rnd.revision.new_position.opposing_evidence_ids)
        seen: set[str] = set()
        unique: list[str] = []
        for eid in out:
            if eid not in seen:
                seen.add(eid)
                unique.append(eid)
        return unique

    @property
    def tool_invocations(self) -> list[ToolInvocation]:
        return [inv for rnd in self.rounds for inv in rnd.tool_invocations]

    @property
    def timeline_events(self) -> list[TimelineEvent]:
        return [ev for rnd in self.rounds for ev in rnd.findings.timeline]


def make_tool_invocation(
    *,
    incident_id: NonEmptyString,
    tool_name: NonEmptyString,
    arguments: dict | None = None,
    result: dict | None = None,
    referenced_evidence_ids: list[NonEmptyString] | None = None,
    duration_ms: NonNegativeInt,
) -> ToolInvocation:
    """Build a ToolInvocation audit record with a fresh invocation id."""
    return ToolInvocation(
        invocation_id=f"TI-{uuid.uuid4()}",
        incident_id=incident_id,
        tool_name=tool_name,
        arguments=dict(arguments or {}),
        result=dict(result) if result is not None else None,
        referenced_evidence_ids=list(referenced_evidence_ids or []),
        duration_ms=duration_ms,
    )
