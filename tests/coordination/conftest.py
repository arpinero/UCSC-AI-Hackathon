"""Fixtures: every test uses its own temporary database, never the shared one."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from coordination.database import init_database
from coordination.service import CoordinationService

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "coord" / "coordination.db"
    init_database(path)
    return path


@pytest.fixture
def svc(db_path: Path) -> CoordinationService:
    return CoordinationService(db_path)


def run_cli(
    *args: str, db: Path | None, cwd: Path = REPO_ROOT, extra_env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    """Run `python -m coordination.cli` in a fresh process (as an agent would)."""
    env = {k: v for k, v in os.environ.items() if k != "FORENSICS_COORD_DB"}
    if db is not None:
        env["FORENSICS_COORD_DB"] = str(db)
    env.update(extra_env or {})
    return subprocess.run(
        [sys.executable, "-m", "coordination.cli", "--json", *args],
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
