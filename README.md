# UCSC AI Hackathon: Sentinel and the Cyber Incident Response Council

A team of local AI agents investigates a simulated cyber incident, argues over a response, and stops to ask a human when it should not decide alone. **Sentinel** is the desktop app for it. Everything runs on one machine, the ASUS Ascent GX10, with no cloud calls, because incident evidence, customer personal data and legal deliberations should not leave the building.

Track: **Local AI (ASUS)**, UCSC AI Hackathon @ SF Tech Week, Oct 10-11, 2026. The deliverables and judging criteria we planned against are in [HACKATHON.md](HACKATHON.md).

> **Simulation only.** Incidents are synthetic (real procedure text, fake hosts and timestamps). No action touches a real host, and the compliance output is not legal advice. MITRE ATT&CK supplies the technique taxonomy only.

## What is in this repository

| Path | What it is |
|---|---|
| `desktop/` | **Sentinel**: Svelte web UI, Python bridge, and Electron packaging for the Linux arm64 app. See [desktop/README.md](desktop/README.md). |
| `council/` | The council protocol: fixed deliberation rounds, votes, escalation, severity, single-agent baseline and evaluation. Standard library only. See [council/README.md](council/README.md). |
| `agents/containment/` | Containment seat: proposes scoped, reversible controls; includes a network simulator and benchmarks. |
| `agents/compliance/` | Compliance seat: which notification regimes trigger, deadlines computed in code, vetoes under legal hold. |
| `fixing-agent/` | Recovery (fixing) seat: model setup, fixtures and restoration scorer. |
| `results/` | Council results: `council-live.*` (12 live cases) and `council-mock.*`. |
| `Hacker Guide - UCSC AI Hackathon.pdf` | The event guide. |
| `STAGE_A_FINDINGS.md` | Early environment audit and model research. |

The Forensics seat lives on its own branch (see [Branches](#branches)). The council reaches it through an optional adapter on port 8747.

## Set up and run

Requirements: Linux (the packaged app targets **arm64**, such as the GX10), Python 3.10+, and Node 22.12+ for building. The council and the bridge use only the Python standard library.

```bash
git clone https://github.com/arpinero/UCSC-AI-Hackathon.git
cd UCSC-AI-Hackathon
```

### 1. Fastest: browser, Demo mode (no models needed)

A built UI is committed, so Node is not required for this.

```bash
python3 -m desktop.bridge --port 8787
```

Open http://127.0.0.1:8787, choose an incident, and keep **Demo**. The seats are deterministic, the approval checkpoint is real, and nothing needs the network.

### 2. Build the Sentinel desktop app (Linux arm64)

Build on the GX10 itself so the bundled Python bridge is native. The first build downloads Electron and packaging tools, so it needs network access once.

```bash
desktop/scripts/build-exe.sh          # AppImage + .deb in desktop/release/
desktop/scripts/build-exe.sh dir      # unpacked app only (fastest)
```

This runs `npm ci`, the frontend build, PyInstaller and electron-builder. The packages are **not stored in git**: the AppImage is over GitHub's 100 MB file limit, so rebuild them with the command above (a few minutes on the GX10 once dependencies are downloaded).

Run the result:

```bash
sudo apt install ./desktop/release/sentinel-web_0.1.0_arm64.deb && /opt/Sentinel/sentinel
# or, portable:
APPIMAGE_EXTRACT_AND_RUN=1 ./desktop/release/Sentinel-0.1.0-arm64.AppImage
```

`APPIMAGE_EXTRACT_AND_RUN=1` is needed only when `libfuse2` is missing, as on the GX10 image. The app starts its own bridge on a free loopback port and stops it when you close the window. The `.deb` is the better choice when Chromium's process sandbox matters. Details and limits are in [desktop/README.md](desktop/README.md).

### Quick start on the GX10 (after building)

```bash
desktop/scripts/install-shortcut.sh   # once: adds a Sentinel icon to the desktop, app menu and dock
desktop/scripts/sentinel-live.sh      # launches the app configured for the local live services
```

`sentinel-live.sh` sets `COUNCIL_MODEL=gemma4:26b`, `COUNCIL_FORENSICS_URL=http://127.0.0.1:8747` and a label for the Forensics model, and respects any value you already exported. The Forensics service does not report its own model, so Sentinel shows the configured label and marks it "Configured label, not reported by the service". The desktop icon runs the same script. After rebuilding, the launcher prefers `desktop/release/next/` over `desktop/release/`.

### 3. Live mode (real models on the GX10)

Live mode makes real model calls. It needs these services running locally before you start an investigation:

| Service | Default address | How to start |
|---|---|---|
| Ollama (shared model, Recovery and votes) | `http://127.0.0.1:11434` | `ollama serve`, with the model pulled. Default `gemma4:26b`, set with `COUNCIL_MODEL`. |
| Containment API | `http://127.0.0.1:8010` | `cd agents/containment && python3 api.py` (needs its own model server, see its README) |
| Compliance API | `http://127.0.0.1:8020` | `cd agents/compliance && python3 server.py` |
| Forensics API (optional) | `http://127.0.0.1:8747` | from the `forensics` branch; set `COUNCIL_FORENSICS_URL` |
| Recovery model (optional) | `http://127.0.0.1:8001/v1` | set `COUNCIL_FIXING_ENDPOINT` and `COUNCIL_FIXING_MODEL` |

Override any address with `COUNCIL_CONTAINMENT_URL`, `COUNCIL_COMPLIANCE_URL`, `COUNCIL_MODEL_ENDPOINT` and the variables above. Check **Models & services** in Sentinel before choosing Live. The packaged app passes its environment to the bridge, so set the variables before launching it. A live investigation takes a few minutes, and there is no automatic fallback to Demo. Weights are not in git. Each agent README explains how its model is downloaded and served.

### 4. Tests

```bash
python3 -m unittest council.test_pipeline desktop.test_bridge -q   # 40 tests
npm --prefix desktop ci && npm --prefix desktop test               # 18 tests
npm --prefix desktop run check                                    # Svelte type check
```

Council without the UI: `python3 -m council.run --list`, then `python3 -m council.run --case mitre-T1041`. `python3 -m council.evaluate --mode mock` compares the council with a single-pass baseline.

## How the council works

1. Containment and Recovery propose first, then Forensics and Compliance. This is the real order, not a staged one.
2. Seats object, veto or revise in a fixed number of rounds, and new telemetry can arrive mid-deliberation.
3. Compliance escalation is computed in code, so a vote cannot override it. Deadlines come from verified rules, never from the model.
4. A unanimous plan still pauses for a **written human decision** before any simulated action. Stale, duplicate and expired approvals fail closed.
5. Consensus is not always the right outcome. The council can stop, keep the disagreement, or hand the case to a human.

58 composite cases back the evaluation (57 evaluated, plus the `mitre-T1498-001` DDoS demo case in `council/ddos.py`). Results compare the council with a single-pass baseline on the same cases (see `results/council-live.md` and the limits listed there). The baseline is not an equal-compute experiment, so we do not claim superiority beyond what those files show.

## Branches

All work was done on Oct 10-11, 2026. **`main` now contains everything below except the two items marked as not merged.** Feature branches are kept for history; they are fully contained in `main` unless noted.

| Branch | Owner area | What it holds | In `main`? |
|---|---|---|---|
| `main` | Everyone | Integrated tree: council, three seats, Sentinel app and packaging | n/a |
| `desktop-ui` | Sentinel UI | Web UI, bridge, human-approval checkpoint, incident chat, live ASUS verification notes | Yes |
| `council` | Council pipeline | Protocol, baseline, evaluation, live-mode fixes, 12-case live run | Yes |
| `council-compliance-sync` | Council | Sends the debate transcript to Compliance | Yes |
| `council-live-fixes` | Council | Live-mode robustness fixes | Yes |
| `compliance` | Compliance seat | Rules, validator, scenarios, ATT&CK and real-world suites, model sweep | Yes |
| `containment` | Containment seat | Proposal agent, simulator, benchmarks, research. **Last 2 commits not merged**: a qualified API client and the completed v3 model benchmarks | Partly |
| `apinero` | Recovery (fixing) seat | Fixing-agent model setup, fixtures and scorer | Yes |
| `forensics` | Forensics seat | Contracts, AGNTCY messaging, investigation loop, reporting. **Not merged**: it is a separate package with its own `pyproject.toml` and tests | No |
| `remove-asus-pdf` | Housekeeping | Early "Initial Pipeline" snapshot, branched to drop the confidential ASUS PDF from the tree | Yes |

The Forensics integration (`agents/forensics/` plus a council runtime adapter) was prepared in a local worktree branch, `integration/forensics-into-council`, which has **not been pushed**. Until it is, run Forensics from the `forensics` branch and point `COUNCIL_FORENSICS_URL` at it. Without it, the council uses its own draft evidence-correlation seat.

## Honest limits

- Scenarios and observations are synthetic, and fixtures are correlated, so results are not production attack-detection numbers.
- Live mode needs the model services above. The packaged app does not bundle model weights.
- Severity weights are uncalibrated demo policy, and citation coverage measures referenced IDs, not factual correctness.
- The packaged app has been exercised in Demo mode on the GX10. A live run from the packaged app and an offline-network check are not yet recorded in `desktop/verification.json`.

## Credits and licences

The Sentinel interface adapts the llama.cpp web UI (MIT); see `desktop/upstream/PROVENANCE.md`. MITRE ATT&CK is used for attribution of technique names. Model licences are listed in each agent's README. The ASUS track statement is confidential, so [HACKATHON.md](HACKATHON.md) summarises it rather than copying it.
