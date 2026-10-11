"""Integration tests: REAL calls to the local llama.cpp server (:8000).

Marked ``@pytest.mark.integration``. These tests are skipped gracefully when
the server is unreachable — they never fake server responses as real results.
Run with: pytest -m integration
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel

from contracts.inference import (
    ChatMessage,
    InferenceRequest,
    StructuredGenerationRequest,
    ToolSpec,
)
from forensics.inference.llamacpp import LlamaCppBackend

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def live_backend() -> LlamaCppBackend:
    backend = LlamaCppBackend(timeout_s=90.0)
    if not backend.health_check():
        pytest.skip("llama.cpp server not reachable at http://127.0.0.1:8000/v1")
    return backend


class _Verdict(BaseModel):
    """Small structured-output model suitable for an 8B model to fill."""

    verdict: str
    confidence: float


def test_health_check_real(live_backend: LlamaCppBackend):
    assert live_backend.health_check() is True


def test_metadata_real(live_backend: LlamaCppBackend):
    meta = live_backend.get_model_metadata()
    assert meta.model_id == "fdtn-ai/Foundation-Sec-8B-Instruct"
    assert meta.backend_name == "llamacpp"
    assert meta.context_window == 131072  # real value reported by /v1/models
    assert meta.supports_native_tool_calls is False
    assert meta.is_mock is False


def test_generate_real(live_backend: LlamaCppBackend):
    result = live_backend.generate(
        InferenceRequest(
            messages=[
                ChatMessage(
                    role="user",
                    content=(
                        "In one short sentence: what is /var/log/auth.log used for "
                        "on a Linux host?"
                    ),
                )
            ],
            max_tokens=80,
            temperature=0.1,
        )
    )
    assert result.backend_name == "llamacpp"
    assert result.text.strip(), "server returned empty completion"
    assert result.completion_tokens > 0
    assert live_backend.last_latency_ms is not None
    assert live_backend.last_latency_ms > 0


def test_generate_structured_real(live_backend: LlamaCppBackend):
    request = StructuredGenerationRequest(
        messages=[
            ChatMessage(
                role="user",
                content=(
                    "Host web-01 shows 40k failed SSH logins from one IP in the last "
                    "hour. Answer strictly as JSON."
                ),
            )
        ],
        response_model="_Verdict",
        max_tokens=512,
    )
    out = live_backend.generate_structured(request, _Verdict)
    assert isinstance(out, _Verdict)
    assert out.verdict
    assert 0.0 <= out.confidence <= 1.0


def test_generate_with_tool_emulation_real(live_backend: LlamaCppBackend):
    tools = [
        ToolSpec(
            name="query_dns_logs",
            description="Query DNS logs for a hostname over recent minutes.",
            parameters={
                "type": "object",
                "properties": {"hostname": {"type": "string"}, "minutes": {"type": "integer"}},
                "required": ["hostname"],
            },
        )
    ]
    result = live_backend.generate(
        InferenceRequest(
            messages=[
                ChatMessage(
                    role="user",
                    content=(
                        "Please investigate unusual DNS traffic for host "
                        "web-01.forensics.local over the last 30 minutes."
                    ),
                )
            ],
            tools=tools,
            max_tokens=256,
            temperature=0.1,
        )
    )
    # Either the model emits an emulated tool call (parsed) or answers in
    # prose — both are valid behaviors for a non-tool-native model.
    assert result.text or result.tool_calls
