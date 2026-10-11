# Synthetic Scenario Format (v1)

Published by `evaluation-engineer`. This format is the shared interface between
the simulation workstream (scenarios, loader, scoring, benchmark) and every
other agent that needs synthetic evidence to test against.

**Location of this spec:** `simulations/FORMAT.md` (branch `feat/evaluation`).
**Loader implementation:** `simulations/loader.py`. **Scoring:** `simulations/scoring.py`.

## Directory layout

Every scenario lives in its own directory:

    simulations/scenarios/<scenario_id>/
      incident.json              # validates against contracts.Incident (frozen v1)
      evidence/evidence-NN.json  # each file validates against contracts.Evidence
      ground_truth.json          # NOT read by the investigation flow (see below)

Example: `simulations/scenarios/ransom01/evidence/evidence-03.json`.

### `incident.json`

A single JSON object that must validate against `contracts.incident.Incident`
(strict, `extra="forbid"`, timezone-aware UTC timestamps). `incident_id` and
`scenario_id` are stable and unique per scenario. `initial_description` is the
only text an investigator sees before examining evidence.

### `evidence/evidence-NN.json`

One JSON object per file validating against `contracts.evidence.Evidence`
(strict). `NN` is a zero-padded two-digit sequence number (`01`, `02`, …)
matching the file name order; files are also sorted by name by the loader.

**Evidence ID convention:** `EV-<scenario_id>-<NN>`, e.g. `EV-ransom01-03`.
Evidence IDs are stable and unique: once published, an ID always refers to the
same evidence item. `incident_id` inside every evidence item MUST match the
scenario's `incident.json`.

Each scenario contains 8–15 evidence items spread across 2–3 `host_id`s, with
sources drawn from `syslog`, `zeek`, `edr`, `auth` (and similar), and
timestamps that form a reconstructable timeline. `raw_data` carries the
structured payload (e.g. log lines, flow records, process hashes, MITRE
technique hints, external IPs) so `search_logs`, `build_timeline`, `enrich_ip`,
and `lookup_mitre_technique` have real signal to work with.

### `ground_truth.json`

The scoring key. It is **never** exposed through the investigator-facing loader
API (`EvidenceStore`); it is only read by `simulations.scoring` and by tests.
Schema (implemented as `simulations.ground_truth.GroundTruth`):

```jsonc
{
  "scenario_id": "ransom01",
  "incident_id": "INC-2026-0001",
  "classification": "confirmed_incident",   // confirmed_incident | suspicious_activity | benign
  "expected_severity": "CRITICAL",          // contracts.Severity the investigation should conclude
  "containment_proposal": "Isolate FS-01 and WS-FIN-07",  // the debated proposal
  "expected_stance": "SUPPORT",             // final contracts.Position on the proposal
  "expected_findings": ["..."],             // key factual findings (soft keyword match)
  "must_cite_evidence_ids": ["EV-ransom01-09"], // citations a correct run MUST include
  "timeline_anchors": [                     // soft timeline overlap targets
    {"timestamp": "2026-09-18T04:23:00Z", "host_id": "FS-01", "description_contains": "encryptor"}
  ],
  "mitre_techniques": ["T1486", "T1490"],
  "evidence_reveal_rounds": {"EV-ransom01-01": 1, "EV-ransom01-12": 2},
  "expected_position_revisions": [
    {
      "previous_position": "SUPPORT",
      "new_position": "OPPOSE",
      "triggering_evidence_ids": ["EV-exfil01-09"],
      "min_round": 2
    }
  ],
  "narrative": "Human-readable ground-truth story for maintainers."
}
```

## Progressive disclosure: `reveal_round`

Multi-round investigation is simulated by hiding later-round evidence until its
round. Because `contracts.Evidence` is **frozen** (`extra="forbid"`), the round
information cannot live inside the evidence files. Instead:

- `ground_truth.json` carries `evidence_reveal_rounds`: a map of
  `evidence_id -> reveal_round` (a non-negative integer).
- **Every evidence item MUST be listed exactly once.** An omitted ID fails
  loader validation. A round-1 item may be listed explicitly or omitted only if
  a default is configured — the loader's default is round 1, and the committed
  scenarios list every item explicitly for clarity.
- The loader enforces: `reveal_round >= 1`, unique keys, and that every key
  matches an evidence file in the scenario.

Semantics: evidence with `reveal_round <= N` is **available** in round `N`.
The investigator-facing API is `EvidenceStore.available_evidence(round)` (and
`get_evidence(evidence_id, round)`), which hide everything else. "New evidence
arrives" between council rounds is simulated by calling these with a higher
round number. This is how scenario 3 tests position revision: round-1 evidence
suggests exfiltration; a round-2 backup-job log should flip SUPPORT -> OPPOSE.

## Scoring interface (summary)

`simulations.scoring.score_run(ground_truth, run)` scores an investigation run
against the key. Metrics (each 0.0–1.0, plus an overall weighted score):

| Metric | Meaning |
|---|---|
| `citation_validity` | every cited/triggering evidence id exists in the scenario |
| `stance_correctness` | final position matches `expected_stance` |
| `severity_match` | final severity assessment matches `expected_severity` |
| `timeline_anchor_overlap` | soft overlap of reported timeline with `timeline_anchors` |
| `position_change_correctness` | did the run make the expected `PositionRevision`(s) — and only those |

`scripts/benchmark.py` runs any `Callable[[EvidenceStore], list[RoundRecord]]`
investigator (the real reasoning engine can be plugged in after integration)
against all scenarios and reports findings accuracy, stance accuracy,
tool-call count, and mean/max `ToolInvocation.duration_ms`.

## Publishing changes

This format is owned by `evaluation-engineer` (`simulations/`). Changes that
affect other agents (layout, ID convention, reveal-round semantics) must be
announced on the coordination bus.
