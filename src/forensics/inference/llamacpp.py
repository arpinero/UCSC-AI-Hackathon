"""llama.cpp OpenAI-compatible backend (Foundation-Sec-8B via :8000).

Talks to the llama.cpp `llama-server` OpenAI-compatible API using only the
standard library (`urllib.request`). The served model
(`fdtn-ai/Foundation-Sec-8B-Instruct`) does NOT support native tool calls in
its chat template: tool calls are emulated via prompt-engineered JSON and
never advertised as native (`supports_native_tool_calls=False`).
"""

from __future__ import annotations

import json
import os
import time
from collections.abc import Callable
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from pydantic import BaseModel, ValidationError

from contracts.inference import (
    ChatMessage,
    FinishReason,
    InferenceRequest,
    InferenceResult,
    ModelMetadata,
    StructuredGenerationRequest,
    ToolCallRequest,
    ToolSpec,
)
from forensics.inference.base import (
    InferenceBackend,
    InferenceBackendError,
    InferenceTimeoutError,
)
from forensics.inference.mock import parse_json_candidate

DEFAULT_BASE_URL = "http://127.0.0.1:8000/v1"
DEFAULT_MODEL_ID = "fdtn-ai/Foundation-Sec-8B-Instruct"
DEFAULT_HEALTH_TIMEOUT_S = 5.0

#: Injectable transport: (method, url, payload, timeout_s) -> (status_code, body).
Transport = Callable[[str, str, "dict[str, Any] | None", float], "tuple[int, dict[str, Any]]"]

def _urllib_transport(
    method: str, url: str, payload: dict[str, Any] | None, timeout_s: float
) -> tuple[int, dict[str, Any]]:
    """Default stdlib HTTP transport (urllib.request only)."""

    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = Request(url, data=data, method=method)  # noqa: S310 - fixed local endpoint
    request.add_header("Content-Type", "application/json")
    request.add_header("Accept", "application/json")
    try:
        with urlopen(request, timeout=timeout_s) as response:  # noqa: S310
            status = response.status
            raw = response.read()
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise InferenceBackendError(
            f"llama.cpp server returned HTTP {exc.code} for {method} {url}: {detail}"
        ) from exc
    except TimeoutError as exc:
        raise InferenceTimeoutError(timeout_s) from exc
    except URLError as exc:
        if isinstance(exc.reason, TimeoutError):
            raise InferenceTimeoutError(timeout_s) from exc
        raise InferenceBackendError(
            f"cannot reach llama.cpp server at {url}: {exc.reason}"
        ) from exc
    try:
        body = json.loads(raw.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise InferenceBackendError(f"non-JSON response from llama.cpp server: {exc}") from exc
    if not isinstance(body, dict):
        raise InferenceBackendError("llama.cpp server returned a non-object JSON body")
    if status >= 400:
        raise InferenceBackendError(f"llama.cpp server returned HTTP {status}: {body}")
    return status, body

def parse_emulated_tool_calls(text: str) -> list[ToolCallRequest]:
    """Parse prompt-engineered tool calls out of free-form model text.

    Tolerates the shapes a JSON-prompted 8B model actually produces:
      - ``{"tool_calls": [{"name": ..., "arguments": {...}}]}``
      - a bare list ``[{"name": ..., "arguments": {...}}]``
      - a single object ``{"name": ..., "arguments": {...}}``
    Returns ``[]`` when the text contains no recognizable tool call.
    """

    try:
        parsed: Any = parse_json_candidate(text)
    except InferenceBackendError:
        return []
    calls: list[dict[str, Any]]
    if isinstance(parsed, dict):
        inner = parsed.get("tool_calls")
        if isinstance(inner, list):
            calls = [c for c in inner if isinstance(c, dict)]
        else:
            calls = [parsed]
    elif isinstance(parsed, list):
        calls = [c for c in parsed if isinstance(c, dict)]
    else:
        return []
    tool_calls: list[ToolCallRequest] = []
    for call in calls:
        name = call.get("name") or call.get("tool_name")
        if not isinstance(name, str) or not name.strip():
            continue
        arguments = call.get("arguments")
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
            except json.JSONDecodeError:
                arguments = {}
        if not isinstance(arguments, dict):
            arguments = {}
        call_id = call.get("call_id")
        try:
            tool_calls.append(
                ToolCallRequest(
                    tool_name=name.strip(),
                    arguments=arguments,
                    call_id=call_id if isinstance(call_id, str) else None,
                )
            )
        except ValidationError:
            continue
    return tool_calls


def _tools_emulation_instruction(tools: list[ToolSpec]) -> str:
    """System instruction emulating tool calls for a non-tool-native model."""

    lines = ["You have access to the following tools:"]
    for tool in tools:
        lines.append(
            f"- {tool.name}: {tool.description} "
            f"Parameters (JSON Schema): {json.dumps(tool.parameters, ensure_ascii=False)}"
        )
    lines += [
        "",
        "When you decide to use a tool, reply with ONLY a single JSON object in this "
        "exact shape:",
        '{"tool_calls": [{"name": "<tool name>", "arguments": {<argument values>}}]}',
        "Do not wrap it in prose or code fences. If you need no tool, answer normally.",
    ]
    return "\n".join(lines)


def _structured_instruction(schema: dict[str, Any], response_model_name: str) -> str:
    return (
        "You are a precise assistant producing machine-readable output for a "
        "forensics system. You must reply with ONLY a single JSON object that "
        f"conforms to the JSON Schema of `{response_model_name}` below. "
        "No prose, no markdown code fences, no trailing commentary.\n\n"
        f"JSON Schema:\n{json.dumps(schema, ensure_ascii=False, indent=2)}"
    )

class LlamaCppBackend(InferenceBackend):
    """OpenAI-compatible backend served by the local llama.cpp server.

    Env overrides (read at construction time):
      - ``FORENSICS_LLAMACPP_BASE_URL`` (default ``http://127.0.0.1:8000/v1``)
      - ``FORENSICS_LLAMACPP_MODEL`` (default ``fdtn-ai/Foundation-Sec-8B-Instruct``)
    """

    def __init__(
        self,
        *,
        base_url: str | None = None,
        model_id: str | None = None,
        timeout_s: float = 60.0,
        transport: Transport | None = None,
    ) -> None:
        self.base_url = (
            base_url or os.environ.get("FORENSICS_LLAMACPP_BASE_URL") or DEFAULT_BASE_URL
        ).rstrip("/")
        self.model_id = model_id or os.environ.get("FORENSICS_LLAMACPP_MODEL") or DEFAULT_MODEL_ID
        self.timeout_s = timeout_s
        self._transport: Transport = transport or _urllib_transport
        #: Latency of the last HTTP call, in milliseconds.
        self.last_latency_ms: float | None = None
        #: Full latency history (ms) for every HTTP call made.
        self.latencies_ms: list[float] = []
        self._metadata_cache: ModelMetadata | None = None

    # ------------------------------------------------------------------ HTTP

    def _http(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None,
        timeout_s: float | None = None,
    ) -> dict[str, Any]:
        """One HTTP call with latency measurement and error normalization."""
        effective_timeout = self.timeout_s if timeout_s is None else timeout_s
        url = f"{self.base_url}{path}"
        start = time.perf_counter()
        _, body = self._transport(method, url, payload, effective_timeout)
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        self.last_latency_ms = elapsed_ms
        self.latencies_ms.append(elapsed_ms)
        return body

    # ------------------------------------------------------------- interface

    def generate(self, request: InferenceRequest) -> InferenceResult:
        messages = [self._to_wire(m) for m in request.messages]
        if request.tools:
            messages = [
                {"role": "system", "content": _tools_emulation_instruction(request.tools)}
            ] + messages
        payload: dict[str, Any] = {
            "model": self.model_id,
            "messages": messages,
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
        }
        if request.stop:
            payload["stop"] = request.stop
        body = self._http("POST", "/chat/completions", payload)
        return self._result_from_completion(body)

    def generate_structured(
        self, request: StructuredGenerationRequest, response_model: type
    ) -> Any:
        if not (isinstance(response_model, type) and issubclass(response_model, BaseModel)):
            raise InferenceBackendError("response_model must be a Pydantic model class")
        schema = response_model.model_json_schema()
        messages: list[dict[str, str]] = [
            {"role": "system", "content": _structured_instruction(schema, request.response_model)}
        ] + [self._to_wire(m) for m in request.messages]

        last_error: Exception | None = None
        for _attempt in range(2):  # first attempt + one retry with the error appended
            body = self._http(
                "POST",
                "/chat/completions",
                {
                    "model": self.model_id,
                    "messages": messages,
                    "max_tokens": request.max_tokens,
                    "temperature": request.temperature,
                },
            )
            text = self._extract_text(body)
            try:
                candidate = parse_json_candidate(text)
                return response_model.model_validate(candidate)
            except (InferenceBackendError, ValidationError) as exc:
                last_error = exc
                messages = messages + [
                    {"role": "assistant", "content": text},
                    {
                        "role": "user",
                        "content": (
                            f"Your previous reply was invalid: {str(exc)[:800]}\n"
                            "Reply again with ONLY a single JSON object conforming to "
                            f"the `{request.response_model}` JSON Schema. "
                            "No prose, no code fences."
                        ),
                    },
                ]
        raise InferenceBackendError(
            f"structured output failed validation after retry: {last_error}"
        ) from last_error

    def health_check(self) -> bool:
        """Cheap real call: list models with a short timeout."""
        try:
            body = self._http("GET", "/models", None, timeout_s=DEFAULT_HEALTH_TIMEOUT_S)
        except (InferenceBackendError, InferenceTimeoutError):
            return False
        model_ids = {m.get("id", "") for m in body.get("data", []) if isinstance(m, dict)}
        return self.model_id in model_ids

    def get_model_metadata(self) -> ModelMetadata:
        """Real metadata from the server (`/v1/models` exposes n_ctx_train)."""
        if self._metadata_cache is not None:
            return self._metadata_cache
        body = self._http("GET", "/models", None, timeout_s=DEFAULT_HEALTH_TIMEOUT_S)
        data = body.get("data", [])
        entry = next(
            (m for m in data if isinstance(m, dict) and m.get("id") == self.model_id), None
        )
        if entry is None:
            available = [m.get("id") for m in data if isinstance(m, dict)]
            raise InferenceBackendError(
                f"model '{self.model_id}' is not served by {self.base_url}; available: {available}"
            )
        meta = entry.get("meta", {}) or {}
        context_window = int(meta.get("n_ctx_train", 0))
        if context_window <= 0:
            # llama.cpp variants that omit `meta` still serve a usable default.
            context_window = 32768
        self._metadata_cache = ModelMetadata(
            model_id=self.model_id,
            backend_name="llamacpp",
            context_window=context_window,
            supports_native_tool_calls=False,  # verified: chat template has no tools
            supports_structured_output=True,  # emulated: JSON prompting + validation
            is_mock=False,
        )
        return self._metadata_cache

    # --------------------------------------------------------------- helpers

    @staticmethod
    def _to_wire(message: ChatMessage) -> dict[str, str]:
        wire: dict[str, str] = {"role": message.role, "content": message.content}
        if message.name:
            wire["name"] = message.name
        if message.tool_call_id:
            wire["tool_call_id"] = message.tool_call_id
        return wire

    def _extract_text(self, body: dict[str, Any]) -> str:
        try:
            return str(body["choices"][0]["message"]["content"] or "")
        except (KeyError, IndexError, TypeError) as exc:
            raise InferenceBackendError(
                f"unexpected chat/completions response shape: {str(body)[:300]}"
            ) from exc

    def _result_from_completion(self, body: dict[str, Any]) -> InferenceResult:
        text = self._extract_text(body)
        raw_reason = ""
        try:
            raw_reason = str(body["choices"][0].get("finish_reason") or "").lower()
        except (KeyError, IndexError, TypeError):
            pass
        usage = body.get("usage", {}) or {}
        # This server never emits native tool_calls; emulate from the reply text.
        tool_calls = parse_emulated_tool_calls(text)
        finish_reason = FinishReason.STOP
        if tool_calls:
            finish_reason = FinishReason.TOOL_CALL
        elif raw_reason == "length":
            finish_reason = FinishReason.MAX_TOKENS
        return InferenceResult(
            text=text,
            finish_reason=finish_reason,
            tool_calls=tool_calls,
            prompt_tokens=int(usage.get("prompt_tokens", 0)),
            completion_tokens=int(usage.get("completion_tokens", 0)),
            backend_name="llamacpp",
        )




