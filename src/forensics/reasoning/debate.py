"""Proposal evaluation and challenge generation for council debates.

``ProposalEvaluator.evaluate_proposal`` returns a SUPPORT / OPPOSE / ABSTAIN
``DebatePosition`` grounded ONLY in cited evidence, with concrete
``conditions_to_change_position``. ``challenge_unsupported_claim`` produces a
CHALLENGE ``CouncilMessage`` when another agent's claim cites no evidence or
cites evidence that was never provided.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

from contracts.common import Position, utc_now
from contracts.evidence import Evidence
from contracts.inference import ChatMessage, StructuredGenerationRequest
from contracts.investigation import DebatePosition, InvestigationFindings
from contracts.messages import CouncilMessage, CouncilMessageType
from forensics.inference.base import InferenceBackend
from forensics.reasoning.validation import (
    keyword_tokens,
    known_evidence_ids,
    validate_cited_evidence_ids,
)

_SYSTEM = (
    "You are the forensics agent of a cyber incident response council. Take a "
    "position (SUPPORT, OPPOSE, or ABSTAIN) on the proposal, grounded ONLY in "
    "the provided evidence. Never cite evidence ids that were not provided."
)

#: Concrete conditions per stance, used whenever the model supplied none.
_DEFAULT_CONDITIONS: dict[Position, list[str]] = {
    Position.SUPPORT: [
        "Evidence showing the proposed action would disrupt critical services "
        "or destroy forensic artifacts",
        "Evidence contradicting the investigation timeline or cited findings",
    ],
    Position.OPPOSE: [
        "Verified artifacts substantiating the proposal's claims",
        "Evidence showing the investigation's cited findings are incorrect",
    ],
    Position.ABSTAIN: [
        "Corroborating evidence for the proposal's claims",
        "Evidence that raises investigation confidence above the abstention "
        "threshold",
    ],
}


class ProposalEvaluator:
    """Evaluates council proposals against available evidence."""

    def __init__(
        self,
        backend: InferenceBackend,
        *,
        agent_id: str = "forensics-agent",
        abstain_confidence: float = 0.35,
    ) -> None:
        self.backend = backend
        self.agent_id = agent_id
        self.abstain_confidence = abstain_confidence

    def evaluate_proposal(
        self,
        proposal: dict[str, Any],
        evidence: list[Evidence],
        findings: InvestigationFindings,
    ) -> DebatePosition:
        """Take a SUPPORT/OPPOSE/ABSTAIN position on ``proposal``.

        Tries the model first; falls back to a deterministic, keyword-grounded
        evaluation whenever the model output is invalid or cites unknown
        evidence. The returned position NEVER cites unprovided evidence.
        """
        evidence = list(evidence)
        position = self._model_position(proposal, evidence, findings)
        if position is None:
            position = self._deterministic_position(proposal, evidence, findings)
        position = position.model_copy(
            update={
                "agent_id": self.agent_id,
                "incident_id": findings.incident_id,
                "round": findings.round,
            }
        )
        if not position.conditions_to_change_position:
            position = position.model_copy(
                update={
                    "conditions_to_change_position": _DEFAULT_CONDITIONS[position.position]
                }
            )
        # Final guard: fabricated citations must fail loudly, never publish.
        validate_cited_evidence_ids(
            position.supporting_evidence_ids + position.opposing_evidence_ids,
            evidence,
            context="debate position",
        )
        return position

    def challenge_unsupported_claim(
        self,
        claim: CouncilMessage,
        evidence: list[Evidence],
        findings: InvestigationFindings,
    ) -> CouncilMessage:
        """Generate a CHALLENGE message for a claim unsupported by evidence.

        Raises ``ValueError`` when the claim IS supported (challenging a
        grounded claim would be bad-faith debate behaviour).
        """
        cited = self._payload_str_list(claim.payload.get("cited_evidence_ids"))
        valid = known_evidence_ids(evidence)
        missing = [i for i in cited if i not in valid]
        if cited and not missing:
            raise ValueError(
                "claim is supported by available evidence; no challenge is warranted"
            )
        reason = (
            "The claim cites no evidence."
            if not cited
            else "The claim cites evidence that was never provided: "
            f"{', '.join(missing)}."
        )
        return CouncilMessage(
            message_id=f"chal-{uuid.uuid4()}",
            incident_id=claim.incident_id,
            round=claim.round,
            sender=self.agent_id,
            recipients=[claim.sender],
            message_type=CouncilMessageType.CHALLENGE,
            timestamp=utc_now(),
            correlation_id=claim.message_id,
            payload={
                "challenge_type": "UNSUPPORTED_CLAIM",
                "claim_message_id": claim.message_id,
                "reason": reason,
                "missing_evidence_ids": missing,
                "requested_evidence": [
                    "Verified artifacts substantiating the claim",
                    "Provenance (source and collection time) for every cited item",
                ],
                "cited_evidence_ids": [
                    i for i in findings.cited_evidence_ids if i in valid
                ],
            },
        )

    # ---------------------------------------------------------- model attempt

    def _model_position(
        self,
        proposal: dict[str, Any],
        evidence: list[Evidence],
        findings: InvestigationFindings,
    ) -> DebatePosition | None:
        if not evidence:
            return None
        user = (
            f"Incident: {findings.incident_id}\n"
            f"Proposal: {json.dumps(proposal, sort_keys=True, default=str)[:3000]}\n"
            "Evidence: "
            f"{json.dumps([e.model_dump(mode='json') for e in evidence], default=str)[:4000]}\n"
            f"Investigation findings: {findings.findings[:1500]}\n"
            f"Findings cited evidence ids: {findings.cited_evidence_ids}\n"
            "Produce a DebatePosition. Only cite evidence ids from the "
            "provided evidence."
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
        if result.incident_id != findings.incident_id:
            return None
        cited = set(result.supporting_evidence_ids) | set(result.opposing_evidence_ids)
        if not cited <= known_evidence_ids(evidence):
            return None  # fabricated citations -> deterministic fallback
        return result

    # -------------------------------------------------------- deterministic

    def _deterministic_position(
        self,
        proposal: dict[str, Any],
        evidence: list[Evidence],
        findings: InvestigationFindings,
    ) -> DebatePosition:
        valid = known_evidence_ids(evidence)
        proposal_text = self._proposal_text(proposal)
        proposal_tokens = keyword_tokens(proposal_text)
        cited = self._payload_str_list(proposal.get("cited_evidence_ids"))
        missing = [i for i in cited if i not in valid]
        base: dict[str, Any] = {
            "agent_id": self.agent_id,
            "incident_id": findings.incident_id,
            "round": findings.round,
        }
        if not evidence or findings.confidence <= self.abstain_confidence:
            n = len(evidence)
            return DebatePosition(
                **base,
                position=Position.ABSTAIN,
                supporting_evidence_ids=[],
                opposing_evidence_ids=[],
                reasoning=(
                    f"Insufficient evidence to take a position: {n} evidence "
                    "item(s) available and investigation confidence is "
                    f"{findings.confidence}."
                ),
                confidence=min(findings.confidence, 0.3),
                conditions_to_change_position=_DEFAULT_CONDITIONS[Position.ABSTAIN],
            )
        if missing:
            return DebatePosition(
                **base,
                position=Position.OPPOSE,
                supporting_evidence_ids=[],
                opposing_evidence_ids=[
                    i for i in findings.cited_evidence_ids if i in valid
                ],
                reasoning=(
                    "The proposal cites evidence that does not exist ("
                    f"{', '.join(missing)}); as stated, no available evidence "
                    "supports it."
                ),
                confidence=0.6,
                conditions_to_change_position=_DEFAULT_CONDITIONS[Position.OPPOSE],
            )
        supporting = [
            e
            for e in evidence
            if keyword_tokens(f"{e.description} {e.event_type}") & proposal_tokens
        ]
        if supporting:
            descriptions = "; ".join(
                f"{e.evidence_id}: {e.description}" for e in supporting
            )
            return DebatePosition(
                **base,
                position=Position.SUPPORT,
                supporting_evidence_ids=[e.evidence_id for e in supporting],
                opposing_evidence_ids=[],
                reasoning=(
                    "Available evidence matches the proposal's claims: "
                    f"{descriptions}. Investigation findings: "
                    f"{findings.findings[:400]}"
                ),
                confidence=max(findings.confidence, 0.6),
                conditions_to_change_position=_DEFAULT_CONDITIONS[Position.SUPPORT],
            )
        return DebatePosition(
            **base,
            position=Position.OPPOSE,
            supporting_evidence_ids=[],
            opposing_evidence_ids=[i for i in findings.cited_evidence_ids if i in valid],
            reasoning=(
                "No provided evidence matches the proposal's claims. The "
                f"investigation found: {findings.findings[:400]}"
            ),
            confidence=max(min(findings.confidence, 0.7), 0.5),
            conditions_to_change_position=_DEFAULT_CONDITIONS[Position.OPPOSE],
        )

    # ------------------------------------------------------------- utilities

    @staticmethod
    def _proposal_text(proposal: dict[str, Any]) -> str:
        parts: list[str] = []

        def _walk(value: Any) -> None:
            if isinstance(value, str):
                parts.append(value)
            elif isinstance(value, dict):
                for key, item in value.items():
                    parts.append(str(key))
                    _walk(item)
            elif isinstance(value, (list, tuple)):
                for item in value:
                    _walk(item)

        _walk(proposal)
        return " ".join(parts)

    @staticmethod
    def _payload_str_list(value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        return [i for i in value if isinstance(i, str) and i.strip()]


