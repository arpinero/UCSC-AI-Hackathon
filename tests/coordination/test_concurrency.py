"""Concurrency: many writer threads/processes; WAL + busy_timeout + retries."""

from __future__ import annotations

import sqlite3
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from coordination.database import init_database
from coordination.service import CoordinationService

SENDERS = [
    "model-engineer",
    "tools-engineer",
    "agntcy-engineer",
    "reasoning-engineer",
    "evaluation-engineer",
    "integration-qa",
]


def _thread_worker(db: str, agent: str, count: int) -> int:
    """Runs inside worker processes (stdlib only; no pydantic import needed)."""
    service = CoordinationService(Path(db))
    for i in range(count):
        service.send(
            sender=agent,
            recipient="coordinator",
            message_type="PROGRESS",
            subject=f"progress {i}",
            body=f"concurrent write {i}",
        )
    return count


def test_concurrent_writer_processes(db_path: Path, tmp_path: Path):
    """12 processes x 10 writes = 120 messages, all must land (WAL + retries)."""
    workers = SENDERS + SENDERS
    with ProcessPoolExecutor(max_workers=len(workers)) as pool:
        futures = [pool.submit(_thread_worker, str(db_path), agent, 10) for agent in workers]
        assert sum(f.result() for f in futures) == len(workers) * 10

    service = CoordinationService(db_path)
    received = service.history(recipient="coordinator", limit=500)
    assert len(received) == 120
    # no duplicate message ids
    assert len({m.message_id for m in received}) == 120


def test_concurrent_reader_and_writer_threads(db_path: Path):
    import threading

    service = CoordinationService(db_path)
    service.send(sender="tools-engineer", recipient="integration-qa",
                 message_type="PROGRESS", subject="seed", body="b")
    errors: list[Exception] = []

    def write(i: int) -> None:
        try:
            CoordinationService(db_path).send(
                sender="tools-engineer", recipient="integration-qa",
                message_type="PROGRESS", subject=f"w{i}", body="b")
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    def read_loop() -> None:
        try:
            for _ in range(20):
                CoordinationService(db_path).inbox("integration-qa")
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=write, args=(i,)) for i in range(8)]
    threads += [threading.Thread(target=read_loop) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert errors == []
    assert len(CoordinationService(db_path).history()) == 9


def test_wal_mode_and_integrity(db_path: Path):
    conn = sqlite3.connect(str(db_path))
    try:
        assert str(conn.execute("PRAGMA journal_mode").fetchone()[0]).lower() == "wal"
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    finally:
        conn.close()


def test_network_filesystem_detection(tmp_path: Path):
    info = init_database(tmp_path / "coord" / "coordination.db")
    assert info["journal_mode"] == "wal"
    # tmp_path is on the local NVMe root filesystem
    assert info["filesystem_type"] not in (None, "nfs", "nfs4", "cifs", "9p")
    assert info["network_filesystem"] is False
