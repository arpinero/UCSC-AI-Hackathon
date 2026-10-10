# Stage B Workstream 06 — Integration & QA Engineer

> **STATUS: PLACEHOLDER.** The full Stage B prompt will be supplied after
> Stage A review. Do not start until you receive it via the message bus.

- **Identity:** `integration-qa`
- **Branch:** `test/integration-qa`
- **Worktree:** `/home/asus/forensics-worktrees/integration-qa`
- **Ownership:** `tests/integration/`, `tests/end_to_end/`, and validation
  scripts in `scripts/` (shared — coordinate via REQUEST before editing
  scripts another agent created)

## Responsibilities

- Own the merge/integration loop: when other agents send
  READY_FOR_INTEGRATION, verify their branches (pytest/ruff/mypy), merge into
  `test/integration-qa` or a staging branch, and run the full suite.
- Report failures to the responsible agent with `TEST_FAILURE` (include the
  failing component, reproduction, and suggested fix).
- Maintain `scripts/verify_foundation.sh`-style validation tooling.

## Interfaces you must respect (frozen contracts)

- All `contracts/` — you are the first line of defense that merged code still
  validates against v1 schemas.
- Coordination bus rules for READY_FOR_INTEGRATION processing.

## Expected deliverables (subject to the full Stage B prompt)

- End-to-end test: Incident -> investigation request -> findings -> debate
  position -> revision -> report, using mocks for all external services.
- Merge checklist and a passing full-suite run on the integrated branch.

## Communication rules

- Check `inbox --agent integration-qa` at every checkpoint (see AGENTS.md).
- You are the default recipient for READY_FOR_INTEGRATION messages.

## Branch and commit rules

- Commit only to `test/integration-qa`. Announce integrated, tested states
  via BROADCAST to all agents.
