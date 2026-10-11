"""Evidence-store-backed tools: search_logs, host/user context, build_timeline.

All results are derived strictly from what the evidence store actually
contains: every returned LogEntry/TimelineEvent carries the evidence_id it
came from (provenance), and nothing is ever invented.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from pydantic import BaseModel

from contracts.investigation import TimelineEvent
from contracts.tools import (
    BuildTimelineArgs,
    BuildTimelineResult,
    GetHostContextArgs,
    GetHostContextResult,
    GetUserContextArgs,
    GetUserContextResult,
    LogEntry,
    SearchLogsArgs,
    SearchLogsResult,
)
from forensics.tools.base import ForensicTool
from forensics.tools.evidence_store import EvidenceStore

# Keys checked (in order) when choosing the human-readable log message.
_MESSAGE_KEYS = ("message", "log_line", "line", "log", "event", "event_message")

# Keys checked (in order) for host facts and service-like names.
_HOST_FACT_KEYS = ("hostname", "os", "criticality")
_SERVICE_KEYS = ("service", "service_name", "process_name", "image", "process")

# Keys checked for user/account references inside raw_data.
_USER_KEYS = (
    "user",
    "user_id",
    "username",
    "account",
    "account_name",
    "subject",
    "actor",
    "login",
    "sam_account",
    "upn",
)


def _flatten(value: Any, out: list[str]) -> None:
    """Recursively collect raw_data keys and scalar values as strings."""
    if isinstance(value, dict):
        for key, item in value.items():
            out.append(str(key))
            _flatten(item, out)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _flatten(item, out)
    elif value is not None:
        out.append(str(value))


def _searchable_text(store_item: Any) -> str:
    """Lowercased text over all evidence fields for substring search."""
    parts = [
        store_item.evidence_id,
        store_item.host_id,
        store_item.source,
        store_item.event_type,
        store_item.description,
    ]
    _flatten(store_item.raw_data, parts)
    return " ".join(parts).lower()


def _message_like(store_item: Any) -> str | None:
    raw = store_item.raw_data
    if not isinstance(raw, dict):
        return None
    for key in _MESSAGE_KEYS:
        value = raw.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return None


def _first_raw(store_items: list[Any], key: str) -> str | None:
    for store_item in store_items:
        value = store_item.raw_data.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return None


def _iso(ts: datetime) -> str:
    return ts.strftime("%Y-%m-%dT%H:%M:%SZ")


class EvidenceBackedTool(ForensicTool):
    """Base for tools that read from a constructor-injected EvidenceStore."""

    def __init__(self, store: EvidenceStore) -> None:
        self.store = store


class SearchLogs(EvidenceBackedTool):
    """Substring/field search over log-like evidence in the store.

    The query is matched (case-insensitive) against the flattened evidence
    text: description, source, event_type, and all raw_data keys and values.
    Optional host_id / start / end filters narrow the search window. Every
    returned LogEntry carries the evidence_id it came from.
    """

    name = "search_logs"
    description = (
        "Search incident logs and raw evidence by substring; optionally narrow "
        "by host and time range. Returns timestamp-ordered log entries with "
        "the evidence_id each entry came from."
    )
    args_model = SearchLogsArgs
    result_model = SearchLogsResult

    def run(self, args: SearchLogsArgs) -> BaseModel:
        candidates = self.store.in_time_range(args.start, args.end)
        if args.host_id is not None:
            candidates = [c for c in candidates if c.host_id == args.host_id]
        query = args.query.lower()
        matches = [c for c in candidates if query in _searchable_text(c)]

        limited = matches[: args.limit]
        entries = [
            LogEntry(
                timestamp=c.timestamp,
                host_id=c.host_id,
                source=c.source,
                message=_message_like(c) or c.description,
                evidence_id=c.evidence_id,
            )
            for c in limited
        ]
        return SearchLogsResult(
            entries=entries,
            matched_evidence_ids=sorted({c.evidence_id for c in matches}),
            truncated=len(matches) > len(limited),
        )


class GetHostContext(EvidenceBackedTool):
    """Aggregate host facts from evidence: services seen, alerts, host facts.

    Only reports what the evidence actually contains; a host with no
    evidence yields empty fields plus an explanatory note.
    """

    name = "get_host_context"
    description = (
        "Aggregate host context (hostname/os/criticality if present, services "
        "seen in logs, recent alerts) strictly from collected evidence."
    )
    args_model = GetHostContextArgs
    result_model = GetHostContextResult
    _MAX_ALERTS = 10

    def run(self, args: GetHostContextArgs) -> BaseModel:
        host_items = self.store.by_host(args.host_id)
        if not host_items:
            return GetHostContextResult(
                host_id=args.host_id,
                notes=f"no evidence found for host '{args.host_id}'",
            )

        services: set[str] = set()
        for item in host_items:
            for key in _SERVICE_KEYS:
                value = item.raw_data.get(key)
                if isinstance(value, str) and value.strip():
                    services.add(value)

        alerts = [
            item
            for item in host_items
            if "alert" in item.event_type.lower()
            or (isinstance(item.raw_data.get("alert"), str) and item.raw_data["alert"])
        ]
        alert_lines = [
            f"{_iso(item.timestamp)} [{item.host_id}] {item.description}"
            for item in alerts[: self._MAX_ALERTS]
        ]

        notes = (
            f"derived from {len(host_items)} evidence items "
            f"({_iso(host_items[0].timestamp)} to {_iso(host_items[-1].timestamp)})"
        )
        return GetHostContextResult(
            host_id=args.host_id,
            hostname=_first_raw(host_items, "hostname"),
            os=_first_raw(host_items, "os"),
            criticality=_first_raw(host_items, "criticality"),
            services=sorted(services),
            recent_alerts=alert_lines,
            notes=notes,
        )


class GetUserContext(EvidenceBackedTool):
    """Aggregate user facts from evidence: accounts seen, roles, anomalies."""

    name = "get_user_context"
    description = (
        "Aggregate user context (display name, roles, groups, MFA state, "
        "anomalies) strictly from collected evidence that mentions the user."
    )
    args_model = GetUserContextArgs
    result_model = GetUserContextResult
    _MAX_ANOMALIES = 10

    @staticmethod
    def _mentions_user(item: Any, user_id: str) -> bool:
        needle = user_id.lower()
        raw = item.raw_data
        if not isinstance(raw, dict):
            return False
        for key in _USER_KEYS:
            value = raw.get(key)
            if isinstance(value, str) and value.lower() == needle:
                return True
            if isinstance(value, (list, tuple)) and needle in [str(v).lower() for v in value]:
                return True
        return False

    def run(self, args: GetUserContextArgs) -> BaseModel:
        user_items = [
            item for item in self.store.all_evidence() if self._mentions_user(item, args.user_id)
        ]
        if not user_items:
            return GetUserContextResult(user_id=args.user_id)

        roles: set[str] = set()
        groups: set[str] = set()
        for item in user_items:
            for key, target in (("roles", roles), ("groups", groups)):
                value = item.raw_data.get(key)
                if isinstance(value, (list, tuple)):
                    target.update(str(v) for v in value if str(v).strip())

        mfa: bool | None = None
        for item in user_items:
            value = item.raw_data.get("mfa_enabled")
            if isinstance(value, bool):
                mfa = value
                break

        anomaly_items = [
            item
            for item in user_items
            if "anomal" in item.event_type.lower()
            or (isinstance(item.raw_data.get("anomaly"), str) and item.raw_data["anomaly"])
        ]
        anomalies = [
            f"{_iso(item.timestamp)} [{item.host_id}] {item.description}"
            for item in anomaly_items[: self._MAX_ANOMALIES]
        ]

        return GetUserContextResult(
            user_id=args.user_id,
            display_name=_first_raw(user_items, "display_name")
            or _first_raw(user_items, "full_name"),
            roles=sorted(roles),
            groups=sorted(groups),
            mfa_enabled=mfa,
            anomalies=anomalies,
        )


class BuildTimeline(EvidenceBackedTool):
    """Merge given evidence_ids into a timestamp-ordered timeline; flag gaps."""

    name = "build_timeline"
    description = (
        "Merge the given evidence IDs into an ordered incident timeline "
        "(timestamp ascending). Flags unexplained time gaps and unknown "
        "evidence IDs instead of guessing."
    )
    args_model = BuildTimelineArgs
    result_model = BuildTimelineResult

    def __init__(
        self,
        store: EvidenceStore,
        *,
        gap_threshold: timedelta = timedelta(hours=6),
    ) -> None:
        super().__init__(store)
        self.gap_threshold = gap_threshold

    def run(self, args: BuildTimelineArgs) -> BaseModel:
        events: list[TimelineEvent] = []
        gaps: list[str] = []
        missing: list[str] = []

        for evidence_id in args.evidence_ids:
            item = self.store.get(evidence_id)
            if item is None:
                if evidence_id not in missing:
                    missing.append(evidence_id)
                continue
            events.append(
                TimelineEvent(
                    timestamp=item.timestamp,
                    description=item.description,
                    evidence_ids=[item.evidence_id],
                    host_id=item.host_id,
                    event_type=item.event_type,
                )
            )

        events.sort(key=lambda event: (event.timestamp, event.description))
        gaps.extend(f"evidence id not found in store: {evidence_id}" for evidence_id in missing)

        for previous, current in zip(events, events[1:]):
            delta = current.timestamp - previous.timestamp
            if delta > self.gap_threshold:
                hours = delta.total_seconds() / 3600.0
                gaps.append(
                    f"unexplained gap of {hours:.1f}h between "
                    f"{_iso(previous.timestamp)} and {_iso(current.timestamp)}"
                )

        return BuildTimelineResult(timeline=events, gaps=gaps)
