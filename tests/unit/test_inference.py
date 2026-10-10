"""Inference interface tests using the mock backend (no GPU, no weights)."""

from __future__ import annotations

import pytest
from pydantic import BaseModel, ValidationError

from contracts.inference import (
    ChatMessage,
    InferenceRequest,
    StructuredGenerationRequest,
)
from contracts.investigation import InvestigationFindings
from forensics.inference.base import (
    InferenceBackend,
    InferenceBackendError,
    InferenceTimeoutError,
)
from forensics.inference.mock import MockInferenceBackend, parse_json_candidate


def _req(text: str = "hello") -> InferenceRequest:
    return InferenceRequest(messages=[ChatMessage(role="user", content=text)])


def test_abstract_cannot_instantiate():
    with pytest.raises(TypeError):
        InferenceBackend()  # type: ignore[abstract]


def test_generate_valid():
    result = MockInferenceBackend().generate(_req("ping"))
    assert result.text == "[mock] ping"
    assert result.backend_name == "mock"


def test_invalid_requests_rejected():
    with pytest.raises(ValidationError):
        InferenceRequest(messages=[])
    with pytest.raises(ValidationError):
        InferenceRequest(messages=[ChatMessage(role="user", content="x")], max_tokens=0)
    with pytest.raises(ValidationError):
        InferenceRequest(messages=[ChatMessage(role="user", content="x")], temperature=5)


def test_structured_generation_valid():
    req = StructuredGenerationRequest(
        messages=[ChatMessage(role="user", content="summarize")],
        response_model="InvestigationFindings",
    )
    out = MockInferenceBackend().generate_structured(req, InvestigationFindings)
    assert isinstance(out, InvestigationFindings)
    assert 0.0 <= out.confidence <= 1.0


def test_structured_rejects_non_pydantic_model():
    req = StructuredGenerationRequest(
        messages=[ChatMessage(role="user", content="x")], response_model="dict"
    )
    with pytest.raises(InferenceBackendError):
        MockInferenceBackend().generate_structured(req, dict)


def test_structured_validation_failure_becomes_backend_error():
    class Strict(BaseModel):
        required_field: str

    req = StructuredGenerationRequest(
        messages=[ChatMessage(role="user", content="x")], response_model="Strict"
    )
    with pytest.raises(InferenceBackendError):
        MockInferenceBackend().generate_structured(req, Strict)


def test_backend_errors():
    with pytest.raises(InferenceBackendError):
        MockInferenceBackend(fail_generate=True).generate(_req())
    req = StructuredGenerationRequest(
        messages=[ChatMessage(role="user", content="x")], response_model="InvestigationFindings"
    )
    with pytest.raises(InferenceBackendError):
        MockInferenceBackend(fail_structured=True).generate_structured(req, InvestigationFindings)


def test_timeout_error_type():
    err = InferenceTimeoutError(5.0)
    assert isinstance(err, InferenceBackendError)
    assert err.timeout_s == 5.0


def test_health_and_metadata():
    backend = MockInferenceBackend()
    assert backend.health_check() is True
    assert MockInferenceBackend(fail_generate=True, fail_structured=True).health_check() is False
    meta = backend.get_model_metadata()
    assert meta.is_mock and meta.context_window > 0
    assert backend.supports_tools() is False


def test_parse_json_candidate():
    assert parse_json_candidate('text {"a": 1} tail') == {"a": 1}
    assert parse_json_candidate('```json\n{"b": 2}\n```') == {"b": 2}
    with pytest.raises(InferenceBackendError):
        parse_json_candidate("no json here")
