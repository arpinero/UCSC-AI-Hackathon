"""Proposal evaluation and challenge-generation tests."""

from __future__ import annotations

import pytest

from contracts.common import Position
from contracts.messages import CouncilMessageType
from forensics.inference.mock import MockInferenceBackend
from forensics.reasoning.debate import ProposalEvaluator
from tests.unit.reasoning.helpers import (
    INCIDENT,
    ScriptedBackend,
    make_evidence,
    make_findings,
    make_message,
)

_CONTAIN_PROPOSAL = {
    "title": "Isolate the compromised web-01 host",
    "description": "Contain lateral movement by isolating web-01 from the network",
}

_UNRELATED_PROPOSAL = {
    "title": "Decommission the mail relay cluster",
    "description": "Quantum telemetry proves the mail relay is the compromised host",
}


def test_support_when_evidence_matches_proposal():
    evidence = [make_evidence("EV-1001")]
    findings = make_findings(cited=["EV-1001"], confidence=0.8)
    evaluator = ProposalEvaluator(MockInferenceBackend(fail_structured=True))
    position = evaluator.evaluate_proposal(_CONTAIN_PROPOSAL, evidence, findings)

    assert position.position == Position.SUPPORT
    assert position.supporting_evidence_ids == ["EV-1001"]
    assert position.opposing_evidence_ids == []
    assert position.conditions_to_change_position
    assert position.agent_id == "forensics-agent"
    assert position.incident_id == INCIDENT
    assert position.round == 1
    assert position.confidence >= 0.6
    assert "EV-1001" in position.reasoning


def test_model_directed_support_position_is_normalized():
    evidence = [make_evidence("EV-1001")]
    findings = make_findings(cited=["EV-1001"])
    backend = ScriptedBackend(
        [
            {
                "agent_id": "rogue-agent",
                "incident_id": INCIDENT,
                "round": 9,
                "position": "SUPPORT",
                "supporting_evidence_ids": ["EV-1001"],
                "reasoning": "Model reasoning grounded in EV-1001.",
                "confidence": 0.75,
            }
        ]
    )
    evaluator = ProposalEvaluator(backend)
    position = evaluator.evaluate_proposal(_CONTAIN_PROPOSAL, evidence, findings)

    assert position.position == Position.SUPPORT
    assert position.agent_id == "forensics-agent"
    assert position.round == findings.round
    assert position.conditions_to_change_position  # defaults filled in


def test_oppose_when_no_evidence_matches_the_proposal():
    evidence = [make_evidence("EV-1001")]
    findings = make_findings(cited=["EV-1001"], confidence=0.8)
    evaluator = ProposalEvaluator(MockInferenceBackend(fail_structured=True))
    position = evaluator.evaluate_proposal(_UNRELATED_PROPOSAL, evidence, findings)

    assert position.position == Position.OPPOSE
    assert position.opposing_evidence_ids == ["EV-1001"]
    assert position.supporting_evidence_ids == []
    assert position.conditions_to_change_position


def test_oppose_when_proposal_cites_nonexistent_evidence():
    evidence = [make_evidence("EV-1001")]
    findings = make_findings(cited=["EV-1001"], confidence=0.8)
    proposal = dict(_CONTAIN_PROPOSAL, cited_evidence_ids=["EV-FAKE"])
    evaluator = ProposalEvaluator(MockInferenceBackend(fail_structured=True))
    position = evaluator.evaluate_proposal(proposal, evidence, findings)

    assert position.position == Position.OPPOSE
    assert "EV-FAKE" not in position.supporting_evidence_ids
    assert "EV-FAKE" not in position.opposing_evidence_ids
    assert "EV-FAKE" in position.reasoning


def test_abstain_when_evidence_is_thin():
    findings = make_findings(cited=[], confidence=0.05)
    evaluator = ProposalEvaluator(MockInferenceBackend(fail_structured=True))
    position = evaluator.evaluate_proposal(_CONTAIN_PROPOSAL, [], findings)

    assert position.position == Position.ABSTAIN
    assert position.confidence <= 0.3
    assert position.supporting_evidence_ids == []
    assert position.opposing_evidence_ids == []
    assert position.conditions_to_change_position


def test_abstain_when_investigation_confidence_is_low():
    evidence = [make_evidence("EV-1001")]
    findings = make_findings(cited=["EV-1001"], confidence=0.2)
    evaluator = ProposalEvaluator(MockInferenceBackend(fail_structured=True))
    position = evaluator.evaluate_proposal(_CONTAIN_PROPOSAL, evidence, findings)

    assert position.position == Position.ABSTAIN


def test_model_position_citing_unknown_evidence_falls_back():
    evidence = [make_evidence("EV-1001")]
    findings = make_findings(cited=["EV-1001"], confidence=0.8)
    backend = ScriptedBackend(
        [
            {
                "agent_id": "forensics-agent",
                "incident_id": INCIDENT,
                "round": 1,
                "position": "SUPPORT",
                "supporting_evidence_ids": ["EV-INVENTED"],
                "reasoning": "Hallucinated support.",
                "confidence": 0.9,
            }
        ]
    )
    evaluator = ProposalEvaluator(backend)
    position = evaluator.evaluate_proposal(_CONTAIN_PROPOSAL, evidence, findings)

    # deterministic fallback engaged; no fabricated citations survive
    assert position.position == Position.SUPPORT
    assert "EV-INVENTED" not in position.supporting_evidence_ids


def test_challenge_for_claim_citing_missing_evidence():
    evidence = [make_evidence("EV-1001")]
    findings = make_findings(cited=["EV-1001"])
    claim = make_message(
        CouncilMessageType.PROPOSAL,
        {"claim": "web-01 is clean", "cited_evidence_ids": ["EV-9999"]},
    )
    evaluator = ProposalEvaluator(MockInferenceBackend(fail_structured=True))
    challenge = evaluator.challenge_unsupported_claim(claim, evidence, findings)

    assert challenge.message_type == CouncilMessageType.CHALLENGE
    assert challenge.correlation_id == claim.message_id
    assert challenge.recipients == ["containment-agent"]
    assert challenge.payload["missing_evidence_ids"] == ["EV-9999"]
    assert challenge.payload["requested_evidence"]


def test_challenge_for_claim_citing_no_evidence():
    evidence = [make_evidence("EV-1001")]
    findings = make_findings(cited=["EV-1001"])
    claim = make_message(CouncilMessageType.FINDING, {"claim": "web-01 is clean"})
    evaluator = ProposalEvaluator(MockInferenceBackend(fail_structured=True))
    challenge = evaluator.challenge_unsupported_claim(claim, evidence, findings)

    assert challenge.message_type == CouncilMessageType.CHALLENGE
    assert "cites no evidence" in challenge.payload["reason"]


def test_supported_claim_is_not_challenged():
    evidence = [make_evidence("EV-1001")]
    findings = make_findings(cited=["EV-1001"])
    claim = make_message(
        CouncilMessageType.PROPOSAL,
        {"claim": "web-01 shows lateral movement", "cited_evidence_ids": ["EV-1001"]},
    )
    evaluator = ProposalEvaluator(MockInferenceBackend(fail_structured=True))
    with pytest.raises(ValueError):
        evaluator.challenge_unsupported_claim(claim, evidence, findings)

