# Ownership (Stage B workstreams)

All six worktrees live in `/home/asus/forensics-worktrees/<agent>/` and all
branches originate from the same foundation commit (see STAGE_B_HANDOFF.md).

| Identity | Branch | Worktree (absolute) | Owns |
|---|---|---|---|
| model-engineer | `feat/inference` | `/home/asus/forensics-worktrees/model-engineer` | `src/forensics/inference/` |
| tools-engineer | `feat/forensic-tools` | `/home/asus/forensics-worktrees/tools-engineer` | `src/forensics/tools/` |
| agntcy-engineer | `feat/agntcy` | `/home/asus/forensics-worktrees/agntcy-engineer` | `src/forensics/messaging/` |
| reasoning-engineer | `feat/reasoning` | `/home/asus/forensics-worktrees/reasoning-engineer` | `src/forensics/reasoning/` |
| evaluation-engineer | `feat/evaluation` | `/home/asus/forensics-worktrees/evaluation-engineer` | `simulations/`, evaluation tests |
| integration-qa | `test/integration-qa` | `/home/asus/forensics-worktrees/integration-qa` | `tests/integration/`, `tests/end_to_end/`, validation scripts |
| coordinator | (logical role) | — | contract approvals, merge arbitration |

## Rules

1. **File ownership.** Agents may not edit files owned by another agent
   without an approved REQUEST on the bus. `scripts/` and `pyproject.toml`
   are shared: REQUEST the coordinator first.
2. **Frozen contracts.** Nobody edits `contracts/` directly — only via the
   CONTRACT_CHANGE_REQUEST -> decision -> versioned-commit -> broadcast flow.
3. **Dependencies.** Need another component's API? Send a REQUEST. Do not
   build duplicate incompatible APIs inside your own directory.
4. **Conflicts.** Record competing proposals + rationale on the bus; the
   coordinator decides; no agent forces a breaking change alone.
5. **Handoffs.** READY_FOR_INTEGRATION must include branch, commit SHA,
   features, test commands, test results, known limitations.
6. **Source of truth.** Git commits + frozen contracts. Bus messages are
   coordination records, not code review.
