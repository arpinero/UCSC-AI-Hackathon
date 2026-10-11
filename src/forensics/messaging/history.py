"""Auditable, per-incident debate history.

The history is append-only, ordered, queryable (by correlation thread,
round, type, sender, recipient), and persisted as JSONL — one line per
council message — at a caller-provided path, defaulting to
``/home/asus/forensics-agent-coordination/debate-history/<incident_id>.jsonl``
so the shared coordination area keeps the full council debate.

Owner: agntcy-engineer (Stage B).
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

from contracts.messages import CouncilMessage, CouncilMessageType
from forensics.messaging.envelopes import InvalidEnvelopeError, validate_envelope

DEFAULT_DEBATE_HISTORY_DIR = Path("/home/asus/forensics-agent-coordination/debate-history")


def default_history_path(incident_id: str) -> Path:
    """Default JSONL persistence path for one incident's debate history."""
    safe_id = incident_id.replace("/", "_")
    return DEFAULT_DEBATE_HISTORY_DIR / f"{safe_id}.jsonl"


class DebateHistory:
    """Ordered, queryable, append-only debate history for one incident."""

    def __init__(self, incident_id: str, path: str | Path | None = None) -> None:
        self.incident_id = incident_id
        self.path = Path(path) if path is not None else default_history_path(incident_id)
        self._messages: list[CouncilMessage] = []
        self._lock = threading.Lock()

    def record(self, message: CouncilMessage | dict[str, Any] | str) -> CouncilMessage:
        """Validate and append one message, persisting it immediately."""
        validated = validate_envelope(message)
        if validated.incident_id != self.incident_id:
            raise InvalidEnvelopeError(
                f"message incident_id {validated.incident_id!r} does not match "
                f"history incident {self.incident_id!r}"
            )
        with self._lock:
            self._messages.append(validated)
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(validated.model_dump_json() + "\n")
        return validated

    def query(
        self,
        *,
        correlation_id: str | None = None,
        round: int | None = None,
        message_type: CouncilMessageType | str | None = None,
        sender: str | None = None,
        recipient: str | None = None,
    ) -> list[CouncilMessage]:
        """Return messages (in order) matching all provided filters."""
        with self._lock:
            messages = list(self._messages)

        expected_type: str | None = None
        if message_type is not None:
            expected_type = (
                message_type.value
                if isinstance(message_type, CouncilMessageType)
                else message_type
            )

        def keep(message: CouncilMessage) -> bool:
            if correlation_id is not None and message.correlation_id != correlation_id:
                return False
            if round is not None and message.round != round:
                return False
            if expected_type is not None and message.message_type.value != expected_type:
                return False
            if sender is not None and message.sender != sender:
                return False
            if recipient is not None and recipient not in message.recipients:
                return False
            return True

        return [message for message in messages if keep(message)]

    @property
    def messages(self) -> list[CouncilMessage]:
        """All recorded messages, in recording order (copy)."""
        with self._lock:
            return list(self._messages)

    def count(self) -> int:
        """Number of recorded messages."""
        with self._lock:
            return len(self._messages)

    def to_jsonl(self) -> str:
        """Full history as a JSONL string (one validated message per line)."""
        with self._lock:
            return "".join(line + "\n" for line in (m.model_dump_json() for m in self._messages))

    def reload(self) -> list[CouncilMessage]:
        """Re-read the persisted JSONL file, validating every line."""
        loaded: list[CouncilMessage] = []
        if self.path.exists():
            with self.path.open(encoding="utf-8") as handle:
                for number, line in enumerate(handle, start=1):
                    stripped = line.strip()
                    if not stripped:
                        continue
                    try:
                        loaded.append(validate_envelope(stripped))
                    except InvalidEnvelopeError as exc:
                        raise InvalidEnvelopeError(f"{self.path}:{number}: {exc.detail}") from exc
        with self._lock:
            self._messages = loaded
        return loaded

    @classmethod
    def load(cls, incident_id: str, path: str | Path) -> DebateHistory:
        """Load a persisted history, validating every recorded message."""
        history = cls(incident_id, path)
        history.reload()
        return history
