"""Transformers backend for the local SOC fine-tune (Priority 2).

Loads `alirezaaminzadeh/soc-analyst-tool-use` (Qwen2.5-1.5B-Instruct base)
with HF transformers. Model-specific concerns stay in this module:

- Qwen2.5 chat template rendering (tools injected per Qwen2.5 convention),
- ``<<{...}>>`` tool-call block parsing (see `qwen_tool_parser`),
- structured output via JSON prompting + Pydantic validation with one retry.

Notes on this host (aarch64 NVIDIA GB10):
- PyPI torch wheels for linux/aarch64 ship CUDA 13 support; the backend
  prefers CUDA when available. On THIS machine the GPU is already fully
  occupied by the llama.cpp server, so placing the SOC model on CUDA fails
  with an out-of-memory error — the backend then falls back to CPU
  automatically (documented behavior, `self._device_resolved` records the
  device actually used).
- The weights cache lives OUTSIDE the git tree via ``HF_HOME``
  (default set by the factory / validation script to
  ``/home/asus/forensics-agent-coordination/hf-cache``).
"""

from __future__ import annotations

import os
import time
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ValidationError

from contracts.inference import (
    FinishReason,
    InferenceRequest,
    InferenceResult,
    ModelMetadata,
    StructuredGenerationRequest,
    ToolSpec,
)
from forensics.inference.base import (
    InferenceBackend,
    InferenceBackendError,
    InferenceTimeoutError,
)
from forensics.inference.mock import parse_json_candidate
from forensics.inference.qwen_tool_parser import parse_qwen_tool_calls, strip_tool_blocks

if TYPE_CHECKING:  # pragma: no cover - heavy imports only for type checkers
    from transformers import PreTrainedModel, PreTrainedTokenizerBase

DEFAULT_SOC_MODEL_ID = "alirezaaminzadeh/soc-analyst-tool-use"

_MISSING_DEPS = (
    "torch/transformers are not installed. Install the approved optional extra: "
    "pip install -e '.[inference]'"
)


def _tools_as_qwen_schema(tools: list[ToolSpec]) -> list[dict[str, Any]]:
    """Map contract ToolSpecs to the Qwen2.5 chat-template tool schema."""

    return [
        {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters,
            },
        }
        for tool in tools
    ]


class TransformersBackend(InferenceBackend):
    """Local transformers backend wrapping the SOC tool-use fine-tune.

    Args:
        model_id: HF repo id (default: the approved SOC fine-tune).
        timeout_s: wall-clock budget per generation call (enforced after the
            fact — HF ``generate`` cannot be interrupted cheaply; exceeding it
            raises ``InferenceTimeoutError``).
        device: ``"cuda"``, ``"cpu"`` or ``None`` (auto: cuda when available).
        lazy: when True, defer weight loading until the first call.
    """

    def __init__(
        self,
        *,
        model_id: str | None = None,
        timeout_s: float = 120.0,
        device: str | None = None,
        lazy: bool = False,
    ) -> None:
        if not lazy:
            self._import_deps()  # fail fast with a clear message
        self.model_id = model_id or os.environ.get("FORENSICS_SOC_MODEL_ID") or (
            DEFAULT_SOC_MODEL_ID
        )
        self.timeout_s = timeout_s
        self.device = device
        self._model: PreTrainedModel | None = None
        self._tokenizer: PreTrainedTokenizerBase | None = None
        self._device_resolved: str | None = None
        #: Latency of the last generate call, in milliseconds.
        self.last_latency_ms: float | None = None
        self.latencies_ms: list[float] = []
        if not lazy:
            self._load()

    # ------------------------------------------------------------------ setup

    @staticmethod
    def _import_deps() -> None:
        try:
            import torch  # noqa: F401
            import transformers  # noqa: F401
        except ImportError as exc:
            raise InferenceBackendError(_MISSING_DEPS) from exc

    def _load(self) -> None:
        """Load tokenizer + weights (downloads on first use, then cached)."""
        self._import_deps()
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        if self._model is not None:
            return
        try:
            tokenizer = AutoTokenizer.from_pretrained(self.model_id)
            # transformers>=5 renamed `torch_dtype` to `dtype`; "auto" keeps
            # the checkpoint's native BF16.
            model = AutoModelForCausalLM.from_pretrained(self.model_id, dtype="auto")
        except Exception as exc:  # network/OOM/corrupt-cache all become backend errors
            raise InferenceBackendError(f"failed to load '{self.model_id}': {exc}") from exc
        if self.device is not None:
            resolved = self.device
        elif torch.cuda.is_available():
            resolved = "cuda"
        else:
            resolved = "cpu"
        try:
            model = model.to(resolved)  # type: ignore[arg-type]
        except Exception as exc:
            if resolved == "cuda" and self.device is None:
                # Expected on this GB10: the GPU is already fully occupied by
                # the llama.cpp server. CPU is the documented fallback.
                resolved = "cpu"
                try:
                    model = model.to("cpu")  # type: ignore[arg-type]
                except Exception as cpu_exc:
                    raise InferenceBackendError(
                        f"failed to place model on 'cpu': {cpu_exc}"
                    ) from cpu_exc
            else:
                raise InferenceBackendError(
                    f"failed to place model on '{resolved}': {exc}"
                ) from exc
        model.eval()
        self._model = model
        self._tokenizer = tokenizer
        self._device_resolved = resolved

    def _ensure_loaded(self) -> tuple[PreTrainedModel, PreTrainedTokenizerBase, str]:
        if self._model is None or self._tokenizer is None or self._device_resolved is None:
            self._load()
        assert self._model is not None and self._tokenizer is not None
        return self._model, self._tokenizer, self._device_resolved or "cpu"

    # ------------------------------------------------------------ generation

    def _run_generation(
        self,
        messages: list[dict[str, str]],
        tools: list[ToolSpec] | None = None,
        max_new_tokens: int = 512,
        temperature: float = 0.2,
    ) -> str:
        """Render the Qwen2.5 chat template and generate, timing the call."""
        import torch

        model, tokenizer, device = self._ensure_loaded()
        if tools:
            try:
                prompt = tokenizer.apply_chat_template(
                    messages,
                    tools=_tools_as_qwen_schema(tools),  # type: ignore[arg-type]
                    add_generation_prompt=True,
                    tokenize=False,
                )
            except Exception:
                # Template without tool support: inject tool schemas as text.
                tool_text = "\n".join(
                    f"- {t.name}: {t.description} Parameters: {t.parameters}" for t in tools
                )
                messages = [
                    {
                        "role": "system",
                        "content": (
                            "You may call these tools by replying with "
                            f"<<{{\"name\": ..., \"arguments\": {{...}}}}>> blocks:\n{tool_text}"
                        ),
                    }
                ] + messages
                prompt = tokenizer.apply_chat_template(
                    messages, add_generation_prompt=True, tokenize=False
                )
        else:
            prompt = tokenizer.apply_chat_template(
                messages, add_generation_prompt=True, tokenize=False
            )
        inputs = tokenizer(prompt, return_tensors="pt").to(device)
        do_sample = temperature > 0.0
        pad_id = getattr(tokenizer, "pad_token_id", None) or getattr(
            tokenizer, "eos_token_id", None
        )
        start = time.perf_counter()
        with torch.inference_mode():
            output_ids = model.generate(  # type: ignore[operator]
                **inputs,  # type: ignore[arg-type]
                max_new_tokens=max_new_tokens,
                do_sample=do_sample,
                temperature=max(temperature, 1e-4) if do_sample else None,
                pad_token_id=pad_id,
            )
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        self.last_latency_ms = elapsed_ms
        self.latencies_ms.append(elapsed_ms)
        if elapsed_ms / 1000.0 > self.timeout_s:
            raise InferenceTimeoutError(self.timeout_s)
        new_tokens = output_ids[0][inputs["input_ids"].shape[1] :]
        decoded = tokenizer.decode(new_tokens, skip_special_tokens=True)
        return str(decoded)

    def generate(self, request: InferenceRequest) -> InferenceResult:
        messages = [{"role": m.role, "content": m.content} for m in request.messages]
        text = self._run_generation(
            messages,
            tools=request.tools or None,
            max_new_tokens=request.max_tokens,
            temperature=request.temperature,
        )
        tool_calls = parse_qwen_tool_calls(text)
        finish_reason = FinishReason.TOOL_CALL if tool_calls else FinishReason.STOP
        return InferenceResult(
            text=strip_tool_blocks(text) if tool_calls else text,
            finish_reason=finish_reason,
            tool_calls=tool_calls,
            backend_name="transformers",
        )

    def generate_structured(
        self, request: StructuredGenerationRequest, response_model: type
    ) -> Any:
        if not (isinstance(response_model, type) and issubclass(response_model, BaseModel)):
            raise InferenceBackendError("response_model must be a Pydantic model class")
        import json as _json

        schema = response_model.model_json_schema()
        messages: list[dict[str, str]] = [
            {
                "role": "system",
                "content": (
                    "Reply with ONLY a single JSON object conforming to this JSON "
                    f"Schema (no prose, no code fences):\n{_json.dumps(schema, ensure_ascii=False)}"
                ),
            }
        ] + [{"role": m.role, "content": m.content} for m in request.messages]

        last_error: Exception | None = None
        for _attempt in range(2):  # initial attempt + one retry with the error
            text = self._run_generation(
                messages,
                max_new_tokens=request.max_tokens,
                temperature=request.temperature,
            )
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
                            "Reply again with ONLY a single valid JSON object."
                        ),
                    },
                ]
        raise InferenceBackendError(
            f"structured output failed validation after retry: {last_error}"
        ) from last_error

    # -------------------------------------------------------------- lifecycle

    def health_check(self) -> bool:
        """Real check: weights loaded AND a 1-token generation succeeds."""
        try:
            self._run_generation(
                [{"role": "user", "content": "hi"}], max_new_tokens=1, temperature=0.0
            )
        except (InferenceBackendError, InferenceTimeoutError):
            return False
        return True

    def get_model_metadata(self) -> ModelMetadata:
        model, _tokenizer, _device = self._ensure_loaded()
        config = model.config
        context_window = int(getattr(config, "max_position_embeddings", 0) or 0)
        if context_window <= 0:
            context_window = int(getattr(config, "n_ctx", 0) or 0) or 32768
        return ModelMetadata(
            model_id=self.model_id,
            backend_name="transformers",
            context_window=context_window,
            supports_native_tool_calls=True,  # Qwen2.5 chat template renders tools
            supports_structured_output=True,  # emulated: JSON prompting + validation
            is_mock=False,
        )



