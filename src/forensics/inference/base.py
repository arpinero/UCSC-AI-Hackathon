"""Abstract inference backend interface.

Every backend (Transformers, llama.cpp OpenAI-compatible, mock, ...) must
implement this interface. Stage B owners: model-engineer (feat/inference).
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from contracts.inference import (
    InferenceRequest,
    InferenceResult,
    ModelMetadata,
    StructuredGenerationRequest,
)


class InferenceBackendError(RuntimeError):
    """Raised when a backend fails to serve a request."""


class InferenceTimeoutError(InferenceBackendError):
    """Raised when a request exceeds the configured timeout."""

    def __init__(self, timeout_s: float) -> None:
        super().__init__(f"inference request timed out after {timeout_s}s")
        self.timeout_s = timeout_s


class InferenceBackend(ABC):
    """Abstract model backend.

    Implementations must never let model-specific formats (chat templates,
    tool-call syntax) leak into investigation logic. Convert everything to
    the typed contracts in `contracts.inference`.
    """

    #: Timeout in seconds applied to every request.
    timeout_s: float = 60.0

    @abstractmethod
    def generate(self, request: InferenceRequest) -> InferenceResult:
        """Run a free-form generation."""

    @abstractmethod
    def generate_structured(
        self, request: StructuredGenerationRequest, response_model: type
    ) -> object:
        """Generate output validated against `response_model` (a Pydantic model).

        Implementations should attempt native structured output where
        available; otherwise parse/repair JSON and validate. Raises
        InferenceBackendError if the output cannot be validated.
        """

    @abstractmethod
    def health_check(self) -> bool:
        """Return True if the backend is ready to serve requests."""

    @abstractmethod
    def get_model_metadata(self) -> ModelMetadata:
        """Return identity and capabilities of the loaded model."""

    def supports_tools(self) -> bool:
        return self.get_model_metadata().supports_native_tool_calls
