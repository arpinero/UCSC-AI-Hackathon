# Stage B Workstream 03 — AGNTCY Integration Engineer

> **STATUS: PLACEHOLDER.** The full Stage B prompt will be supplied after
> Stage A review. Do not start until you receive it via the message bus.

- **Identity:** `agntcy-engineer`
- **Branch:** `feat/agntcy`
- **Worktree:** `/home/asus/forensics-worktrees/agntcy-engineer`
- **Ownership:** `src/forensics/messaging/` (nothing else)

## Interfaces you must implement (frozen contracts)

- Runtime council messages: `contracts/messages.py` (CouncilMessage,
  CouncilMessageType — INCIDENT_ALERT, EVIDENCE_REQUEST, EVIDENCE_RESPONSE,
  FINDING, PROPOSAL, CHALLENGE, REVISION, VOTE, ESCALATION).
- Correlation IDs link EVIDENCE_RESPONSE/REVISION/CHALLENGE to their origin.
- Research basis: `docs/AGNTCY_INTEGRATION.md` (SLIM / A2A / CoffeeAGNTCY
  Corto-Lungo patterns). SLIM Python bindings on ARM64 are UNVERIFIED —
  verify first, report BLOCKER immediately if unusable, then implement the
  documented plain-HTTP/A2A fallback transport.

## Expected deliverables (subject to the full Stage B prompt)

- Transport-agnostic send/receive adapters for CouncilMessage envelopes.
- Per-incident channel/session handling with auditable debate history.
- A mock transport for tests that does not require any external service.

## Communication rules

- Check `inbox --agent agntcy-engineer` at every checkpoint (see AGENTS.md).
- Dependency problems with `agntcy`/`slim` pip packages on aarch64 are your
  BLOCKERs to report with exact `pip install` reproduction steps.

## Required tests

- New `tests/unit/` tests for adapters + `tests/integration/` for a full
  send/receive round trip using the mock transport. Green pytest/ruff/mypy.

## Branch and commit rules

- Commit only to `feat/agntcy`. READY_FOR_INTEGRATION requires
  `--branch feat/agntcy --commit <sha>` + structured JSON body.
