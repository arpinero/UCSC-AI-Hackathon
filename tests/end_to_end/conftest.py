"""Injectable engine harness for end-to-end tests (see harness.py).

Also re-exports the `backend` / `registry` fixtures so the end-to-end
suite shares the exact same swap point as the integration suite.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Make this worktree's src/ take precedence over the shared venv's editable
# install (which points at the main repo's src/, without forensics/api).
_SRC = str(Path(__file__).resolve().parents[2] / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from tests.integration.conftest import backend, registry  # noqa: E402, F401
