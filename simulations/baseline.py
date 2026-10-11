"""A trivial baseline investigator.

This baseline is deterministic and reads ONLY the `EvidenceStore` (never ground
truth; ground truth reaches the benchmark exclusively through
`simulations.scoring`). It uses simple keyword heuristics:

* benign markers (backup job, scheduled, approved, ...) in the available
  evidence -> stance OPPOSE (the activity looks authorized);
* threat markers (ransom, lsass, brute force, ...) -> stance SUPPORT;
* otherwise ABSTAIN.

When the stance changes between rounds it emits a `PositionRevision` citing the
newly revealed evidence — which is how scenario 3's SUPPORT->OPPOSE flip is
reproduced without any knowledge of the scoring key.
"""

from __future__ import annotations

import json

from contracts.common import Position, Severity
from contracts.investigation import (
    DebatePosition,
    InvestigationFindings,
    PositionRevision,
    TimelineEvent,
)
from simulations.loader import EvidenceStore
from simulations.runs import InvestigationRun, RoundRecord, make_tool_invocation

AGENT_ID = "baseline-investigator"

BENIGN_KEYWORDS = [
    "backup job",
    "approved",
    "change ticket",
    "retention",
    "sanctioned",
]
THREAT_KEYWORDS = [
    "ransom",
    "encryptor",
    "brute force",
    "lsass",
    "phishing",
    "kerberoast",
    "lateral movement",
    "beacon",
    "c2",
    "credential",
    "dump",
    "port scan",
    "shadow cop",
    "scheduled task",
    "authorized_keys",
    "exfiltrat",
    "rclone",
]
CRITICAL_KEYWORDS = ["ransom", "encryptor", ".locked", "vssadmin", "mass file"]
HIGH_KEYWORDS = ["lsass", "phishing", "lateral", "admin share", "authorized_keys", "credential"]


def _evidence_text(evidence) -> str:
    parts = [evidence.description, evidence.event_type, evidence.source]
    try:
        parts.append(json.dumps(evidence.raw_data, sort_keys=True))
    except (TypeError, ValueError):
        parts.append(str(evidence.raw_data))
    return " ".join(parts).casefold()


def _matched_keywords(text: str, keywords: list[str]) -> list[str]:
    return [kw for kw in keywords if kw.casefold() in text]


def _stance(benign: bool, threat: bool) -> Position:
    if benign:
        return Position.OPPOSE
    if threat:
        return Position.SUPPORT
    return Position.ABSTAIN


def _severity(benign: bool, threat_keywords: list[str]) -> Severity:
    if benign:
        return Severity.LOW
    if any(kw in CRITICAL_KEYWORDS for kw in threat_keywords):
        return Severity.CRITICAL
    if any(kw in HIGH_KEYWORDS for kw in threat_keywords):
        return Severity.HIGH
    return Severity.MEDIUM


def _position(
    store: EvidenceStore,
    round_: int,
    stance: Position,
    threat_hits: list[str],
    benign_hits: list[str],
    reasoning: str,
    confidence: float,
) -> DebatePosition:
    supporting = threat_hits if stance is Position.SUPPORT else []
    opposing = benign_hits if stance is Position.OPPOSE else []
    return DebatePosition(
        agent_id=AGENT_ID,
        incident_id=store.incident_id,
        round=round_,
        position=stance,
        supporting_evidence_ids=supporting,
        opposing_evidence_ids=opposing,
        reasoning=reasoning,
        confidence=confidence,
        conditions_to_change_position=["new evidence that contradicts the current reading"],
    )


def _tool_invocations(
    store: EvidenceStore, round_: int, evidence_ids: list[str]
) -> list:
    """Deterministic audit records of the conceptual steps the baseline takes."""
    invocations = [
        make_tool_invocation(
            incident_id=store.incident_id,
            tool_name="search_logs",
            arguments={"incident_id": store.incident_id, "query": "login OR failed"},
            referenced_evidence_ids=evidence_ids,
            duration_ms=10 + round_,
        ),
        make_tool_invocation(
            incident_id=store.incident_id,
            tool_name="build_timeline",
            arguments={"incident_id": store.incident_id, "evidence_ids": evidence_ids},
            referenced_evidence_ids=evidence_ids,
            duration_ms=15 + 3 * round_,
        ),
    ]
    if evidence_ids:
        invocations.append(
            make_tool_invocation(
                incident_id=store.incident_id,
                tool_name="lookup_mitre_technique",
                arguments={"technique_id": "T1486"},
                referenced_evidence_ids=[evidence_ids[0]],
                duration_ms=7,
            )
        )
    return invocations


def baseline_investigator(store: EvidenceStore) -> InvestigationRun:
    """Run the heuristic baseline over every round the store can reveal."""
    rounds: list[RoundRecord] = []
    previous_position: DebatePosition | None = None
    previously_seen: set[str] = set()

    for round_ in range(1, store.max_round + 1):
        available = store.available_evidence(round_)
        available_ids = [e.evidence_id for e in available]
        texts = [(e.evidence_id, _evidence_text(e)) for e in available]
        benign_hits = [eid for eid, t in texts if _matched_keywords(t, BENIGN_KEYWORDS)]
        threat_hits = [eid for eid, t in texts if _matched_keywords(t, THREAT_KEYWORDS)]
        threat_keywords = [kw for _, t in texts for kw in _matched_keywords(t, THREAT_KEYWORDS)]
        newly_revealed = [eid for eid in available_ids if eid not in previously_seen]
        newly_benign = [eid for eid in newly_revealed if eid in benign_hits]

        stance = _stance(bool(benign_hits), bool(threat_hits))
        severity = _severity(bool(benign_hits), threat_keywords)
        confidence = 0.5 if stance is Position.ABSTAIN else 0.75

        findings = InvestigationFindings(
            agent_id=AGENT_ID,
            incident_id=store.incident_id,
            round=round_,
            findings=(
                f"Round {round_}: baseline examined {len(available)} evidence items. "
                f"Benign markers matched: {len(benign_hits)}; threat markers matched: "
                f"{len(threat_hits)}. Baseline stance on the containment proposal: "
                f"{stance.value} (severity assessment {severity.value})."
            ),
            cited_evidence_ids=available_ids,
            confidence=confidence,
            uncertainties=["keyword heuristics only; no semantic analysis performed"],
            timeline=[
                TimelineEvent(
                    timestamp=e.timestamp,
                    description=e.description,
                    evidence_ids=[e.evidence_id],
                    host_id=e.host_id,
                    event_type=e.event_type,
                )
                for e in sorted(available, key=lambda e: (e.timestamp, e.evidence_id))
            ],
            severity_assessment=severity,
        )

        position = _position(
            store,
            round_,
            stance,
            threat_hits,
            benign_hits,
            reasoning=(
                f"Newly revealed benign evidence: {newly_benign or 'none'}; "
                f"threat-marked evidence: {threat_hits or 'none'}."
            ),
            confidence=confidence,
        )

        revision: PositionRevision | None = None
        if previous_position is not None and previous_position.position != stance:
            revision = PositionRevision(
                agent_id=AGENT_ID,
                incident_id=store.incident_id,
                round=round_,
                previous_position=previous_position,
                new_position=position,
                triggering_evidence_ids=newly_benign or newly_revealed,
                explanation=(
                    f"Newly revealed evidence changed the picture: {newly_benign or newly_revealed}"
                ),
            )

        rounds.append(
            RoundRecord(
                round_=round_,
                findings=findings,
                position=position,
                revision=revision,
                tool_invocations=_tool_invocations(store, round_, available_ids),
            )
        )
        previous_position = position
        previously_seen.update(available_ids)

    return InvestigationRun(
        scenario_id=store.scenario_id, incident_id=store.incident_id, rounds=rounds
    )
