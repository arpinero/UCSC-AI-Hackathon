"""Shared fixtures for forensics.messaging tests."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    # The worktree's src must win over the editable install of the main repo.
    sys.path.insert(0, str(SRC))

import pytest  # noqa: E402

from forensics.messaging.envelopes import build_message  # noqa: E402


@pytest.fixture
def make_message():
    """Factory producing valid synthetic council messages (no real data)."""

    def _make(**overrides):
        defaults: dict = {
            "incident_id": "INC-TEST-1",
            "message_type": "FINDING",
            "sender": "forensics",
            "recipients": ["coordinator"],
            "payload": {"note": "synthetic test payload"},
        }
        defaults.update(overrides)
        return build_message(**defaults)

    return _make
