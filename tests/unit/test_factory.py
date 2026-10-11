"""Unit tests for the inference backend factory."""

from __future__ import annotations

import pytest

from forensics.inference.base import InferenceBackend, InferenceBackendError
from forensics.inference.factory import create_backend
from forensics.inference.llamacpp import LlamaCppBackend
from forensics.inference.mock import MockInferenceBackend


def test_default_is_mock():
    assert isinstance(create_backend(), MockInferenceBackend)
    assert isinstance(create_backend("mock"), MockInferenceBackend)


def test_llamacpp_backend_created():
    backend = create_backend("llamacpp", timeout_s=7.5)
    assert isinstance(backend, LlamaCppBackend)
    assert backend.timeout_s == 7.5


def test_env_variable_selects_backend(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("FORENSICS_INFERENCE_BACKEND", "llamacpp")
    assert isinstance(create_backend(), LlamaCppBackend)


def test_env_variable_case_insensitive(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("FORENSICS_INFERENCE_BACKEND", "Mock")
    assert isinstance(create_backend(), MockInferenceBackend)


def test_transformers_backend_lazy_no_weights_loaded():
    # lazy=True defers the heavy import + weight load: constructing the object
    # must not touch torch or the HF cache.
    backend = create_backend("transformers", lazy=True, timeout_s=5.0)
    assert isinstance(backend, InferenceBackend)
    assert backend.model_id == "alirezaaminzadeh/soc-analyst-tool-use"


def test_unknown_backend_raises():
    with pytest.raises(InferenceBackendError, match="unknown inference backend"):
        create_backend("vllm")
