"""SQLite storage for the coding-agent coordination bus (stdlib only).

The database MUST live outside every Git worktree. Location comes from the
FORENSICS_COORD_DB environment variable (absolute path) or an explicit path.
"""

from __future__ import annotations

import os
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import quote

from coordination.models import (
    AGENT_ROLES,
    SCHEMA_VERSION,
    DatabaseUnavailable,
    utc_now_iso,
)

ENV_VAR = "FORENSICS_COORD_DB"
BUSY_TIMEOUT_MS = 15_000
NETWORK_FS = {"nfs", "nfs4", "cifs", "smb3", "smbfs", "fuse.sshfs", "9p", "afs", "ceph"}

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS agents (
    agent_id TEXT PRIMARY KEY,
    role TEXT NOT NULL,
    registered_at TEXT NOT NULL,
    last_heartbeat_at TEXT,
    last_heartbeat_note TEXT
);
CREATE TABLE IF NOT EXISTS messages (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id TEXT NOT NULL UNIQUE,
    schema_version TEXT NOT NULL,
    sender TEXT NOT NULL REFERENCES agents(agent_id),
    recipient TEXT NOT NULL REFERENCES agents(agent_id),
    message_type TEXT NOT NULL,
    priority TEXT NOT NULL,
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    created_at TEXT NOT NULL,
    correlation_id TEXT NOT NULL,
    related_branch TEXT,
    related_commit TEXT,
    status TEXT NOT NULL,
    read_at TEXT,
    acknowledged_at TEXT,
    resolved_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_msg_recipient ON messages(recipient, status);
CREATE INDEX IF NOT EXISTS idx_msg_correlation ON messages(correlation_id);
CREATE INDEX IF NOT EXISTS idx_msg_sender ON messages(sender);
"""


def resolve_db_path(explicit: str | None = None) -> Path:
    """Return the absolute database path from `explicit` or FORENSICS_COORD_DB."""
    raw = explicit or os.environ.get(ENV_VAR)
    if not raw:
        raise DatabaseUnavailable(
            f"no database configured: set {ENV_VAR} to an absolute path or pass --db"
        )
    path = Path(raw).expanduser()
    if not path.is_absolute():
        raise DatabaseUnavailable(f"database path must be absolute, got '{raw}'")
    return path


def filesystem_type(path: Path) -> str | None:
    """Best-effort filesystem type of `path` from /proc/mounts (Linux)."""
    try:
        probe = path
        while not probe.exists() and probe != probe.parent:
            probe = probe.parent
        target = str(probe.resolve())
        best: tuple[int, str] | None = None
        with open("/proc/mounts", encoding="utf-8") as handle:
            for line in handle:
                parts = line.split()
                if len(parts) < 3:
                    continue
                mount = parts[1].replace("\\040", " ")
                prefix = mount.rstrip("/") + "/"
                if (target == mount or target.startswith(prefix)) and (
                    best is None or len(mount) > best[0]
                ):
                    best = (len(mount), parts[2])
        return best[1] if best else None
    except OSError:
        return None


def _configure(conn: sqlite3.Connection) -> None:
    conn.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA synchronous = NORMAL")


def connect(path: Path, *, create: bool = False) -> sqlite3.Connection:
    """Open a connection. Without `create`, a missing database is an error."""
    timeout = BUSY_TIMEOUT_MS / 1000
    try:
        if create:
            path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(str(path), timeout=timeout, isolation_level=None)
        else:
            if not path.is_file():
                raise DatabaseUnavailable(
                    f"database not found at {path}; run `python -m coordination.cli init`"
                )
            uri = f"file:{quote(str(path))}?mode=rw"
            conn = sqlite3.connect(uri, uri=True, timeout=timeout, isolation_level=None)
        conn.row_factory = sqlite3.Row
        _configure(conn)
        conn.execute("SELECT count(*) FROM sqlite_master").fetchone()
        return conn
    except DatabaseUnavailable:
        raise
    except (sqlite3.Error, OSError) as exc:
        raise DatabaseUnavailable(f"cannot open database {path}: {exc}") from exc


@contextmanager
def write_transaction(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    """BEGIN IMMEDIATE ... COMMIT/ROLLBACK; serializes concurrent writers."""
    try:
        conn.execute("BEGIN IMMEDIATE")
    except sqlite3.OperationalError as exc:
        raise DatabaseUnavailable(f"database is locked or unavailable: {exc}") from exc
    try:
        yield conn
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    else:
        conn.execute("COMMIT")


def init_database(path: Path) -> dict[str, object]:
    """Create/upgrade the schema, enable WAL, and register the canonical agents."""
    fs_type = filesystem_type(path)
    conn = connect(path, create=True)
    try:
        mode = str(conn.execute("PRAGMA journal_mode = WAL").fetchone()[0]).lower()
        conn.executescript(SCHEMA)
        now = utc_now_iso()
        with write_transaction(conn):
            conn.execute(
                "INSERT OR IGNORE INTO meta(key, value) VALUES ('schema_version', ?)",
                (SCHEMA_VERSION,),
            )
            conn.execute("INSERT OR IGNORE INTO meta(key, value) VALUES ('created_at', ?)", (now,))
            for agent_id, role in AGENT_ROLES.items():
                conn.execute(
                    "INSERT OR IGNORE INTO agents(agent_id, role, registered_at) VALUES (?, ?, ?)",
                    (agent_id, role, now),
                )
        return {
            "path": str(path),
            "journal_mode": mode,
            "filesystem_type": fs_type,
            "network_filesystem": (fs_type in NETWORK_FS) if fs_type else None,
            "schema_version": SCHEMA_VERSION,
            "agents_registered": len(AGENT_ROLES),
        }
    except sqlite3.Error as exc:
        raise DatabaseUnavailable(f"failed to initialise database {path}: {exc}") from exc
    finally:
        conn.close()
