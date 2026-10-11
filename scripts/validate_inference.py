#!/usr/bin/env python3
"""Functional validation: REAL inference calls with latency numbers.

Usage (from the worktree root, venv activated):

    python scripts/validate_inference.py                     # llama.cpp (:8000)
    python scripts/validate_inference.py --rounds 5         # more structured rounds
    python scripts/validate_inference.py --backend transformers  # SOC fine-tune

Never fakes server responses: every reported number comes from a real call.
Exits non-zero when generate() fails; prints the structured success rate.
"""

from __future__ import annotations

import argparse
import os
import statistics
import sys
import time
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from pydantic import BaseModel  # noqa: E402

from contracts.inference import (  # noqa: E402
    ChatMessage,
    InferenceRequest,
    StructuredGenerationRequest,
    ToolSpec,
)
from forensics.inference.base import InferenceBackend, InferenceBackendError  # noqa: E402
from forensics.inference.factory import create_backend  # noqa: E402


class Verdict(BaseModel):
    """Structured output contract used for validation runs."""

    verdict: str
    confidence: float


SCENARIOS = [
    "Host web-01 shows 40000 failed SSH logins from one external IP in the last hour.",
    "An attacker likely added an authorized_keys entry to enable persistence.",
    "Cron jobs on host db-02 reference a suspicious script in /tmp.",
]

TOOL_SCENARIO = (
    "Investigate unusual DNS traffic for host web-01.forensics.local over the "
    "last 30 minutes."
)


def _run_generate(backend: InferenceBackend) -> bool:
    t0 = time.perf_counter()
    result = backend.generate(
        InferenceRequest(
            messages=[
                ChatMessage(
                    role="user",
                    content=(
                        "You are a SOC analyst. In one short sentence: what does a "
                        "spike in failed SSH logins from a single IP usually indicate?"
                    ),
                )
            ],
            max_tokens=120,
            temperature=0.1,
        )
    )
    gen_ms = (time.perf_counter() - t0) * 1000.0
    latency = getattr(backend, "last_latency_ms", None)
    print(f"generate latency_ms    : {gen_ms:.0f} (backend-measured: {latency})")
    print(
        f"generate finish_reason : {result.finish_reason.value} "
        f"(tokens={result.completion_tokens})"
    )
    print("generate text sample   :")
    for line in result.text.strip().splitlines()[:6]:
        print(f"    | {line}")
    return bool(result.text.strip())


def _run_tool_emulation(backend_name: str, backend: InferenceBackend) -> int:
    tools = [
        ToolSpec(
            name="query_dns_logs",
            description="Query DNS logs for a hostname over recent minutes.",
            parameters={
                "type": "object",
                "properties": {
                    "hostname": {"type": "string"},
                    "minutes": {"type": "integer"},
                },
                "required": ["hostname"],
            },
        )
    ]
    try:
        tool_result = backend.generate(
            InferenceRequest(
                messages=[ChatMessage(role="user", content=TOOL_SCENARIO)],
                tools=tools,
                max_tokens=256,
                temperature=0.1,
            )
        )
    except InferenceBackendError as exc:
        print(f"tool-call emulation     : ERROR {exc}")
        return -1
    print(
        f"tool-call emulation     : {len(tool_result.tool_calls)} call(s) parsed, "
        f"finish_reason={tool_result.finish_reason.value}"
    )
    return len(tool_result.tool_calls)


def _run_structured(backend: InferenceBackend, rounds: int) -> tuple[int, list[float]]:
    successes = 0
    latencies: list[float] = []
    for i in range(rounds):
        scenario = SCENARIOS[i % len(SCENARIOS)]
        request = StructuredGenerationRequest(
            messages=[ChatMessage(role="user", content=scenario)],
            response_model="Verdict",
            max_tokens=512,
        )
        t0 = time.perf_counter()
        try:
            out = backend.generate_structured(request, Verdict)
            elapsed = (time.perf_counter() - t0) * 1000.0
            latencies.append(elapsed)
            if isinstance(out, Verdict) and 0.0 <= out.confidence <= 1.0:
                successes += 1
                print(
                    f"structured round {i + 1}/{rounds}  : OK ({elapsed:.0f} ms) "
                    f"verdict={out.verdict!r} confidence={out.confidence}"
                )
            else:
                print(f"structured round {i + 1}/{rounds}  : INVALID ({elapsed:.0f} ms)")
        except InferenceBackendError as exc:
            elapsed = (time.perf_counter() - t0) * 1000.0
            latencies.append(elapsed)
            print(
                f"structured round {i + 1}/{rounds}  : ERROR ({elapsed:.0f} ms): "
                f"{str(exc)[:120]}"
            )
    return successes, latencies


def validate(backend_name: str, rounds: int, base_url: str | None) -> int:
    kwargs: dict[str, Any] = {}
    if base_url:
        kwargs["base_url"] = base_url
    if backend_name == "transformers":
        os.environ.setdefault("HF_HOME", "/home/asus/forensics-agent-coordination/hf-cache")
        kwargs["timeout_s"] = 300.0
    backend: InferenceBackend = create_backend(backend_name, **kwargs)

    print(f"=== validate_inference: backend={backend_name} ===")
    t0 = time.perf_counter()
    healthy = backend.health_check()
    print(
        f"health_check           : {'OK' if healthy else 'FAILED'} "
        f"({(time.perf_counter() - t0) * 1000:.0f} ms)"
    )
    if not healthy:
        print("RESULT: FAIL (backend unhealthy)")
        return 1

    meta = backend.get_model_metadata()
    print(
        f"model                  : {meta.model_id} (backend={meta.backend_name}, "
        f"ctx={meta.context_window}, native_tools={meta.supports_native_tool_calls}, "
        f"mock={meta.is_mock})"
    )

    text_ok = _run_generate(backend)
    tool_calls = _run_tool_emulation(backend_name, backend)
    successes, latencies = _run_structured(backend, rounds)
    success_rate = successes / rounds if rounds else 0.0
    if latencies:
        print(
            f"structured latency_ms   : mean={statistics.mean(latencies):.0f} "
            f"min={min(latencies):.0f} max={max(latencies):.0f}"
        )
    print(f"structured success rate: {successes}/{rounds} = {success_rate:.0%}")

    print(
        f"RESULT: {'PASS' if text_ok else 'FAIL'} "
        f"(generate={'ok' if text_ok else 'FAIL'}, "
        f"structured={successes}/{rounds}, tool_calls={tool_calls})"
    )
    return 0 if text_ok else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--backend",
        choices=["mock", "llamacpp", "transformers"],
        default=os.environ.get("FORENSICS_INFERENCE_BACKEND", "llamacpp"),
    )
    parser.add_argument("--rounds", type=int, default=3, help="structured validation rounds")
    parser.add_argument("--base-url", default=None, help="llamacpp base URL override")
    args = parser.parse_args()
    return validate(args.backend, args.rounds, args.base_url)


if __name__ == "__main__":
    raise SystemExit(main())

