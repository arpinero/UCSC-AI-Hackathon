"""enrich_ip: synthetic IP enrichment from a static map plus evidence.

SYNTHETIC ENRICHMENT ONLY. The reputation map is a committed static file
(``src/forensics/tools/data/ip_reputation.json``) written for the evaluation
scenarios -- it is NOT real threat intelligence and no external reputation
service is ever queried. Every result is marked with its reputation source
via a ``reputation_source:*`` label in ``known_threat_labels`` so consumers
can tell synthetic data from absent data.

Evidence-derived facts are strictly observational: whether the IP was seen
in scenario evidence (and in network-flow-like evidence) is reported, but the
reputation verdict itself comes only from the static map.
"""

from __future__ import annotations

import ipaddress
import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from contracts.tools import EnrichIPArgs, EnrichIPResult, ToolError
from forensics.tools.base import ForensicTool, ForensicToolError
from forensics.tools.evidence_store import Evidence
from forensics.tools.impl.store_tools import _flatten

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_DEFAULT_MAP_PATH = _DATA_DIR / "ip_reputation.json"

# raw_data keys checked for exact IP references.
_IP_KEYS = (
    "ip",
    "src_ip",
    "dst_ip",
    "remote_ip",
    "peer_ip",
    "client_ip",
    "server_ip",
    "internal_ip",
    "external_ip",
)


class EnrichIP(ForensicTool):
    """Enrich an IP from the synthetic static reputation map + evidence."""

    name = "enrich_ip"
    description = (
        "Enrich an IP address: internal/private-range classification, plus a "
        "SYNTHETIC static reputation map for scenario IPs (marked with its "
        "source) and whether the IP was observed in collected evidence."
    )
    args_model = EnrichIPArgs
    result_model = EnrichIPResult

    def __init__(
        self,
        store: Any,
        reputation_map_path: str | Path | None = None,
    ) -> None:
        # ``store`` is duck-typed (all_evidence()) to stay decoupled from the
        # concrete EvidenceStore import in tests using stand-in stores.
        self.store = store
        path = Path(reputation_map_path) if reputation_map_path is not None else _DEFAULT_MAP_PATH
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"cannot load IP reputation map {path}: {exc}") from exc
        self._internal_networks = [
            ipaddress.ip_network(rng) for rng in document.get("internal_ranges", [])
        ]
        self._entries: dict[str, dict[str, Any]] = dict(document.get("entries", {}))
        self._default_reputation = str(document.get("default_reputation", "unknown"))

    def run(self, args: EnrichIPArgs) -> BaseModel:
        try:
            address = ipaddress.ip_address(args.ip.strip())
        except ValueError as exc:
            raise ForensicToolError(
                ToolError(error_code="INVALID_IP", message=f"not a valid IP address: {args.ip}")
            ) from exc

        is_internal = any(address in network for network in self._internal_networks)
        entry = self._entries.get(str(address))

        labels: list[str] = []
        source = "none"
        reputation = self._default_reputation
        asn: str | None = None
        country: str | None = None
        if entry is not None:
            labels.extend(str(label) for label in entry.get("threat_labels", []))
            source = str(entry.get("source", "static-map"))
            reputation = str(entry.get("reputation", reputation))
            asn = _non_empty_str(entry.get("asn"))
            country = _non_empty_str(entry.get("country"))

        observed = [
            item for item in self.store.all_evidence() if _ip_in_evidence(item, str(address))
        ]
        if observed:
            labels.append("observed_in_scenario_evidence")
            flow_like = any(
                "flow" in item.event_type.lower() or "network" in item.event_type.lower()
                for item in observed
            )
            if flow_like:
                labels.append("observed_in_network_flow_evidence")
        labels.append(f"reputation_source:{source}")

        return EnrichIPResult(
            ip=str(address),
            asn=asn,
            country=country,
            reputation=reputation,
            known_threat_labels=labels,
            is_internal=is_internal,
        )


def _non_empty_str(value: Any) -> str | None:
    """Coerce a map value to a non-empty string (contract-safe) or None."""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _ip_in_evidence(item: Evidence, ip: str) -> bool:
    """Exact match on known raw_data IP keys, else substring fallback."""
    raw = item.raw_data
    if isinstance(raw, dict):
        for key in _IP_KEYS:
            value = raw.get(key)
            if isinstance(value, str) and value.strip() == ip:
                return True
    parts: list[str] = []
    _flatten(raw, parts)
    return ip in " ".join(parts)
