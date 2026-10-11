"""Injectable component fixtures for integration tests.

These fixtures are THE swap point for real implementations: after the
coordinator merges feat/inference and feat/forensic-tools, repoint these
fixtures at the real backend/registry and the whole integration suite
re-runs unchanged.
"""

from __future__ import annotations

import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

# The shared venv's editable install maps `forensics` to the MAIN repo's
# src/ tree, which does not contain this worktree's src/forensics/api.
# Insert this worktree's src/ BEFORE importing forensics so the package
# (and its submodules) resolve to worktree-local code.
_SRC = str(Path(__file__).resolve().parents[2] / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from forensics.inference.base import InferenceBackend  # noqa: E402
from forensics.inference.mock import MockInferenceBackend  # noqa: E402
from forensics.tools.base import ToolRegistry  # noqa: E402
from forensics.tools.mock import build_mock_registry  # noqa: E402


@pytest.fixture
def backend() -> Iterator[InferenceBackend]:
    """Stage A mock inference backend (deterministic, no GPU)."""
    yield MockInferenceBackend()


@pytest.fixture
def registry() -> Iterator[ToolRegistry]:
    """Stage A mock tool registry with all seven forensic tools."""
    yield build_mock_registry()
