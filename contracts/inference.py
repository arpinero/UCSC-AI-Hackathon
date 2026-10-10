"""Inference contracts: typed requests/responses for model backends."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from contracts.common import FrozenModelConfig, NonEmptyString


class ChatMessage(BaseModel):
    """One message in a chat conversation."""

    model_config = FrozenModelConfig.model_config

    role: NonEmptyString = Field(description="system | user | assistant | tool")
    content: str = ""
    tool_call_id: NonEmptyString | None = None
    name: NonEmptyString | None = None


class ToolSpec(BaseModel):
    """Declarative description of a tool the model may call."""

    model_config = FrozenModelConfig.model_config

    name: NonEmptyString
    description: NonEmptyString
    parameters: dict[str, Any] = Field(description="JSON Schema of the arguments")


class ToolCallRequest(BaseModel):
    """A tool call emitted by the model."""

    model_config = FrozenModelConfig.model_config

    tool_name: NonEmptyString
    arguments: dict[str, Any] = Field(default_factory=dict)
    call_id: NonEmptyString | None = None


class FinishReason(str, Enum):
    STOP = "STOP"
    MAX_TOKENS = "MAX_TOKENS"
    TOOL_CALL = "TOOL_CALL"
    ERROR = "ERROR"


class InferenceRequest(BaseModel):
    """Free-form generation request."""

    model_config = FrozenModelConfig.model_config

    messages: list[ChatMessage] = Field(min_length=1)
    max_tokens: int = Field(default=512, gt=0)
    temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    tools: list[ToolSpec] = Field(default_factory=list)
    stop: list[str] = Field(default_factory=list)


class InferenceResult(BaseModel):
    """Free-form generation result."""

    model_config = FrozenModelConfig.model_config

    text: str = ""
    finish_reason: FinishReason = FinishReason.STOP
    tool_calls: list[ToolCallRequest] = Field(default_factory=list)
    prompt_tokens: int = Field(default=0, ge=0)
    completion_tokens: int = Field(default=0, ge=0)
    backend_name: NonEmptyString


class StructuredGenerationRequest(BaseModel):
    """Generation request whose answer must validate against a Pydantic model.

    The expected response model is referenced by name and resolved by the
    backend at runtime (keeps the wire format serializable).
    """

    model_config = FrozenModelConfig.model_config

    messages: list[ChatMessage] = Field(min_length=1)
    response_model: NonEmptyString = Field(
        description="Contract class name, e.g. InvestigationFindings"
    )
    max_tokens: int = Field(default=1024, gt=0)
    temperature: float = Field(default=0.1, ge=0.0, le=2.0)


class ModelMetadata(BaseModel):
    """Capabilities and identity of a loaded inference backend."""

    model_config = FrozenModelConfig.model_config

    model_id: NonEmptyString
    backend_name: NonEmptyString
    context_window: int = Field(gt=0)
    supports_native_tool_calls: bool = Field(
        description="False for e.g. Foundation-Sec-8B via llama.cpp"
    )
    supports_structured_output: bool
    is_mock: bool = False
