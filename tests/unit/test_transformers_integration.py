"""Integration tests: REAL local generation with the SOC fine-tune.

Marked ``@pytest.mark.integration``. Skipped gracefully when the weights are
not present in the HF cache (HF_HOME) or torch/transformers are missing — no
network downloads are triggered from tests.
"""

from __future__ import annotations

import os

import pytest

from contracts.inference import ChatMessage, InferenceRequest, ToolSpec
from forensics.inference.qwen_tool_parser import parse_qwen_tool_calls

pytestmark = pytest.mark.integration

HF_HOME = os.environ.get(
    "HF_HOME", "/home/asus/forensics-agent-coordination/hf-cache"
)
SOC_REPO_DIR = os.path.join(
    HF_HOME, "hub", "models--alirezaaminzadeh--soc-analyst-tool-use"
)


def _weights_cached() -> bool:
    try:
        import torch  # noqa: F401
        import transformers  # noqa: F401
    except ImportError:
        return False
    return os.path.isdir(SOC_REPO_DIR) and any(
        name.endswith(".safetensors")
        for root, _dirs, files in os.walk(SOC_REPO_DIR)
        for name in files
    )


@pytest.fixture(scope="module")
def soc_backend():
    if not _weights_cached():
        pytest.skip(
            "SOC model weights not cached in HF_HOME (or deps missing) — "
            "run scripts/validate_inference.py --backend transformers first"
        )
    from forensics.inference.transformers_backend import TransformersBackend

    backend = TransformersBackend(timeout_s=180.0)
    if not backend.health_check():
        pytest.skip("SOC model loaded but 1-token generation failed")
    return backend


def test_soc_generate_real(soc_backend):
    result = soc_backend.generate(
        InferenceRequest(
            messages=[
                ChatMessage(role="user", content="Name one common Linux persistence mechanism.")
            ],
            max_tokens=64,
            temperature=0.1,
        )
    )
    assert result.backend_name == "transformers"
    assert result.text.strip()


def test_soc_tool_call_real(soc_backend):
    tools = [
        ToolSpec(
            name="query_dns_logs",
            description="Query DNS logs for a hostname.",
            parameters={"type": "object", "properties": {"hostname": {"type": "string"}}},
        )
    ]
    result = soc_backend.generate(
        InferenceRequest(
            messages=[
                ChatMessage(
                    role="user",
                    content="Investigate DNS traffic for host web-01.forensics.local.",
                )
            ],
            tools=tools,
            max_tokens=128,
            temperature=0.1,
        )
    )
    # The fine-tune may or may not emit <<{...}>> blocks; both paths must be
    # consistent: tool_calls parsed iff finish_reason is TOOL_CALL.
    assert bool(result.tool_calls) == (result.finish_reason.value == "TOOL_CALL")


def test_soc_tool_parser_used_for_blocks():
    # Pure-parser regression tied to the SOC convention (no weights needed).
    calls = parse_qwen_tool_calls('<<{"name": "query_dns_logs", "arguments": {}}>>')
    assert calls[0].tool_name == "query_dns_logs"
