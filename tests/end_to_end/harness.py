"""Injectable engine-style investigation harness for end-to-end tests.

`MockInvestigationEngine` wires an *injected* inference backend and tool
registry into the investigation loop that the real reasoning engine
(feat/reasoning) will provide after the coordinator merges it. Tests and
the forensics API service depend only on the public methods below — never
on the mock classes themselves — so mocks stay swappable for real
implementations.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any, Protocol

from contracts.common import Position
from contracts.evidence import Evidence
from contracts.inference import ChatMessage, StructuredGenerationRequest
from contracts.investigation import (
    DebatePosition,
    InvestigationFindings,
    InvestigationRequest,
    PositionRevision,
    TimelineEvent,
)
from contracts.tools import ToolInvocation
from forensics.inference.base import InferenceBackend, InferenceBackendError
from forensics.tools.base import ToolRegistry

#: Decides, given new evidence and the current position, whether to revise.
RevisionDecider = Callable[[Evidence, DebatePosition], bool]


def _always_revise(evidence: Evidence, position: DebatePosition) -> bool:
    return True


def _generation(question: str, response_model: str) -> StructuredGenerationRequest:
    return StructuredGenerationRequest(
        messages=[ChatMessage(role="user", content=question)],
        response_model=response_model,
    )


class InvestigationEngine(Protocol):
    """Minimum engine surface the forensics API service depends on.

    The real reasoning engine (feat/reasoning) must provide these three
    methods; anything else about it is free to change.
    """

    def investigate(self, request: InvestigationRequest) -> InvestigationFindings: ...

    def evaluate_proposal(
        self, incident_id: str, round: int, proposal: dict[str, Any]
    ) -> DebatePosition: ...

    def consider_evidence(self, evidence: Evidence) -> PositionRevision | None: ...


class MockInvestigationEngine:
    """Deterministic engine-style loop over injected backend + tools.

    Produces a complete audit trail (`tool_audit`) and tracks the latest
    published position per incident so evidence can trigger revisions.
    """

    def __init__(
        self,
        *,
        backend: InferenceBackend,
        registry: ToolRegistry,
        agent_id: str = "forensics-agent",
        revision_decider: RevisionDecider = _always_revise,
    ) -> None:
        self.backend = backend
        self.registry = registry
        self.agent_id = agent_id
        self.revision_decider = revision_decider
        self.tool_audit: list[ToolInvocation] = []
        self.positions: dict[str, DebatePosition] = {}

    # ------------------------------------------------------------------ tools

    def _invoke(self, name: str, arguments: dict[str, Any], incident_id: str) -> ToolInvocation:
        invocation = self.registry.get(name).invoke(arguments, incident_id)
        self.tool_audit.append(invocation)
        return invocation

    # ----------------------------------------------------------------- engine

    def investigate(self, request: InvestigationRequest) -> InvestigationFindings:
        search = self._invoke(
            "search_logs",
            {"incident_id": request.incident_id, "query": request.question},
            request.incident_id,
        )
        cited = list(request.available_evidence_ids)
        if search.result is not None:
            cited.extend(search.result.get("matched_evidence_ids", []))
        cited = sorted(dict.fromkeys(cited))

        timeline: list[TimelineEvent] = []
        if cited:
            built = self._invoke(
                "build_timeline",
                {"incident_id": request.incident_id, "evidence_ids": cited},
                request.incident_id,
            )
            if built.result is not None:
                timeline = [
                    TimelineEvent.model_validate(event)
                    for event in built.result.get("timeline", [])
                ]

        question = json.dumps(
            {"question": request.question, "cited_evidence_ids": cited}, sort_keys=True
        )
        generated = self.backend.generate_structured(
            _generation(question, "InvestigationFindings"), InvestigationFindings
        )
        if not isinstance(generated, InvestigationFindings):
            raise InferenceBackendError(
                f"backend returned {type(generated).__name__}, expected InvestigationFindings"
            )
        # Reconcile canned mock output with the live request context; a real
        # engine derives these fields from the prompt instead of overriding.
        return generated.model_copy(
            update={
                "agent_id": self.agent_id,
                "incident_id": request.incident_id,
                "round": request.round,
                "cited_evidence_ids": cited,
                "timeline": timeline or list(generated.timeline),
            }
        )

    def evaluate_proposal(
        self, incident_id: str, round: int, proposal: dict[str, Any]  # noqa: A002
    ) -> DebatePosition:
        question = json.dumps({"incident_id": incident_id, "proposal": proposal}, sort_keys=True)
        generated = self.backend.generate_structured(
            _generation(question, "DebatePosition"), DebatePosition
        )
        if not isinstance(generated, DebatePosition):
            raise InferenceBackendError(
                f"backend returned {type(generated).__name__}, expected DebatePosition"
            )
        position = generated.model_copy(
            update={"agent_id": self.agent_id, "incident_id": incident_id, "round": round}
        )
        self.positions[incident_id] = position
        return position

    def consider_evidence(self, evidence: Evidence) -> PositionRevision | None:
        previous = self.positions.get(evidence.incident_id)
        if previous is None or not self.revision_decider(evidence, previous):
            return None
        new_stance = (
            Position.OPPOSE if previous.position is not Position.OPPOSE else Position.SUPPORT
        )
        new_position = previous.model_copy(
            update={
                "round": previous.round + 1,
                "position": new_stance,
                "opposing_evidence_ids": sorted(
                    set(previous.opposing_evidence_ids) | {evidence.evidence_id}
                ),
                "reasoning": f"Position revised after new evidence {evidence.evidence_id}",
            }
        )
        revision = PositionRevision(
            agent_id=self.agent_id,
            incident_id=evidence.incident_id,
            round=new_position.round,
            previous_position=previous,
            new_position=new_position,
            triggering_evidence_ids=[evidence.evidence_id],
            explanation=f"New evidence changed the assessment: {evidence.description}",
        )
        self.positions[evidence.incident_id] = new_position
        return revision
