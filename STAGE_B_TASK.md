# STAGE B TASK — tools-engineer

You are `tools-engineer`, one of six parallel coding agents building the
Forensics / Investigation Agent. Execute this task completely and autonomously.
Work ONLY in this worktree, on branch `feat/forensic-tools`. You own
`src/forensics/tools/` (and its tests).

## Ground rules (mandatory)

- Read first: `AGENTS.md`, `docs/OWNERSHIP.md`, `docs/CONTRACTS.md`,
  `contracts/tools.py`, `src/forensics/tools/base.py`, and `mock.py`.
- Python: `source /home/asus/forensics-agent/.venv/bin/activate`.
- Bus: `export FORENSICS_COORD_DB=/home/asus/forensics-agent-coordination/coordination.db`
  heartbeat on start; check inbox at every checkpoint.
- IMPORTANT COORDINATION: `evaluation-engineer` publishes the scenario /
  evidence-store format on the bus early (check
  `history --type BROADCAST` and `inbox`). If it has not arrived yet, start
  with the evidence-store LOADER interface design below, send a REQUEST to
  `evaluation-engineer`, poll your inbox every few minutes while working on
  format-independent parts, and adapt once the spec arrives.
- NEVER: push, modify `contracts/` (frozen), fabricate evidence, write to any
  real system, modify other agents' files, or read ground-truth data in the
  tools layer (that is evaluation's test-only area).
- All checks green before finishing: `pytest`, `ruff check .`, `mypy`.
  Never claim tests pass without running them.

## YOUR MISSION (owner: src/forensics/tools/)

### 1. Evidence store loader (adapt to evaluation-engineer's published format)
`evidence_store.py`: a read-only store over the scenario layout
(`simulations/scenarios/<id>/evidence/*.json`): load, validate every item
against `contracts.Evidence`, index by evidence_id/host/event_type/timestamp,
and expose lookup APIs for the tools. No ground-truth access. If the real
format differs from the assumption above, follow the published spec — it is
authoritative. Design for a constructor-injected root path so tests can use
fixtures.

### 2. The seven real tools (replace the mocks' behavior, keep their names)
Implement under `src/forensics/tools/impl/` (keep `mock.py` intact for tests):
- `search_logs`: query over log-like evidence (substring/field match,
  optional host_id and time range from SearchLogsArgs); every returned
  LogEntry carries the evidence_id it came from (provenance, never invented).
- `get_host_context` / `get_user_context`: aggregate host/user facts from
  the evidence store (services seen in logs, accounts seen, anomalies).
  Only report what the evidence actually contains.
- `lookup_mitre_technique`: small static mapping file you commit under
  `src/forensics/tools/data/mitre.json` covering the techniques used by
  evaluation's scenarios (Request the list from evaluation-engineer);
  unknown ids -> found=False, never guessed.
- `enrich_ip`: derive from evidence (internal ranges, IPs seen in C2-like
  flows) plus an explicit static reputation map file for the scenario IPs —
  document that this is synthetic enrichment, mark reputation source.
- `build_timeline`: merge the given evidence_ids into an ordered
  TimelineEvent list (timestamp asc), flag gaps.
- `submit_incident_report`: the ONLY writing tool — writes a report JSON
  artifact to a constructor-injected output directory (default
  `/home/asus/forensics-agent-coordination/reports/`, outside git);
  returns the report_id path.
- Register all seven in a `build_default_registry(...)` factory next to the
  mock one; keep `ForensicTool` semantics: validated args, timeouts,
  ToolInvocation audit records, read-only except the report tool.

### 3. Tests
Extend `tests/unit/test_tools.py` (or add `tests/unit/test_tools_impl.py`):
- Build a small fixture evidence set in tests (or REQUEST evaluation's
  fixtures once published — do not edit `simulations/`, that is evaluation's).
- Each tool: valid args, invalid args, empty-result paths, provenance
  correctness (returned evidence ids exist in the store), timeout behavior,
  audit records complete. search_logs time/host filtering; build_timeline
  ordering and gap flagging; report tool writes only to the injected dir.

## FINAL HANDOFF (mandatory)
1. Commit everything on `feat/forensic-tools`.
2. READY_FOR_INTEGRATION to `integration-qa` (--branch feat/forensic-tools
   --commit <SHA> --body '<JSON: implemented_features, test_commands,
   test_results, known_limitations>').
3. PROGRESS summary to `coordinator`, noting which evidence-store format
  version you implemented against.
