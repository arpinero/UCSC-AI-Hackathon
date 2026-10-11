"""Backend factory: `create_backend("mock" | "llamacpp" | "transformers")`.

Honors the ``FORENSICS_INFERENCE_BACKEND`` environment variable when no name
is given (default: ``mock``).
"""

from __future__ import annotations

import os

from forensics.inference.base import InferenceBackend, InferenceBackendError
from forensics.inference.mock import MockInferenceBackend

VALID_BACKENDS = ("mock", "llamacpp", "transformers")


def create_backend(
    name: str | None = None, **kwargs: object
) -> InferenceBackend:
    """Instantiate an inference backend by name.

    ``kwargs`` are passed straight to the backend constructor (e.g.
    ``timeout_s``, ``transport`` for llamacpp, ``device`` for transformers).
    Heavy deps (torch/transformers) are imported lazily so that the default
    mock/llamacpp paths work without them.
    """

    resolved = (name or os.environ.get("FORENSICS_INFERENCE_BACKEND") or "mock").strip().lower()
    if resolved == "mock":
        return MockInferenceBackend(**kwargs)  # type: ignore[arg-type]
    if resolved == "llamacpp":
        from forensics.inference.llamacpp import LlamaCppBackend

        return LlamaCppBackend(**kwargs)  # type: ignore[arg-type]
    if resolved == "transformers":
        from forensics.inference.transformers_backend import TransformersBackend

        return TransformersBackend(**kwargs)  # type: ignore[arg-type]
    raise InferenceBackendError(
        f"unknown inference backend '{resolved}'; expected one of {VALID_BACKENDS}"
    )
