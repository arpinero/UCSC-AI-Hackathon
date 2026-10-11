"""Read-only evidence store over the synthetic scenario layout.

Implements the tools-engineer view of the scenario format published by
evaluation-engineer (``simulations/FORMAT.md`` v1 on ``feat/evaluation``):

    simulations/scenarios/<scenario_id>/
      incident.json              # contracts.Incident (not needed by the tools)
      evidence/evidence-NN.json  # one contracts.Evidence object per file
      ground_truth.json          # evaluation's scoring key -- NEVER read here

Rules enforced by this module:

* strictly read-only: evidence is loaded once at construction time;
* every file must validate against the frozen ``contracts.Evidence`` model
  (strict, ``extra="forbid"``); anything else fails loudly at construction;
* evidence IDs must be unique and ``incident_id`` must be uniform;
* ``ground_truth.json`` is never opened -- reveal rounds and scoring are
  evaluation's concern (``simulations.loader``). Callers that need
  round-limited visibility pass an explicit ``visible_evidence_ids``
  allowlist, so multi-round tests can simulate "new evidence arrives"
  without this class ever touching ground-truth data.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path

from pydantic import ValidationError

from contracts.evidence import Evidence


class EvidenceStoreError(RuntimeError):
    """Raised when the store cannot be built from the scenario directory."""


class EvidenceStore:
    """In-memory read-only index over one scenario's ``evidence/`` directory.

    The scenario directory is constructor-injected so tests can point the
    store at a fixture directory instead of ``simulations/scenarios/<id>``.
    """

    def __init__(
        self,
        scenario_dir: str | Path,
        *,
        visible_evidence_ids: Iterable[str] | None = None,
    ) -> None:
        scenario = Path(scenario_dir)
        evidence_dir = scenario / "evidence"
        if not evidence_dir.is_dir():
            raise EvidenceStoreError(f"evidence directory not found: {evidence_dir}")

        items: list[Evidence] = []
        seen_ids: set[str] = set()
        incident_ids: set[str] = set()
        for path in sorted(evidence_dir.glob("*.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise EvidenceStoreError(f"cannot read evidence file {path}: {exc}") from exc
            try:
                item = Evidence.model_validate(payload)
            except ValidationError as exc:
                raise EvidenceStoreError(
                    f"{path} does not validate against contracts.Evidence: {exc}"
                ) from exc
            if item.evidence_id in seen_ids:
                raise EvidenceStoreError(f"duplicate evidence_id {item.evidence_id!r} in {path}")
            seen_ids.add(item.evidence_id)
            incident_ids.add(item.incident_id)
            items.append(item)

        if not items:
            raise EvidenceStoreError(f"no evidence files found under {evidence_dir}")
        if len(incident_ids) > 1:
            raise EvidenceStoreError(
                f"evidence in {evidence_dir} mixes incident_ids: {sorted(incident_ids)}"
            )

        if visible_evidence_ids is not None:
            allow = set(visible_evidence_ids)
            unknown = sorted(allow - seen_ids)
            if unknown:
                raise EvidenceStoreError(f"visible_evidence_ids not in store: {unknown}")
            items = [item for item in items if item.evidence_id in allow]

        self._scenario_dir = scenario
        self._evidence_dir = evidence_dir
        self._items = sorted(items, key=lambda item: (item.timestamp, item.evidence_id))
        self._by_id: dict[str, Evidence] = {item.evidence_id: item for item in self._items}
        self._by_host: dict[str, list[Evidence]] = {}
        self._by_event_type: dict[str, list[Evidence]] = {}
        for item in self._items:
            self._by_host.setdefault(item.host_id, []).append(item)
            self._by_event_type.setdefault(item.event_type, []).append(item)

    # -- basic properties ----------------------------------------------------

    @property
    def scenario_dir(self) -> Path:
        """Directory of the scenario this store was built from."""
        return self._scenario_dir

    @property
    def incident_id(self) -> str:
        """The (uniform) incident_id of every evidence item in this store."""
        return self._items[0].incident_id

    def evidence_ids(self) -> list[str]:
        """All evidence IDs, ordered by (timestamp, evidence_id)."""
        return [item.evidence_id for item in self._items]

    def hosts(self) -> list[str]:
        """Distinct host_ids present in the evidence, sorted."""
        return sorted(self._by_host)

    def event_types(self) -> list[str]:
        """Distinct event_types present in the evidence, sorted."""
        return sorted(self._by_event_type)

    def __len__(self) -> int:
        return len(self._items)

    def __contains__(self, evidence_id: object) -> bool:
        return evidence_id in self._by_id

    # -- lookup APIs ----------------------------------------------------------

    def get(self, evidence_id: str) -> Evidence | None:
        """Return the evidence item with this ID, or None if unknown."""
        return self._by_id.get(evidence_id)

    def all_evidence(self) -> list[Evidence]:
        """All evidence items, ordered by (timestamp, evidence_id)."""
        return list(self._items)

    def by_host(self, host_id: str) -> list[Evidence]:
        """Evidence items for one host, timestamp-ordered."""
        return list(self._by_host.get(host_id, ()))

    def by_event_type(self, event_type: str) -> list[Evidence]:
        """Evidence items with this exact event_type, timestamp-ordered."""
        return list(self._by_event_type.get(event_type, ()))

    def in_time_range(
        self,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[Evidence]:
        """Evidence items with ``start <= timestamp <= end`` (bounds optional)."""
        return [
            item
            for item in self._items
            if (start is None or item.timestamp >= start)
            and (end is None or item.timestamp <= end)
        ]
