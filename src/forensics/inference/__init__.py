"""Inference subpackage: abstract backends, model adapters, chat templates.

Model-specific tool-call parsing and chat templates live here, strictly
separated from investigation logic (which lives in forensics.reasoning).
"""

from forensics.inference.base import (
    InferenceBackend,
    InferenceBackendError,
    InferenceTimeoutError,
)
from forensics.inference.factory import create_backend
from forensics.inference.mock import MockInferenceBackend, parse_json_candidate

__all__ = [
    "InferenceBackend",
    "InferenceBackendError",
    "InferenceTimeoutError",
    "MockInferenceBackend",
    "create_backend",
    "parse_json_candidate",
]

