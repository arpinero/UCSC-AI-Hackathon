# STAGE B TASK — evaluation-engineer

You are `evaluation-engineer`, one of six parallel coding agents building the
Forensics / Investigation Agent. Execute this task completely and autonomously.
Work ONLY in this worktree, on branch `feat/evaluation`.

## Ground rules (mandatory)

- Read first: `AGENTS.md`, `docs/OWNERSHIP.md`, `docs/CONTRACTS.md`, `contracts/`.
- Python: `source /home/asus/forensics-agent/.venv/bin/activate` (pytest/ruff/mypy).
- Bus: `export FORENSICS_COORD_DB=/home/asus/forensics-agent-coordination/coordination.db`
  - On start: `heartbeat --agent evaluation-engineer --note "started"`, check inbox.
  - After the format spec (below): `broadcast --sender evaluation-engineer --subject "scenario format published" --body "<short summary + path>"`.
  - On blockers: BLOCKER to coordinator (structured JSON body, see AGENTS.md).
- NEVER: push, deploy, modify `contracts/` (frozen), touch other agents' worktrees
  or `~compliance-agent`/`~containment-agent`, kill/reconfigure ollama (:11434)
  or llama-server (:8000), store secrets, fabricate evidence.
- All checks must pass before you finish: `pytest`, `ruff check .`, `mypy`.
  Never claim tests pass without running them.

## YOUR MISSION (owner: simulations/ + evaluation tests)

### Step 1 — IMMEDIATE: publish the shared scenario format
Design the synthetic evidence-store format and broadcast it on the bus in your
FIRST work session (other agents are waiting for it). Commit it as
`simulations/FORMAT.md` and send the BROADCAST message. Required layout:

    simulations/scenarios/<scenario_id>/
      incident.json            # validates against contracts.Incident
      evidence/evidence-NN.json  # each validates against contracts.Evidence
      ground_truth.json         # NOT read by the investigation flow

`evidence_id` convention: `EV-<scenario_id>-<NN>`, stable and unique. Include a
"reveal_round" integer field idea in FORMAT.md: evidence available in round N
(ground truth has it; the loader can reveal progressively for multi-round tests).

### Step 2 — three+ synthetic incidents (realistic, self-consistent)
1. Ransomware: execution + persistence + mass file encryption indicators.
2. Credential theft / lateral movement: phishing -> stolen creds -> SMB/SSH
   lateral movement to a second host.
3. Suspected data exfiltration WITH contradictory evidence: an initial
   evidence set suggesting exfiltration, plus a later-round evidence item
   (e.g., a backup job log) that should flip a SUPPORT stance to OPPOSE.
Each scenario: 8-15 evidence items across 2-3 hosts, timestamps forming a
reconstructable timeline, sources (syslog, zeek, edr, auth logs), and enough
signal for search_logs/build_timeline/enrich_ip/lookup tools to be useful.
Ground truth must distinguish "suspicious activity" vs "confirmed incident"
and, for scenario 3, record the correct final stance (OPPOSE containment).

### Step 3 — loader + injection + scoring (as importable code + CLI)
- `simulations/loader.py` (or a package): load + validate every file against
  the frozen contracts; fail loudly on invalid payloads.
- Evidence injection: `available_evidence(round)` — later-round evidence is
  hidden until its round (this is how "new evidence arrives" is simulated).
- `simulations/scoring.py`: score an investigation run against ground truth:
  citation validity (every cited_evidence_id exists), stance correctness,
  severity match, timeline anchor overlap (soft), position-change correctness
  (did the agent revise SUPPORT->OPPOSE when contradictory evidence arrived).
- `scripts/benchmark.py`: repeatable benchmark that runs a provided
  investigation callable against all scenarios and prints a metrics report
  (findings accuracy, stance accuracy, tool-call count, mean/max
  ToolInvocation.duration_ms). Make the investigation callable injectable so
  this works with the real reasoning engine after integration; for now ship a
  trivial baseline callable that reads ground truth ONLY through the scoring
  interface (never through the investigation path).

### Step 4 — tests
- Loader validates all committed scenarios; every fixture passes contracts.
- Scorer: a correct synthetic run scores 1.0; a run citing nonexistent
  evidence is flagged; scenario-3 revision is scored correctly.
- Ground-truth isolation test: assert the loader API used by investigators
  never returns ground_truth contents.

## FINAL HANDOFF (mandatory)
1. Commit everything on `feat/evaluation` with clear messages.
2. `python3 -m coordination.cli send --sender evaluation-engineer --recipient integration-qa \
   --type READY_FOR_INTEGRATION --branch feat/evaluation --commit <SHA> \
   --body '<JSON: implemented_features, test_commands, test_results, known_limitations>'`
3. Also send a PROGRESS summary to `coordinator`. If incomplete, still commit,
   run what you can, and document gaps in known_limitations honestly.
