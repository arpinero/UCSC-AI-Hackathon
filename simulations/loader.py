"""Scenario loader: strict validation + round-based progressive evidence reveal.

Two views are provided:

* `ScenarioBundle` — the full scenario including ground truth. Used ONLY by
  scoring, tests, and benchmark tooling. Never hand this to an investigator.
* `EvidenceStore` — the investigator-facing API. It exposes the incident and
  evidence that is available in a given round. It structurally cannot provide
  ground truth: the object simply does not hold it.

Every file is validated against the frozen contracts (`contracts.Incident`,
`contracts.Evidence`); invalid payloads fail loudly with `ScenarioFormatError`.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from contracts.evidence import Evidence
from contracts.incident import Incident
from simulations.ground_truth import GroundTruth

DEFAULT_SCENARIOS_ROOT = Path(__file__).resolve().parent / "scenarios"

_EVIDENCE_FILE_RE = re.compile(r"^evidence-(\d+)\.json$")

REQUIRED_EVIDENCE_MIN = 8
REQUIRED_EVIDENCE_MAX = 15
REQUIRED_HOSTS_MIN = 2
REQUIRED_HOSTS_MAX = 3


class ScenarioFormatError(Exception):
    """Raised when a scenario directory does not conform to simulations/FORMAT.md."""


def _fail(scenario_dir: Path, detail: str) -> ScenarioFormatError:
    return ScenarioFormatError(f"invalid scenario at {scenario_dir}: {detail}")


def _load_json(path: Path) -> dict[str, Any]:
    try:
        with path.open(encoding="utf-8") as fh:
            payload = json.load(fh)
    except json.JSONDecodeError as exc:
        raise ScenarioFormatError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ScenarioFormatError(
            f"{path}: top-level JSON object expected, got {type(payload).__name__}"
        )
    return payload


class ScenarioBundle:
    """A fully validated scenario, including the ground-truth scoring key."""

    def __init__(
        self,
        scenario_dir: Path,
        incident: Incident,
        evidence: list[Evidence],
        ground_truth: GroundTruth,
    ) -> None:
        self.scenario_dir = scenario_dir
        self.incident = incident
        self.evidence = evidence
        self.ground_truth = ground_truth

    @property
    def scenario_id(self) -> str:
        return self.incident.scenario_id

    @property
    def incident_id(self) -> str:
        return self.incident.incident_id

    @property
    def evidence_ids(self) -> list[str]:
        return [e.evidence_id for e in self.evidence]

    def reveal_round(self, evidence_id: str) -> int:
        return self.ground_truth.evidence_reveal_rounds[evidence_id]

    def available_evidence(self, round_: int) -> list[Evidence]:
        """Evidence visible in `round_` (reveal_round <= round_)."""
        if round_ < 1:
            raise ValueError(f"round must be >= 1, got {round_}")
        return [e for e in self.evidence if self.reveal_round(e.evidence_id) <= round_]


class EvidenceStore:
    """Investigator-facing view of a scenario.

    Provides the incident and progressively-revealed evidence. Ground truth is
    deliberately absent from this object: there is no attribute, method, or
    property that can yield it.
    """

    def __init__(
        self,
        scenario_id: str,
        incident: Incident,
        evidence: list[Evidence],
        reveal_rounds: dict[str, int],
    ) -> None:
        self._scenario_id = scenario_id
        self.incident = incident
        self._evidence = {e.evidence_id: e for e in evidence}
        self._reveal_rounds = dict(reveal_rounds)

    @property
    def scenario_id(self) -> str:
        return self._scenario_id

    @property
    def incident_id(self) -> str:
        return self.incident.incident_id

    @property
    def max_round(self) -> int:
        """Highest reveal round; investigators should iterate 1..max_round."""
        return max(self._reveal_rounds.values(), default=1)

    def available_evidence(self, round_: int = 1) -> list[Evidence]:
        """Evidence available in `round_`, sorted by evidence_id."""
        if round_ < 1:
            raise ValueError(f"round must be >= 1, got {round_}")
        ids = sorted(eid for eid, r in self._reveal_rounds.items() if r <= round_)
        return [self._evidence[eid] for eid in ids]

    def available_evidence_ids(self, round_: int = 1) -> list[str]:
        return [e.evidence_id for e in self.available_evidence(round_)]

    def get_evidence(self, evidence_id: str, round_: int = 1) -> Evidence | None:
        """One evidence item if it exists AND is available in `round_`."""
        if round_ < 1:
            raise ValueError(f"round must be >= 1, got {round_}")
        if self._reveal_rounds.get(evidence_id, 10**9) > round_:
            return None
        return self._evidence.get(evidence_id)


def _validate_incident(scenario_dir: Path, scenario_id: str) -> Incident:
    path = scenario_dir / "incident.json"
    if not path.is_file():
        raise _fail(scenario_dir, "missing incident.json")
    try:
        incident = Incident.model_validate(_load_json(path))
    except ValidationError as exc:
        raise _fail(
            scenario_dir, f"incident.json failed contracts.Incident validation: {exc}"
        ) from exc
    if incident.scenario_id != scenario_id:
        raise _fail(
            scenario_dir,
            f"incident.scenario_id {incident.scenario_id!r} != directory name {scenario_id!r}",
        )
    return incident


def _validate_evidence(
    scenario_dir: Path, scenario_id: str, incident_id: str
) -> list[Evidence]:
    evidence_dir = scenario_dir / "evidence"
    if not evidence_dir.is_dir():
        raise _fail(scenario_dir, "missing evidence/ directory")
    files = sorted(p for p in evidence_dir.iterdir() if _EVIDENCE_FILE_RE.match(p.name))
    if not files:
        raise _fail(scenario_dir, "evidence/ contains no evidence-NN.json files")
    evidence: list[Evidence] = []
    seen_ids: set[str] = set()
    numbers: list[int] = []
    for path in files:
        match = _EVIDENCE_FILE_RE.match(path.name)
        assert match is not None  # files were filtered by the same regex
        number = int(match.group(1))
        numbers.append(number)
        try:
            item = Evidence.model_validate(_load_json(path))
        except ValidationError as exc:
            raise _fail(
                scenario_dir, f"{path.name} failed contracts.Evidence validation: {exc}"
            ) from exc
        expected_id = f"EV-{scenario_id}-{number:02d}"
        if item.evidence_id != expected_id:
            raise _fail(
                scenario_dir,
                f"{path.name}: evidence_id {item.evidence_id!r} does not match "
                f"required convention {expected_id!r}",
            )
        if item.evidence_id in seen_ids:
            raise _fail(scenario_dir, f"duplicate evidence_id {item.evidence_id!r}")
        if item.incident_id != incident_id:
            raise _fail(
                scenario_dir,
                f"{item.evidence_id}: incident_id {item.incident_id!r} != "
                f"scenario incident_id {incident_id!r}",
            )
        seen_ids.add(item.evidence_id)
        evidence.append(item)
    if numbers != list(range(1, len(files) + 1)):
        raise _fail(
            scenario_dir, f"evidence files must be numbered consecutively from 01, got {numbers}"
        )
    return evidence



def _validate_ground_truth(
    scenario_dir: Path,
    scenario_id: str,
    incident_id: str,
    evidence_ids: list[str],
) -> GroundTruth:
    path = scenario_dir / "ground_truth.json"
    if not path.is_file():
        raise _fail(scenario_dir, "missing ground_truth.json")
    try:
        gt = GroundTruth.model_validate(_load_json(path))
    except ValidationError as exc:
        raise _fail(scenario_dir, f"ground_truth.json failed validation: {exc}") from exc
    if gt.scenario_id != scenario_id:
        raise _fail(scenario_dir, f"ground_truth.scenario_id {gt.scenario_id!r} != {scenario_id!r}")
    if gt.incident_id != incident_id:
        raise _fail(scenario_dir, f"ground_truth.incident_id {gt.incident_id!r} != {incident_id!r}")
    id_set = set(evidence_ids)
    gt_ids = set(gt.evidence_reveal_rounds)
    missing = sorted(id_set - gt_ids)
    unknown = sorted(gt_ids - id_set)
    if missing:
        raise _fail(scenario_dir, f"ground_truth.evidence_reveal_rounds missing: {missing}")
    if unknown:
        raise _fail(
            scenario_dir,
            f"ground_truth.evidence_reveal_rounds references unknown evidence: {unknown}",
        )
    for cited in gt.must_cite_evidence_ids:
        if cited not in id_set:
            raise _fail(
                scenario_dir, f"must_cite_evidence_ids references unknown evidence: {cited!r}"
            )
    for rev in gt.expected_position_revisions:
        unknown_triggers = sorted(set(rev.triggering_evidence_ids) - id_set)
        if unknown_triggers:
            raise _fail(
                scenario_dir,
                f"expected_position_revisions reference unknown evidence: {unknown_triggers}",
            )
    return gt


def _validate_shape(scenario_dir: Path, bundle: ScenarioBundle) -> None:
    count = len(bundle.evidence)
    if not (REQUIRED_EVIDENCE_MIN <= count <= REQUIRED_EVIDENCE_MAX):
        raise _fail(
            scenario_dir,
            f"expected {REQUIRED_EVIDENCE_MIN}-{REQUIRED_EVIDENCE_MAX} evidence items, got {count}",
        )
    hosts = {e.host_id for e in bundle.evidence}
    if not (REQUIRED_HOSTS_MIN <= len(hosts) <= REQUIRED_HOSTS_MAX):
        raise _fail(
            scenario_dir,
            f"expected {REQUIRED_HOSTS_MIN}-{REQUIRED_HOSTS_MAX} distinct host_ids, "
            f"got {sorted(hosts)}",
        )
    incident_hosts = set(bundle.incident.affected_hosts)
    if not hosts.issubset(incident_hosts):
        raise _fail(
            scenario_dir,
            f"evidence references hosts absent from incident.affected_hosts: "
            f"{sorted(hosts - incident_hosts)}",
        )


def load_scenario_bundle(scenario_dir: Path | str) -> ScenarioBundle:
    """Load and fully validate one scenario directory (includes ground truth)."""
    scenario_dir = Path(scenario_dir)
    if not scenario_dir.is_dir():
        raise ScenarioFormatError(f"scenario directory not found: {scenario_dir}")
    scenario_id = scenario_dir.name
    incident = _validate_incident(scenario_dir, scenario_id)
    evidence = _validate_evidence(scenario_dir, scenario_id, incident.incident_id)
    ground_truth = _validate_ground_truth(
        scenario_dir, scenario_id, incident.incident_id, [e.evidence_id for e in evidence]
    )
    bundle = ScenarioBundle(scenario_dir, incident, evidence, ground_truth)
    _validate_shape(scenario_dir, bundle)
    return bundle


def load_evidence_store(scenario_dir: Path | str) -> EvidenceStore:
    """Load a scenario and return the investigator-facing view (NO ground truth)."""
    bundle = load_scenario_bundle(scenario_dir)
    return EvidenceStore(
        scenario_id=bundle.scenario_id,
        incident=bundle.incident,
        evidence=bundle.evidence,
        reveal_rounds=bundle.ground_truth.evidence_reveal_rounds,
    )


def discover_scenario_dirs(root: Path | str = DEFAULT_SCENARIOS_ROOT) -> list[Path]:
    """All valid scenario directory paths under `root`, sorted by name."""
    root = Path(root)
    if not root.is_dir():
        raise ScenarioFormatError(f"scenarios root not found: {root}")
    dirs = [p for p in sorted(root.iterdir()) if p.is_dir() and (p / "incident.json").is_file()]
    if not dirs:
        raise ScenarioFormatError(f"no scenarios found under {root}")
    return dirs


def load_all_bundles(root: Path | str = DEFAULT_SCENARIOS_ROOT) -> list[ScenarioBundle]:
    """Load and validate every scenario under `root`."""
    return [load_scenario_bundle(p) for p in discover_scenario_dirs(root)]
