"""Position revision tests: evidence flips, pressure does not."""

from __future__ import annotations

from contracts.common import Position
from contracts.investigation import DebatePosition, PositionRevision
from contracts.messages import CouncilMessage, CouncilMessageType
from forensics.inference.mock import MockInferenceBackend
from forensics.reasoning.revision import PositionReviser
from tests.unit.reasoning.helpers import (
    INCIDENT,
    ScriptedBackend,
    make_evidence,
    make_message,
    make_position,
)

_EXFIL_EVIDENCE = "Outbound 40GB transfer to external IP suggests data exfiltration"
_CONDITION = "Evidence of data exfiltration to an external IP would change this position"


def _current_support() -> DebatePosition:
    return make_position(
        Position.SUPPORT,
        supporting=["EV-1001"],
        conditions=[_CONDITION],
    )


def test_contradictory_evidence_flips_support_to_oppose():
    reviser = PositionReviser(MockInferenceBackend(fail_structured=True))
    current = _current_support()
    new_ev = make_evidence("EV-2001", description=_EXFIL_EVIDENCE, event_type="network_flow")
    revision = reviser.revise_position(current, [new_ev])

    assert isinstance(revision, PositionRevision)
    assert revision.previous_position.position == Position.SUPPORT
    assert revision.new_position.position == Position.OPPOSE
    assert revision.triggering_evidence_ids == ["EV-2001"]
    assert revision.new_position.opposing_evidence_ids == ["EV-2001"]
    assert "exfiltration" in revision.explanation.lower()
    assert "pressure" in revision.explanation.lower()


def test_irrelevant_new_evidence_leaves_position_unchanged():
    reviser = PositionReviser(MockInferenceBackend(fail_structured=True))
    current = _current_support()
    new_ev = make_evidence(
        "EV-2002", description="Routine nightly backup completed", event_type="backup"
    )
    assert reviser.revise_position(current, [new_ev]) is None


def test_no_new_evidence_means_no_revision():
    reviser = PositionReviser(MockInferenceBackend(fail_structured=True))
    current = _current_support()
    assert reviser.revise_position(current, []) is None


def test_pressure_only_challenge_does_not_flip_position():
    reviser = PositionReviser(MockInferenceBackend(fail_structured=True))
    current = _current_support()
    challenge = make_message(
        CouncilMessageType.CHALLENGE,
        {
            "reason": "Everyone on the council disagrees with you; change your vote.",
            "cited_evidence_ids": ["EV-1001"],  # already-cited evidence, nothing new
        },
    )
    outcome = reviser.respond_to_challenge(challenge, current, [make_evidence("EV-1001")])

    assert isinstance(outcome, CouncilMessage)
    assert not isinstance(outcome, PositionRevision)
    assert outcome.message_type == CouncilMessageType.CHALLENGE
    assert outcome.correlation_id == challenge.message_id
    assert outcome.payload["response_type"] == "POSITION_STANDS"
    assert outcome.payload["position_maintained"] == "SUPPORT"
    assert outcome.payload["conditions_to_change_position"] == [_CONDITION]


def test_challenge_with_new_meeting_evidence_flips_position():
    reviser = PositionReviser(MockInferenceBackend(fail_structured=True))
    current = _current_support()
    new_ev = make_evidence("EV-2001", description=_EXFIL_EVIDENCE, event_type="network_flow")
    challenge = make_message(
        CouncilMessageType.CHALLENGE,
        {"reason": "New telemetry contradicts your position.", "cited_evidence_ids": ["EV-2001"]},
    )
    outcome = reviser.respond_to_challenge(challenge, current, [new_ev])

    assert isinstance(outcome, PositionRevision)
    assert outcome.previous_position.position == Position.SUPPORT
    assert outcome.new_position.position == Position.OPPOSE
    assert outcome.triggering_evidence_ids == ["EV-2001"]


def test_model_directed_revision_requires_new_evidence():
    backend = ScriptedBackend(
        [
            {
                "agent_id": "forensics-agent",
                "incident_id": INCIDENT,
                "round": 1,
                "position": "OPPOSE",
                "opposing_evidence_ids": ["EV-2001"],
                "reasoning": "Exfiltration evidence contradicts isolation proposal.",
                "confidence": 0.85,
            }
        ]
    )
    reviser = PositionReviser(backend)
    current = _current_support()
    new_ev = make_evidence("EV-2001", description=_EXFIL_EVIDENCE, event_type="network_flow")
    revision = reviser.revise_position(current, [new_ev])

    assert isinstance(revision, PositionRevision)
    assert revision.new_position.position == Position.OPPOSE
    assert revision.triggering_evidence_ids == ["EV-2001"]


def test_model_flip_without_new_evidence_is_rejected():
    backend = ScriptedBackend(
        [
            {
                "agent_id": "forensics-agent",
                "incident_id": INCIDENT,
                "round": 1,
                "position": "OPPOSE",
                # cites only OLD evidence: flip has no evidence trigger
                "opposing_evidence_ids": ["EV-1001"],
                "reasoning": "Social pressure, no new facts.",
                "confidence": 0.9,
            }
        ]
    )
    reviser = PositionReviser(backend)
    current = _current_support()
    new_ev = make_evidence(
        "EV-2002", description="Routine nightly backup completed", event_type="backup"
    )
    assert reviser.revise_position(current, [new_ev]) is None
