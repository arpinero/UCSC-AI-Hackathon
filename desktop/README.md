# Sentinel web workspace

Browser-first incident response UI on branch `desktop-ui`, based on `council` commit `b2dc838`. Run activity comes from the actual council protocol. All incidents and execution remain simulated. Demo mode uses deterministic seats; live mode calls the configured model services. There is no automatic live-to-demo fallback.

## Open locally

Node 22.12+ and Python 3.10+ are required. From the repository root:

```bash
npm --prefix desktop ci
npm --prefix desktop run build
python -m desktop.bridge --port 8787
```

Open **http://127.0.0.1:8787**. This single server serves the built UI and API. A small prebuilt `web-build` is committed for hackathon deployment, so teammates can run the Python server immediately without installing Node. Rebuild after frontend edits. `npm --prefix desktop start -- --port 8787` is an equivalent launcher after building. For UI development, start the Python bridge and run `npm --prefix desktop run dev`; Vite on port 5173 proxies the API.

## ASUS / team access

Use an isolated checkout of `desktop-ui`; do not change a teammate's working branch. Build the frontend as above. Run the bridge on the pipeline host using the same `COUNCIL_*` environment settings as the team's live pipeline:

```bash
COUNCIL_MODEL=gemma4:26b python3 -m desktop.bridge --port 8787 \
  --origin https://YOUR-8787.usw3.devtunnels.ms
```

Privately forward **8787** through the authenticated VS Code tunnel, then open that forwarded HTTPS address. Replace the model name with an actually installed model and the origin with the exact forwarded address. Keep forwarding private. Node is needed only to build; the built web app can be served with standard-library Python.

Live role configuration follows `council/seats.py`: `COUNCIL_MODEL_ENDPOINT`, `COUNCIL_MODEL`, `COUNCIL_CONTAINMENT_URL`, `COUNCIL_COMPLIANCE_URL`, optional `COUNCIL_FORENSICS_URL`, `COUNCIL_FIXING_ENDPOINT`, `COUNCIL_FIXING_MODEL`. Defaults are inherited from the pipeline. Check **Models & services** before choosing Live. Reachability and model identity are reported separately. Ollama's loaded model list is displayed when available.

## What works

- Incident selector with 57 existing composite fixtures; investigation history and search.
- Incremental real agent call events, responses, objections/vetoes and final votes. Evidence and outcome views render recorded data rather than invented statistics.
- Human checkpoint after unanimous plan acceptance and before simulated containment/recovery. Approve or reject requires a written reason and the current approval ID. Stale, duplicate and expired decisions fail closed. Approval never overrides binding compliance escalation.
- Incident chat: contextual deterministic summaries in Demo; read-only model answers with evidence-ID validation in Live. Chat text cannot execute or approve plans.
- JSON report export. Append-only event journals and council reports under `reports/desktop`; interrupted runs remain visible after server restart and are not silently resumed.
- Polling every 900 ms while an investigation is open. Service health refreshed every 30 seconds.

The bridge binds to loopback. JSON mutations require a server token and an allowed browser origin; no wildcard CORS is enabled. Evidence is rendered as text. One active pipeline run is allowed to protect the shared GPU.

## Integration boundaries

The existing council starts Containment and a Recovery intent, then Forensics and Compliance. The UI shows that real order; it does not invent a compliance-first execution sequence. Production notification ingestion and automatic detection are not present in the council branch. Starting an investigation currently selects a simulated fixture. Team incident ingestion can be added against an authenticated schema once its contract is defined.

The only changes to `council/protocol.py` are optional observer and approval callbacks, plus telemetry-update events. Existing CLI behavior is unchanged when callbacks are omitted. Event types: `incident`, `incident_updated`, `agent_started`, `agent_finished`, `agent_failed`, `message`, `approval_requested`, `human_decision`, `approval_expired`, `chat`, `completed`, `error`.

API: `GET /api/health`, `/api/cases`, `/api/models`, `/api/runs`, `/api/runs/{id}?after={event_count}`. `POST /api/runs` takes `case_id` and `mode`. `POST /api/runs/{id}/decision` takes `approval_id`, `decision` (`approve`/`reject`) and `reason`. Chat takes `message` at `/api/runs/{id}/chat`. Get the CSRF token from health and send it in `X-Sentinel-CSRF` on mutations.

The preserved llama.cpp source and reused components are documented in `upstream/PROVENANCE.md`. Electron shell files are retained for later packaging; the supported workflow for this handoff is the browser app.

## Validation

```bash
python -m unittest council.test_pipeline desktop.test_bridge -q
npm --prefix desktop run check
npm --prefix desktop run build
npm --prefix desktop test
```

Approval tests exercise actual pipeline blocking, rejection, timeout, duplicate/stale decision handling, unchanged binding escalation and ordered incremental events. Live-model correctness is the pipeline team's responsibility; a working web Demo does not claim all live services are ready.
