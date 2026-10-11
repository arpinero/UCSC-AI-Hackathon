# Sentinel web workspace

Browser-first incident response UI on branch `desktop-ui`, synced with `council` commit `e0312bd`. Run activity comes from the actual council protocol. All incidents and execution remain simulated. Demo mode uses deterministic seats; live mode calls the configured model services. There is no automatic live-to-demo fallback.

Sentinel uses a dark theme by default, with a saved light/dark preference. Agent outputs render sanitized Markdown, highlighted code and copyable JSON. Containment/recovery proposals, forensic timelines and policy reviews have separate presentations. Conversation, side panel and dialog scrollbars are hidden while scrolling remains available; the composer shares the conversation scroll area.

The UI uses llama.cpp's original floating sidebar, text input and light/dark theme, with the connected incident pipeline as its conversation adapter. The centered chat layout is retained; evidence, metrics and human decisions are added inside it. Source mapping and MIT attribution are in upstream/PROVENANCE.md.

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

## Linux arm64 executable (GX10)

Sentinel can be packaged as a single desktop app: Electron starts a frozen copy of the Python bridge on a free loopback port, waits for its health check, and opens the UI. Nothing else needs to be launched, and Demo mode works with no network.

Build on the GX10 itself so the Python bridge is native aarch64 (needs Node 22.12+, Python 3.10+ with `venv`, and network access the first time to download Electron and the packaging tools):

```bash
desktop/scripts/build-exe.sh        # AppImage + .deb in desktop/release
desktop/scripts/build-exe.sh dir    # unpacked app only: desktop/release/linux-arm64-unpacked/sentinel
```

The script runs `npm ci`, the frontend build, PyInstaller (`desktop/packaging/sentinel-server.spec`, which ships the teammate fixture and agent sources that `council/sources.py` loads by path), and electron-builder.

Run it:

```bash
sudo apt install ./desktop/release/sentinel-web_0.1.0_arm64.deb && /opt/Sentinel/sentinel   # installed; also in the app menu
./desktop/release/Sentinel-0.1.0-arm64.AppImage                           # portable
```

The GX10 image has no `libfuse2`; run the AppImage with `APPIMAGE_EXTRACT_AND_RUN=1` or install `libfuse2t64`. Incident history is stored under `~/.config/sentinel/reports`.

Things to know:

- **Live mode still needs the model services.** The executable does not bundle model weights. For Live, start Ollama and the Containment, Compliance and (optionally) Forensics services first, and set the same `COUNCIL_*` environment variables as for the bridge. The app passes its environment to the bridge.
- **Sandbox.** Chromium's process sandbox needs a root-owned setuid helper. The `.deb` installs it that way. The AppImage and unpacked build lack that, so their launcher starts Electron with `--no-sandbox`. Renderer isolation, the CSP and the IPC route allowlist still apply. Use the `.deb` when the sandbox matters.
- **Remote bridge.** `SENTINEL_USE_SAVED_CONNECTION=1 /opt/Sentinel/sentinel` reuses the bridge URL saved in Connection settings instead of starting a local one.
- Everything remains simulated; incidents and actions never touch real hosts.

## Validation

```bash
python -m unittest council.test_pipeline desktop.test_bridge -q
npm --prefix desktop run check
npm --prefix desktop run build
npm --prefix desktop test
```

Approval tests exercise actual pipeline blocking, rejection, timeout, duplicate/stale decision handling, unchanged binding escalation and ordered incremental events. Live-model correctness is the pipeline team's responsibility; a working web Demo does not claim all live services are ready.


### Interactive investigation controls

Click an agent stage under the incident title to inspect its latest recorded response. The agent viewer has tabs for all four roles and distinct follow-up questions; it reports a missing, failed, or in-progress response without inventing output. Each question fills the existing chat composer and requires Send before calling the model.

Evidence citations open the exact observation. Use the evidence filter to switch IDs or return to all evidence. Proposed controls expand to show host scope, preserved channels, expiry, rollback, and the original structured control. Missing fields remain explicitly unspecified.

Suggestions above the composer change with inference, evidence browsing, escalation, and approval. During a written decision they only navigate or cancel decision mode, so a chat prompt cannot overwrite the approval reason. Approval and compliance policy enforcement remain in the Python pipeline. New incidents always require an explicit Start click; these exploration controls never start model runs.
