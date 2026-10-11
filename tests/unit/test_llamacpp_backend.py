"""Unit tests for the llama.cpp backend using a fake HTTP transport.

No network is touched: the transport callable is replaced with a canned
responder that records every request.
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from pydantic import BaseModel

from contracts.inference import (
    ChatMessage,
    InferenceRequest,
    StructuredGenerationRequest,
    ToolSpec,
)
from forensics.inference.base import InferenceBackendError, InferenceTimeoutError
from forensics.inference.llamacpp import (
    LlamaCppBackend,
    parse_emulated_tool_calls,
)

MODEL_ID = "fdtn-ai/Foundation-Sec-8B-Instruct"


def _completion_body(text: str, finish_reason: str = "stop") -> dict[str, Any]:
    return {
        "choices": [
            {"message": {"role": "assistant", "content": text}, "finish_reason": finish_reason}
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5},
    }


class FakeTransport:
    """Canned transport: replies come from a queue; requests are recorded."""

    def __init__(self, replies: list[Any]) -> None:
        self.replies = list(replies)
        self.requests: list[tuple[str, str, dict[str, Any] | None, float]] = []

    def __call__(
        self, method: str, url: str, payload: dict[str, Any] | None, timeout_s: float
    ) -> tuple[int, dict[str, Any]]:
        self.requests.append((method, url, payload, timeout_s))
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return 200, reply


def _models_body() -> dict[str, Any]:
    return {
        "data": [
            {
                "id": MODEL_ID,
                "meta": {"n_ctx_train": 131072, "n_params": 8031309888},
            }
        ]
    }


def _backend(transport: FakeTransport) -> LlamaCppBackend:
    return LlamaCppBackend(transport=transport, timeout_s=30.0)


def _req(text: str = "ping", **kwargs: Any) -> InferenceRequest:
    return InferenceRequest(messages=[ChatMessage(role="user", content=text)], **kwargs)


def test_generate_maps_request_fields_and_measures_latency():
    transport = FakeTransport([_completion_body("pong")])
    result = _backend(transport).generate(
        _req("hello", max_tokens=64, temperature=0.7, stop=["END"])
    )
    assert result.text == "pong"
    assert result.backend_name == "llamacpp"
    assert result.prompt_tokens == 10 and result.completion_tokens == 5
    method, url, payload, _timeout = transport.requests[0]
    assert method == "POST" and url.endswith("/chat/completions")
    assert payload is not None
    assert payload["model"] == MODEL_ID
    assert payload["max_tokens"] == 64
    assert payload["temperature"] == 0.7
    assert payload["stop"] == ["END"]
    assert payload["messages"] == [{"role": "user", "content": "hello"}]
    assert result.finish_reason.value == "STOP"
    backend = _backend(FakeTransport([]))
    assert backend.last_latency_ms is None  # no call made yet
    assert backend.latencies_ms == []


def test_generate_with_tools_injects_emulation_prompt():
    transport = FakeTransport(
        [_completion_body('{"tool_calls": [{"name": "list_processes", "arguments": {}}]}')]
    )
    tools = [
        ToolSpec(
            name="list_processes",
            description="List running processes",
            parameters={"type": "object", "properties": {}},
        )
    ]
    result = _backend(transport).generate(_req("check the host", tools=tools))
    _method, _url, payload, _t = transport.requests[0]
    assert payload is not None
    first = payload["messages"][0]
    assert first["role"] == "system"
    assert "list_processes" in first["content"]
    assert result.finish_reason.value == "TOOL_CALL"
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].tool_name == "list_processes"


def test_generate_finish_reason_max_tokens():
    transport = FakeTransport([_completion_body("trunc", finish_reason="length")])
    result = _backend(transport).generate(_req())
    assert result.finish_reason.value == "MAX_TOKENS"


def test_generate_wraps_malformed_response():
    transport = FakeTransport([{"unexpected": "shape"}])
    with pytest.raises(InferenceBackendError):
        _backend(transport).generate(_req())


def test_timeout_error_propagates_and_is_specific():
    transport = FakeTransport([InferenceTimeoutError(30.0)])
    with pytest.raises(InferenceTimeoutError):
        _backend(transport).generate(_req())


def test_http_error_wrapped_in_backend_error():
    transport = FakeTransport([InferenceBackendError("HTTP 500: boom")])
    with pytest.raises(InferenceBackendError):
        _backend(transport).generate(_req())


class _Verdict(BaseModel):
    verdict: str
    confidence: float


def _structured_req() -> StructuredGenerationRequest:
    return StructuredGenerationRequest(
        messages=[ChatMessage(role="user", content="Was the host compromised?")],
        response_model="_Verdict",
    )


def test_structured_success_first_attempt():
    transport = FakeTransport([_completion_body('{"verdict": "yes", "confidence": 0.9}')])
    out = _backend(transport).generate_structured(_structured_req(), _Verdict)
    assert isinstance(out, _Verdict) and out.verdict == "yes"
    assert len(transport.requests) == 1
    _method, _url, payload, _t = transport.requests[0]
    assert payload is not None
    system = payload["messages"][0]["content"]
    assert '"verdict"' in system  # JSON schema prompt-engineered into the request


def test_structured_retries_once_with_error_appended():
    transport = FakeTransport(
        [
            _completion_body("I think yes"),  # unparsable first reply
            _completion_body('{"verdict": "yes", "confidence": 0.8}'),
        ]
    )
    out = _backend(transport).generate_structured(_structured_req(), _Verdict)
    assert isinstance(out, _Verdict)
    assert len(transport.requests) == 2
    second_payload = transport.requests[1][2]
    assert second_payload is not None
    roles = [m["role"] for m in second_payload["messages"]]
    assert roles[-2:] == ["assistant", "user"]
    assert "invalid" in second_payload["messages"][-1]["content"].lower()


def test_structured_retries_on_validation_failure():
    transport = FakeTransport(
        [
            _completion_body('{"verdict": "yes"}'),  # missing confidence
            _completion_body('{"verdict": "yes", "confidence": 1.0}'),
        ]
    )
    out = _backend(transport).generate_structured(_structured_req(), _Verdict)
    assert out.confidence == 1.0
    assert len(transport.requests) == 2


def test_structured_fails_after_retry():
    transport = FakeTransport(
        [_completion_body("nope"), _completion_body("still nope")]
    )
    with pytest.raises(InferenceBackendError, match="after retry"):
        _backend(transport).generate_structured(_structured_req(), _Verdict)
    assert len(transport.requests) == 2


def test_structured_rejects_non_pydantic_model():
    transport = FakeTransport([])
    with pytest.raises(InferenceBackendError, match="Pydantic"):
        _backend(transport).generate_structured(_structured_req(), dict)


def test_health_check_true_when_model_served():
    transport = FakeTransport([_models_body()])
    assert _backend(transport).health_check() is True
    method, url, payload, timeout = transport.requests[0]
    assert method == "GET" and url.endswith("/models") and payload is None
    assert timeout == 5.0  # short health timeout


def test_health_check_false_when_model_missing():
    transport = FakeTransport([{"data": [{"id": "some/other-model"}]}])
    assert _backend(transport).health_check() is False


def test_health_check_false_on_error():
    transport = FakeTransport([InferenceBackendError("connection refused")])
    assert _backend(transport).health_check() is False


def test_metadata_uses_real_server_values():
    transport = FakeTransport([_models_body()])
    meta = _backend(transport).get_model_metadata()
    assert meta.model_id == MODEL_ID
    assert meta.backend_name == "llamacpp"
    assert meta.context_window == 131072  # real value from /v1/models meta
    assert meta.supports_native_tool_calls is False  # never pretend tool support
    assert meta.supports_structured_output is True
    assert meta.is_mock is False


def test_metadata_fails_for_unknown_model():
    transport = FakeTransport([{"data": []}])
    with pytest.raises(InferenceBackendError, match="not served"):
        _backend(transport).get_model_metadata()


def test_env_overrides(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("FORENSICS_LLAMACPP_BASE_URL", "http://example.test:9999/v1/")
    monkeypatch.setenv("FORENSICS_LLAMACPP_MODEL", "custom/model")
    backend = LlamaCppBackend()
    assert backend.base_url == "http://example.test:9999/v1"
    assert backend.model_id == "custom/model"


def test_latency_history_recorded():
    transport = FakeTransport([_completion_body("a"), _completion_body("b")])
    backend = _backend(transport)
    backend.generate(_req())
    backend.generate(_req())
    assert len(backend.latencies_ms) == 2
    assert backend.last_latency_ms == backend.latencies_ms[-1]
    assert all(value >= 0 for value in backend.latencies_ms)


def test_parse_emulated_tool_calls_shapes():
    wrapped = '{"tool_calls": [{"name": "t", "arguments": {"a": 1}}]}'
    assert parse_emulated_tool_calls(wrapped)[0].tool_name == "t"
    bare_list = '[{"name": "t", "arguments": {"a": 1}}]'
    assert parse_emulated_tool_calls(bare_list)[0].arguments == {"a": 1}
    single = '{"name": "t", "arguments": {"a": 1}}'
    assert parse_emulated_tool_calls(single)[0].tool_name == "t"
    string_args = '{"name": "t", "arguments": ' + json.dumps(json.dumps({"a": 1})) + "}"
    assert parse_emulated_tool_calls(string_args)[0].arguments == {"a": 1}
    assert parse_emulated_tool_calls("plain prose, no JSON") == []
    assert parse_emulated_tool_calls('{"tool_calls": [{"no_name": true}]}') == []


def test_emulated_tool_calls_in_code_fence():
    text = '```json\n{"tool_calls": [{"name": "t", "arguments": {}}]}\n```'
    assert parse_emulated_tool_calls(text)[0].tool_name == "t"


def test_wire_json_serialization_roundtrip():
    payload_json = json.dumps(_req().model_dump())
    assert InferenceRequest.model_validate_json(payload_json).messages[0].content == "ping"


