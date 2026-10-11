"""Model-directed investigation loop with a deterministic fallback.

The engine asks the inference backend (``generate_structured`` toward
``ToolCallRequest``) which forensic tool to call next, executes it through the
``ToolRegistry`` (audit records), and feeds results back — up to a bounded
number of steps. If the model's selection is invalid, unavailable, or the
backend fails, a deterministic rule-based plan takes over so the engine NEVER
dead-ends on a weak model. Findings cite only evidence ids that were actually
provided; violations fail loudly via ``EvidenceFabricationError``.
"""

from __future__ import annotations

import json
from collections import deque
from typing import Any

from pydantic import ValidationError

from contracts.evidence import Evidence
from contracts.inference import (
    ChatMessage,
    StructuredGenerationRequest,
    ToolCallRequest,
)
from contracts.investigation import (
    InvestigationFindings,
    InvestigationRequest,
    Severity,
    TimelineEvent,
)
from contracts.tools import ToolInvocation
from forensics.inference.base import InferenceBackend
from forensics.reasoning.validation import (
    EvidenceFabricationError,
    known_evidence_ids,
    validate_findings,
)
from forensics.tools.base import ToolRegistry

#: Tool names the model may use to signal "no further tool call needed".
_DONE_SIGNALS = frozenset({"done", "finish", "stop", "none", "no_tool"})

_SEVERITY_ORDER: list[Severity] = [
    Severity.INFO,
    Severity.LOW,
    Severity.MEDIUM,
    Severity.HIGH,
    Severity.CRITICAL,
]

_HIGH_SEVERITY_EVENT_TYPES = frozenset(
    {"data_exfiltration", "lateral_movement", "privilege_escalation", "command_execution"}
)

_TOOL_SYSTEM = (
    "You are the forensics agent of a cyber incident response council. "
    "Select the single next forensic tool to call, or answer with tool_name "
    "'finish' when no further tool call would add evidence."
)

_FINDINGS_SYSTEM = (
    "You are the forensics agent of a cyber incident response council. "
    "Summarize the investigation. You may ONLY cite evidence ids that appear "
    "in the provided evidence list; never invent evidence ids."
)

_MODEL_DONE = object()  # sentinel: the model signaled completion


class InvestigationEngine:
    """Model-directed, evidence-grounded investigation loop."""

    def __init__(
        self,
        backend: InferenceBackend,
        registry: ToolRegistry,
        *,
        agent_id: str = "forensics-agent",
        max_steps: int = 8,
    ) -> None:
        if max_steps < 1:
            raise ValueError("max_steps must be >= 1")
        self.backend = backend
        self.registry = registry
        self.agent_id = agent_id
        self.max_steps = max_steps
        self._invocations: list[ToolInvocation] = []

    @property
    def last_invocations(self) -> list[ToolInvocation]:
        """Audit records of the tool invocations from the last investigation."""
        return list(self._invocations)

    def investigate(
        self, request: InvestigationRequest, evidence: list[Evidence]
    ) -> InvestigationFindings:
        """Investigate ``request`` over the provided ``evidence``.

        Never raises on weak models: every model interaction has a
        deterministic fallback. The returned findings are guaranteed to cite
        only evidence ids present in ``evidence``.
        """
        self._invocations = []
        evidence = list(evidence)
        self._run_tool_loop(request, evidence)
        timeline = self._build_timeline(evidence)
        findings = self._synthesize(request, evidence, timeline)
        # Hard requirement: published findings cite only real evidence. This
        # final guard never fires in practice; if it does, that is a bug and
        # must fail loudly rather than publish fabricated citations.
        validate_findings(findings, evidence)
        return findings

    # ------------------------------------------------------------- tool loop

    def _run_tool_loop(
        self, request: InvestigationRequest, evidence: list[Evidence]
    ) -> None:
        if not self.registry.names():
            return
        fallback = deque(self._rule_based_plan(request, evidence))
        executed: set[tuple[str, str]] = set()
        for _ in range(self.max_steps):
            call = self._model_next_call(request, evidence, executed)
            if call is _MODEL_DONE:
                break
            if call is None:
                # Model unavailable/invalid -> deterministic fallback so the
                # engine never dead-ends on a weak model.
                if not fallback:
                    break
                call = fallback.popleft()
            fingerprint = (
                call.tool_name,
                json.dumps(call.arguments, sort_keys=True, default=str),
            )
            if fingerprint in executed:
                break  # no new information would be produced
            tool = self.registry.get(call.tool_name)
            self._invocations.append(tool.invoke(call.arguments, request.incident_id))
            executed.add(fingerprint)

    def _model_next_call(
        self,
        request: InvestigationRequest,
        evidence: list[Evidence],
        executed: set[tuple[str, str]],
    ) -> Any:
        names = self.registry.names()
        user = (
            f"Incident: {request.incident_id}\n"
            f"Question: {request.question}\n"
            f"Available evidence ids: {sorted(known_evidence_ids(evidence))}\n"
            f"Registered tools: {names}\n"
            f"Tool specs: {json.dumps(self.registry.as_tool_specs(), sort_keys=True)}\n"
            f"Already executed (do not repeat): {sorted(executed)}\n"
            f"Tool results so far: {json.dumps(self._results_digest(), default=str)}\n"
            "Return the next tool call as JSON with keys tool_name and arguments."
        )
        req = StructuredGenerationRequest(
            messages=[
                ChatMessage(role="system", content=_TOOL_SYSTEM),
                ChatMessage(role="user", content=user),
            ],
            response_model="ToolCallRequest",
        )
        try:
            result = self.backend.generate_structured(req, ToolCallRequest)
        except Exception:  # weak/failing model -> caller uses the fallback plan
            return None
        if not isinstance(result, ToolCallRequest):
            return None
        if result.tool_name.strip().lower() in _DONE_SIGNALS:
            return _MODEL_DONE
        if result.tool_name not in names:
            return None  # invalid selection -> deterministic fallback
        return result

    def _rule_based_plan(
        self, request: InvestigationRequest, evidence: list[Evidence]
    ) -> list[ToolCallRequest]:
        """Deterministic plan using only provided facts (no model output)."""
        plan: list[ToolCallRequest] = []
        valid_ids = sorted(known_evidence_ids(evidence))
        if "build_timeline" in self.registry.names() and valid_ids:
            plan.append(
                ToolCallRequest(
                    tool_name="build_timeline",
                    arguments={
                        "incident_id": request.incident_id,
                        "evidence_ids": valid_ids,
                    },
                )
            )
        if "search_logs" in self.registry.names():
            plan.append(
                ToolCallRequest(
                    tool_name="search_logs",
                    arguments={
                        "incident_id": request.incident_id,
                        "query": request.question[:200],
                    },
                )
            )
        return plan

    def _results_digest(self) -> list[str]:
        digest: list[str] = []
        for inv in self._invocations:
            if inv.error is not None:
                digest.append(f"{inv.tool_name}: ERROR {inv.error.error_code}")
            elif inv.result is not None:
                digest.append(
                    f"{inv.tool_name}: "
                    f"{json.dumps(inv.result, sort_keys=True, default=str)[:400]}"
                )
        return digest

    # -------------------------------------------------------------- timeline

    def _build_timeline(self, evidence: list[Evidence]) -> list[TimelineEvent]:
        """Reconstruct a timeline via build_timeline results and/or evidence
        timestamps. Every event cites only provided evidence ids."""
        valid_ids = known_evidence_ids(evidence)
        events: list[TimelineEvent] = []
        covered: set[str] = set()
        for inv in self._invocations:
            if inv.tool_name != "build_timeline" or inv.result is None:
                continue
            if inv.error is not None:
                continue
            for raw in inv.result.get("timeline", []) or []:
                try:
                    event = TimelineEvent.model_validate(raw)
                except ValidationError:
                    continue
                if set(event.evidence_ids) <= valid_ids:
                    events.append(event)
                    covered.update(event.evidence_ids)
        for ev in evidence:
            if ev.evidence_id in covered:
                continue
            events.append(
                TimelineEvent(
                    timestamp=ev.timestamp,
                    description=ev.description,
                    evidence_ids=[ev.evidence_id],
                    host_id=ev.host_id,
                    event_type=ev.event_type,
                )
            )
        events.sort(key=lambda e: (e.timestamp, tuple(sorted(e.evidence_ids))))
        return events

    # ------------------------------------------------------------ synthesis

    def _synthesize(
        self,
        request: InvestigationRequest,
        evidence: list[Evidence],
        timeline: list[TimelineEvent],
    ) -> InvestigationFindings:
        notes: list[str] = []
        model_findings = self._model_findings(request, evidence, timeline)
        if model_findings is None:
            notes.append(
                "Model synthesis unavailable, invalid, or cited unknown evidence; "
                "deterministic fallback findings were produced."
            )
            findings = self._deterministic_findings(request, evidence, timeline)
        else:
            # Engine-controlled fields and the validated timeline are
            # authoritative regardless of what the model returned.
            findings = model_findings.model_copy(
                update={
                    "agent_id": self.agent_id,
                    "incident_id": request.incident_id,
                    "round": request.round,
                    "timeline": timeline,
                }
            )
        for inv in self._invocations:
            if inv.error is not None:
                notes.append(
                    f"Tool {inv.tool_name} failed with {inv.error.error_code}; "
                    "its result was not used."
                )
        for note in notes:
            if note not in findings.uncertainties:
                findings.uncertainties.append(note)
        return findings

    def _model_findings(
        self,
        request: InvestigationRequest,
        evidence: list[Evidence],
        timeline: list[TimelineEvent],
    ) -> InvestigationFindings | None:
        if not evidence:
            return None  # nothing to reason over; go straight to fallback
        user = (
            f"Incident: {request.incident_id}\nRound: {request.round}\n"
            f"Question: {request.question}\n"
            "Evidence: "
            f"{json.dumps([e.model_dump(mode='json') for e in evidence], default=str)[:4000]}\n"
            "Reconstructed timeline: "
            f"{json.dumps([t.model_dump(mode='json') for t in timeline], default=str)[:2000]}\n"
            "Produce InvestigationFindings. You may ONLY cite evidence ids from "
            "the provided evidence list."
        )
        req = StructuredGenerationRequest(
            messages=[
                ChatMessage(role="system", content=_FINDINGS_SYSTEM),
                ChatMessage(role="user", content=user),
            ],
            response_model="InvestigationFindings",
            max_tokens=2048,
        )
        try:
            result = self.backend.generate_structured(req, InvestigationFindings)
        except Exception:
            return None
        if not isinstance(result, InvestigationFindings):
            return None
        if result.incident_id != request.incident_id:
            return None  # model confused the incident
        try:
            validate_findings(result, evidence)
        except EvidenceFabricationError:
            return None  # fabricated citations are never published
        return result

    def _deterministic_findings(
        self,
        request: InvestigationRequest,
        evidence: list[Evidence],
        timeline: list[TimelineEvent],
    ) -> InvestigationFindings:
        """Findings built exclusively from provided evidence — no invention."""
        n = len(evidence)
        if n == 0:
            return InvestigationFindings(
                agent_id=self.agent_id,
                incident_id=request.incident_id,
                round=request.round,
                findings=(
                    f"Unable to answer '{request.question}': no evidence was provided "
                    f"for incident {request.incident_id}. No conclusions are drawn."
                ),
                cited_evidence_ids=[],
                confidence=0.05,
                uncertainties=["No evidence was provided; nothing can be concluded."],
                timeline=[],
                recommended_actions=[
                    "Escalate to human incident responders: no evidence is available.",
                    "Request evidence collection (host telemetry, logs, network "
                    "flows) before further analysis.",
                ],
                severity_assessment=Severity.INFO,
            )
        confidence = {1: 0.35, 2: 0.6}.get(n, 0.8)
        uncertainties: list[str] = []
        actions: list[str] = []
        if n <= 2:
            uncertainties.append(
                f"Only {n} evidence item(s) available; conclusions are preliminary."
            )
        if n == 1:
            actions.append(
                "Escalate to senior incident responders for manual corroboration: "
                "evidence is insufficient for confident conclusions."
            )
        actions.append(
            "Preserve the cited evidence and expand collection around the "
            "reconstructed timeline."
        )
        event_types = sorted({e.event_type for e in evidence})
        hosts = sorted({e.host_id for e in evidence})
        span = (
            f"{timeline[0].timestamp.isoformat()} to "
            f"{timeline[-1].timestamp.isoformat()}"
            if timeline
            else "n/a"
        )
        findings_text = (
            f"Question '{request.question}' investigated over {n} evidence item(s) "
            f"(event types: {', '.join(event_types)}; hosts: {', '.join(hosts)}; "
            f"time span {span} UTC). The cited evidence establishes the events on "
            "the timeline. Deterministic fallback synthesis: no inference beyond "
            "the provided evidence was made."
        )
        return InvestigationFindings(
            agent_id=self.agent_id,
            incident_id=request.incident_id,
            round=request.round,
            findings=findings_text,
            cited_evidence_ids=sorted(known_evidence_ids(evidence)),
            confidence=confidence,
            uncertainties=uncertainties,
            timeline=timeline,
            recommended_actions=actions,
            severity_assessment=self._assess_severity(evidence),
        )

    def _assess_severity(self, evidence: list[Evidence]) -> Severity:
        found: list[Severity] = []
        for ev in evidence:
            raw = ev.raw_data.get("severity")
            if isinstance(raw, str):
                try:
                    found.append(Severity(raw.strip().upper()))
                except ValueError:
                    continue
        if found:
            return max(found, key=_SEVERITY_ORDER.index)
        if any(e.event_type in _HIGH_SEVERITY_EVENT_TYPES for e in evidence):
            return Severity.HIGH
        return Severity.MEDIUM



