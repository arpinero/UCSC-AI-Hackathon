# Stage B Workstream 05 — Simulation & Evaluation Engineer

> **STATUS: PLACEHOLDER.** The full Stage B prompt will be supplied after
> Stage A review. Do not start until you receive it via the message bus.

- **Identity:** `evaluation-engineer`
- **Branch:** `feat/evaluation`
- **Worktree:** `/home/asus/forensics-worktrees/evaluation-engineer`
- **Ownership:** `simulations/` (scenarios + ground truth) and evaluation tests

## Interfaces you must produce (frozen contracts)

- Scenario data validating against `contracts/incident.py` (Incident) and
  `contracts/evidence.py` (Evidence with stable IDs and provenance).
- Ground truth mapping incident -> expected findings/positions so agent
  performance can be scored.

## Expected deliverables (subject to the full Stage B prompt)

- At least 3 synthetic scenarios (e.g. ransomware, credential theft via
  phishing, data exfiltration) as JSON files in `simulations/scenarios/`.
- Ground truth in `simulations/ground_truth/` (expected severity, timeline
  anchors, MITRE techniques, correct containment stance).
- Evaluation scripts/tests that run the reasoning stack against scenarios
  and compare with ground truth. Read-only forensic data only.

## Communication rules

- Check `inbox --agent evaluation-engineer` at every checkpoint (see AGENTS.md).
- The scenario store format is YOURS; tools-engineer and reasoning-engineer
  will REQUEST the schema from you. Publish it early via a PROGRESS message.

## Required tests

- Contract validation of every scenario file (all valid payloads must pass).
- Evaluation harness test on at least one scenario. Green pytest/ruff/mypy.

## Branch and commit rules

- Commit only to `feat/evaluation`. READY_FOR_INTEGRATION requires
  `--branch feat/evaluation --commit <sha>` + structured JSON body.
