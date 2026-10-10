# Stage B Handoff

**Do not launch Stage B agents before the team reviews Stage A.**
This document explains exactly how to launch them when ready.

## Launching a coding agent (per workstream)

1. **Open the worktree** (VS Code: File > Open Folder, or a new window):

   | Agent | Worktree path |
   |---|---|
   | model-engineer | `/home/asus/forensics-worktrees/model-engineer` |
   | tools-engineer | `/home/asus/forensics-worktrees/tools-engineer` |
   | agntcy-engineer | `/home/asus/forensics-worktrees/agntcy-engineer` |
   | reasoning-engineer | `/home/asus/forensics-worktrees/reasoning-engineer` |
   | evaluation-engineer | `/home/asus/forensics-worktrees/evaluation-engineer` |
   | integration-qa | `/home/asus/forensics-worktrees/integration-qa` |

2. **Prompt the agent with its instruction file**
   (`coding-agents/0X_*.md` currently placeholders — replace with the full
   Stage B prompts supplied by the team) and tell it to read `AGENTS.md`
   first. All six agents may run concurrently in separate VS Code windows.

3. **Environment**: the shared venv works from every worktree:

   ```bash
   source /home/asus/forensics-agent/.venv/bin/activate   # or use absolute paths
   /home/asus/forensics-agent/.venv/bin/pytest
   /home/asus/forensics-agent/.venv/bin/ruff check .
   /home/asus/forensics-agent/.venv/bin/mypy
   ```

   The coordination bus needs no environment at all (stdlib-only):
   `python3 -m coordination.cli ...` from the worktree root.

4. **Message bus** (every agent, in every worktree, same DB):

   ```bash
   export FORENSICS_COORD_DB=/home/asus/forensics-agent-coordination/coordination.db
   python3 -m coordination.cli inbox --agent <identity>            # check mail
   python3 -m coordination.cli send --sender <identity> --recipient <id> \
       --type REQUEST --subject "..." --body "..."                  # ask for help
   python3 -m coordination.cli heartbeat --agent <identity> --note "working on X"
   ```

   Blockers: `--type BLOCKER` with the structured JSON body (see
   docs/CODING_AGENT_COMMUNICATION.md). Integration: `--type
   READY_FOR_INTEGRATION` with `--branch` and `--commit`.

5. **Foundation tests from any worktree**:
   `cd <worktree> && /home/asus/forensics-agent/.venv/bin/pytest`.

## Merge and validation loop (owned by integration-qa)

1. On READY_FOR_INTEGRATION: integration-qa runs the suite on the agent's
   branch, merges into `test/integration-qa` (or per-PR branches), runs the
   full suite, and broadcasts results. Failures go back as TEST_FAILURE to
   the responsible agent. Cross-cutting disputes go to `coordinator`.

## Foundation commit (all six branches originate here)

Recorded at handoff time in the final Stage A report; verify with:

```bash
cd /home/asus/forensics-agent && git log --oneline -3
git worktree list   # shows each worktree, branch, and commit
```
