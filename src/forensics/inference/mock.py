"""Mock inference backend: validates the interface without GPU or weights."""

from __future__ import annotations

import json
import time
from typing import Any

from pydantic import BaseModel, ValidationError

from contracts.inference import (
    FinishReason,
    InferenceRequest,
    InferenceResult,
    ModelMetadata,
    StructuredGenerationRequest,
)
from forensics.inference.base import InferenceBackend, InferenceBackendError


class MockInferenceBackend(InferenceBackend):
    """Deterministic mock used by tests and Stage B scaffolding.

    Configurable failure modes:
      - fail_generate=True      -> generate() raises InferenceBackendError
      - fail_structured=True    -> generate_structured() raises
      - delay_s=N               -> sleep N seconds (for timeout tests)
    """

    def __init__(
        self,
        *,
        model_id: str = "mock/mock-forensics-1b",
        fail_generate: bool = False,
        fail_structured: bool = False,
        delay_s: float = 0.0,
        timeout_s: float = 60.0,
    ) -> None:
        self.model_id = model_id
        self.fail_generate = fail_generate
        self.fail_structured = fail_structured
        self.delay_s = delay_s
        self.timeout_s = timeout_s
        self.calls: list[str] = []

    def _respect_timeout(self) -> None:
        if self.delay_s > 0:
            time.sleep(self.delay_s)
        # Timeouts are enforced by the caller/wrapper; the mock records the
        # configured limit so tests can assert timeout behaviour.

    def generate(self, request: InferenceRequest) -> InferenceResult:
        self.calls.append("generate")
        self._respect_timeout()
        if self.fail_generate:
            raise InferenceBackendError("mock backend configured to fail")
        last_user = next((m.content for m in reversed(request.messages) if m.role == "user"), "")
        return InferenceResult(
            text=f"[mock] {last_user}",
            finish_reason=FinishReason.STOP,
            backend_name="mock",
        )

    def generate_structured(
        self, request: StructuredGenerationRequest, response_model: type
    ) -> Any:
        self.calls.append("generate_structured")
        self._respect_timeout()
        if self.fail_structured:
            raise InferenceBackendError("mock backend configured to fail structured output")
        if not (isinstance(response_model, type) and issubclass(response_model, BaseModel)):
            raise InferenceBackendError("response_model must be a Pydantic model class")
        payload = self._fake_payload(request, response_model)
        try:
            return response_model.model_validate(payload)
        except ValidationError as exc:
            raise InferenceBackendError(f"structured output failed validation: {exc}") from exc

    @staticmethod
    def _fake_payload(
        request: StructuredGenerationRequest, response_model: type
    ) -> dict[str, Any]:
        """Build a minimal valid payload for common contract models."""
        name = response_model.__name__
        if name == "InvestigationFindings":
            return {
                "agent_id": "forensics-agent",
                "incident_id": "INC-MOCK-001",
                "round": 1,
                "findings": "[mock] lateral movement detected on web-01",
                "cited_evidence_ids": ["EV-0001"],
                "confidence": 0.8,
                "uncertainties": ["mock uncertainty"],
                "timeline": [],
                "recommended_actions": ["isolate web-01"],
            }
        if name == "DebatePosition":
            return {
                "agent_id": "forensics-agent",
                "incident_id": "INC-MOCK-001",
                "round": 1,
                "position": "SUPPORT",
                "reasoning": "[mock] evidence supports the proposal",
                "confidence": 0.7,
            }
        # Generic fallback: try all-default construction.
        return {}

    def health_check(self) -> bool:
        self.calls.append("health_check")
        return not (self.fail_generate and self.fail_structured)

    def get_model_metadata(self) -> ModelMetadata:
        return ModelMetadata(
            model_id=self.model_id,
            backend_name="mock",
            context_window=8192,
            supports_native_tool_calls=False,
            supports_structured_output=True,
            is_mock=True,
        )


def parse_json_candidate(text: str) -> Any:
    """Parse the first JSON object found in model text.

    Shared helper for real backends: model output often wraps JSON in prose
    or code fences. Raises InferenceBackendError if no JSON is found.
    """
    fenced = text.split("```")
    candidates = [fenced[i] for i in range(1, len(fenced), 2)]
    candidates = [c.removeprefix("json").strip() for c in candidates]
    candidates.append(text.strip())
    for candidate in candidates:
        start = candidate.find("{")
        end = candidate.rfind("}")
        if start != -1 and end > start:
            try:
                return json.loads(candidate[start : end + 1])
            except json.JSONDecodeError:
                continue
    raise InferenceBackendError("no parsable JSON object in model output")
