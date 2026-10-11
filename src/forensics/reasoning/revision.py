"""Evidence-only revision of debate positions.

A position changes ONLY because of evidence — never because of social
pressure. ``revise_position`` checks whether newly arrived evidence meets any
stated ``conditions_to_change_position`` and, if so, emits an explicit
``PositionRevision`` (previous position + new position + triggering evidence
ids + explanation). ``respond_to_challenge`` answers a CHALLENGE message: it
produces a revision only when the challenge presents NEW evidence that meets
the stated conditions; otherwise the position stands and the challenge is
answered with a grounded reply.
"""

from __future__ import annotations

import json
import uuid

from contracts.common import Position, utc_now
from contracts.evidence import Evidence
from contracts.inference import ChatMessage, StructuredGenerationRequest
from contracts.investigation import DebatePosition, PositionRevision
from contracts.messages import CouncilMessage, CouncilMessageType
from forensics.inference.base import InferenceBackend
from forensics.reasoning.validation import keyword_tokens, known_evidence_ids

_SYSTEM = (
    "You are the forensics agent of a cyber incident response council. Given "
    "the current debate position, its conditions to change, and NEW evidence, "
    "decide the agent's position. Only cite evidence ids from the provided "
    "evidence."
)


class PositionReviser:
    """Revises debate positions strictly on the basis of new evidence."""

    def __init__(
        self,
        backend: InferenceBackend,
        *,
        agent_id: str = "forensics-agent",
        min_condition_overlap: int = 2,
    ) -> None:
        self.backend = backend
        self.agent_id = agent_id
        self.min_condition_overlap = min_condition_overlap

    # ------------------------------------------------------------------ public

    def revise_position(
        self, current: DebatePosition, new_evidence: list[Evidence]
    ) -> PositionRevision | None:
        """Return a revision if new evidence meets stated conditions.

        Returns ``None`` when no condition is met (the position stands).
        """
        new_evidence = list(new_evidence)
        if not new_evidence:
            return None
        revision = self._model_revision(current, new_evidence)
        if revision is not None:
            return revision
        matched = self._conditions_met(current, new_evidence)
        if not matched:
            return None
        return self._build_revision(current, matched)

    def respond_to_challenge(
        self,
        challenge: CouncilMessage,
        current: DebatePosition,
        evidence: list[Evidence],
    ) -> PositionRevision | CouncilMessage:
        """Answer a CHALLENGE against ``current``.

        Returns a :class:`PositionRevision` only when the challenge presents
        new evidence that meets the stated conditions to change position.
        Otherwise the position stands and a grounded CHALLENGE reply (with
        ``correlation_id`` set to the incoming message) is returned.
        """
        if challenge.message_type != CouncilMessageType.CHALLENGE:
            raise ValueError("respond_to_challenge expects a CHALLENGE message")
        evidence = list(evidence)
        valid = known_evidence_ids(evidence)
        cited: list[str] = []
        for key in ("cited_evidence_ids", "new_evidence_ids"):
            value = challenge.payload.get(key)
            if isinstance(value, list):
                cited.extend(i for i in value if isinstance(i, str))
        existing = set(current.supporting_evidence_ids) | set(current.opposing_evidence_ids)
        fresh = [
            e
            for e in evidence
            if e.evidence_id in set(cited)
            and e.evidence_id in valid
            and e.evidence_id not in existing
        ]
        matched = self._conditions_met(current, fresh) if fresh else []
        if matched:
            return self._build_revision(current, matched)
        return CouncilMessage(
            message_id=f"resp-{uuid.uuid4()}",
            incident_id=challenge.incident_id,
            round=challenge.round,
            sender=self.agent_id,
            recipients=[challenge.sender],
            message_type=CouncilMessageType.CHALLENGE,
            timestamp=utc_now(),
            correlation_id=challenge.message_id,
            payload={
                "response_type": "POSITION_STANDS",
                "challenge_message_id": challenge.message_id,
                "reason": (
                    "The challenge presents no new evidence meeting the stated "
                    "conditions to change position; the position stands."
                ),
                "position_maintained": current.position.value,
                "conditions_to_change_position": list(
                    current.conditions_to_change_position
                ),
                "cited_evidence_ids": [
                    i for i in current.supporting_evidence_ids if i in valid
                ],
            },
        )

    # ------------------------------------------------------ condition matching

    def _conditions_met(
        self, current: DebatePosition, evidence: list[Evidence]
    ) -> list[tuple[str, Evidence]]:
        """Pairs of (condition, evidence) where the condition is met.

        A condition is met when an evidence item's id is mentioned in the
        condition text, or when the condition and the evidence description
        share at least ``min_condition_overlap`` distinctive keywords.
        """
        matched: list[tuple[str, Evidence]] = []
        for condition in current.conditions_to_change_position:
            cond_tokens = keyword_tokens(condition)
            for e in evidence:
                if e.evidence_id in condition:
                    matched.append((condition, e))
                    continue
                ev_tokens = keyword_tokens(f"{e.description} {e.event_type}")
                if len(cond_tokens & ev_tokens) >= self.min_condition_overlap:
                    matched.append((condition, e))
        return matched

    # ------------------------------------------------------------- revision

    def _build_revision(
        self, current: DebatePosition, matched: list[tuple[str, Evidence]]
    ) -> PositionRevision:
        trig_ids = sorted({e.evidence_id for _, e in matched})
        conditions = sorted({c for c, _ in matched})
        descriptions = "; ".join(f"{e.evidence_id}: {e.description}" for _, e in matched)
        previous = current.position
        if previous == Position.SUPPORT:
            flipped = Position.OPPOSE
        elif previous == Position.OPPOSE:
            flipped = Position.SUPPORT
        else:
            # A stated condition being met means decisive evidence arrived;
            # the agent can now support the matter under debate.
            flipped = Position.SUPPORT
        if flipped == Position.OPPOSE:
            supporting: list[str] = []
            opposing: list[str] = trig_ids
        else:
            supporting = trig_ids
            opposing = []
        new_position = DebatePosition(
            agent_id=self.agent_id,
            incident_id=current.incident_id,
            round=current.round,
            position=flipped,
            supporting_evidence_ids=supporting,
            opposing_evidence_ids=opposing,
            reasoning=(
                f"Previously stated condition met: {conditions[0]}. New "
                f"evidence: {descriptions}."
            ),
            confidence=min(0.9, max(current.confidence, 0.6)),
            conditions_to_change_position=[
                "Evidence contradicting the newly cited items",
                f"Evidence showing the original {previous.value} position "
                "was correct after all",
            ],
        )
        return PositionRevision(
            agent_id=self.agent_id,
            incident_id=current.incident_id,
            round=current.round,
            previous_position=current,
            new_position=new_position,
            triggering_evidence_ids=trig_ids,
            explanation=(
                "Position revised because a previously stated condition was "
                f"met by new evidence: {conditions} — {descriptions}. This "
                "revision is driven solely by evidence, not by debate pressure."
            ),
        )

    # ---------------------------------------------------------- model attempt

    def _model_revision(
        self, current: DebatePosition, new_evidence: list[Evidence]
    ) -> PositionRevision | None:
        new_ids = known_evidence_ids(new_evidence)
        allowed = new_ids | set(current.supporting_evidence_ids) | set(
            current.opposing_evidence_ids
        )
        user = (
            f"Incident: {current.incident_id}\n"
            f"Current position: {current.position.value}\n"
            f"Current reasoning: {current.reasoning[:800]}\n"
            f"Conditions to change position: {current.conditions_to_change_position}\n"
            "New evidence: "
            f"{json.dumps([e.model_dump(mode='json') for e in new_evidence], default=str)[:4000]}\n"
            "Produce the new DebatePosition, or repeat the current position if "
            "no condition is met."
        )
        req = StructuredGenerationRequest(
            messages=[
                ChatMessage(role="system", content=_SYSTEM),
                ChatMessage(role="user", content=user),
            ],
            response_model="DebatePosition",
        )
        try:
            result = self.backend.generate_structured(req, DebatePosition)
        except Exception:
            return None
        if not isinstance(result, DebatePosition):
            return None
        if result.position == current.position:
            return None
        cited = set(result.supporting_evidence_ids) | set(result.opposing_evidence_ids)
        if not cited <= allowed:
            return None  # fabricated citations -> deterministic decision
        triggering = sorted(cited & new_ids)
        if not triggering:
            return None  # a position flip MUST be triggered by new evidence
        new_position = result.model_copy(
            update={
                "agent_id": self.agent_id,
                "incident_id": current.incident_id,
                "round": current.round,
            }
        )
        return PositionRevision(
            agent_id=self.agent_id,
            incident_id=current.incident_id,
            round=current.round,
            previous_position=current,
            new_position=new_position,
            triggering_evidence_ids=triggering,
            explanation=(
                "Position revised after new evidence met a stated condition "
                f"(model-directed): {result.reasoning[:800]}. Triggering "
                f"evidence: {', '.join(triggering)}."
            ),
        )

