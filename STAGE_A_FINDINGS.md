# Stage A Findings & Progress Report

**Project:** Cyber Incident Response Council — Forensics / Investigation Agent
**Date:** 2026-10-10
**Status:** PARTIAL — Environment audit, model research, and AGNTCY research are complete and verified. The repository foundation, contracts, communication system, tests, worktrees, and commits have **not** been built yet (work had not started when this report was requested).

---

## 1. What was actually done (verified steps)

1. Ran hardware and OS inspection commands (`uname`, `lscpu`, `free -h`, `df`, `nvidia-smi`, `ss -tlnp`, `ip -brief addr`).
2. Ran software inspection commands (Python, pip, Git, Docker, CUDA toolkit, sqlite3, pip package listing).
3. Probed running model servers (`ollama` on :11434, `llama-server` on :8000) with non-destructive HTTP GETs.
4. Fetched and analyzed the three candidate models from Hugging Face (page + API metadata, file listings).
5. Fetched AGNTCY GitHub organization and CoffeeAGNTCY repository documentation.
6. Extracted text from the two hackathon PDFs in this repo (track statement + hacker guide) with `pdftotext`.

All findings below come **only** from commands that were actually executed — nothing is assumed.

---

## 2. Environment audit findings (verified)

### Hardware — IMPORTANT: this is a GB10, not a GB300

| Item | Verified value |
|---|---|
| Machine | **NVIDIA GB10 / DGX Spark-class** (ASUS Ascent GX10 — confirmed as the required Local AI track hardware from the track statement PDF) |
| Architecture | **aarch64 (ARM64)**, 20 CPU cores (Cortex-X925 + A725) |
| GPU | NVIDIA GB10, driver **580.142**, CUDA **13.0**, unified memory |
| RAM | 121 GiB total (~43 GiB used, ~78 GiB available) |
| Disk | 916 GB NVMe, **607 GB free** |
| OS | Ubuntu 24.04.4 LTS, kernel 6.17.0-1014-nvidia |

**Implication for our plan:** any x86-only wheel or CUDA-build assumption is invalid. Standard PyPI aarch64 PyTorch wheels are CPU-only; GPU torch on GB10 needs NVIDIA-provided builds. vLLM support on GB10 is unverified and unlikely to work out of the box.

### Active GPU workloads — must not be disturbed

- `ollama` (PID 86296): **24.2 GB** GPU memory.
- `llama-server` (PID 89752, llama.cpp): **12.2 GB** GPU memory, serving **`fdtn-ai/Foundation-Sec-8B-Instruct`** (GGUF, 8.03B params, ~8.5 GB, 128K context) on an **OpenAI-compatible API at `http://127.0.0.1:8000/v1`** — one of our fallback models is *already running*.
- ollama also has: `gemma4:26b`, `nemotron-3-super` (123.6B), `nemotron3:33b`, `qwen3.6:35b` (all Q4_K_M GGUF).

### Software

| Item | Status |
|---|---|
| Python | 3.12.3 (system), `venv` available, pip 24.0 |
| ML/AI Python packages (torch, transformers, vllm, fastapi, pydantic, agntcy) | **NOT installed** anywhere (system or user site-packages) |
| Git | 2.43.0, worktree support present |
| Docker | 29.2.1 installed but **permission denied** for this user (no docker group) — containers effectively unusable without sudo |
| CUDA toolkit | nvcc 13.0 present |
| sqlite3 | 3.45.1 CLI available (good for the SQLite coordination bus) |
| Network | Wi-Fi 169.233.72.113, Tailscale iface, SSH on :22, ollama :11434, llama-server :8000, DGX dashboard :11000 |
| Sibling projects | `/home/asus/compliance-agent` and `/home/asus/containment-agent` (teammates' components, not git repos — do not touch); plan is to create `/home/asus/forensics-agent` following the same convention |

---

## 3. Model research findings (verified from Hugging Face)

### Primary: `alirezaaminzadeh/soc-analyst-tool-use` — viable, small, with caveats

- **Base:** Qwen2.5-1.5B-Instruct, `Qwen2ForCausalLM`, 1.54B params, BF16.
- **Repo contains BOTH:** a full merged `model.safetensors` (3.09 GB — loads directly with transformers, no base model needed) **and** a `adapter/` PEFT QLoRA adapter (`adapter_config.json` + `adapter_model.safetensors`).
- **Tool calling:** Qwen2.5 chat template using `unsloth` XML conventions; specifically fine-tuned for SOC tool use.
- **License:** Apache-2.0. Context window inherits Qwen2.5 (~32K). ~3–4 GB footprint — trivially fits alongside existing workloads.
- **Blocker/risks:** community fine-tune with only 144 downloads and no eval data; tool-call reliability unverified. **Not vLLM-compatible as-is** (fine-tuned template + tiny model; vLLM on aarch64 unverified anyway). A functional test is required before trusting either the merged weights or the adapter.

### Fallback 1: `fdtn-ai/Foundation-Sec-8B-Instruct` — already running on this machine

- Llama-3.1-8B fine-tuned with 5B security tokens by Foundation AI (Cisco). 8.03B params, BF16 safetensors (~16 GB) + GGUF already on the llama.cpp server at :8000.
- **No native tool-calling in its chat template** — tool calls would need prompt-engineering/JSON-mode, not native OpenAI tool-call API.
- License: "other" (Foundation AI license, Llama-derivative — check terms before redistribution).

### Fallback 2: `Qwen/Qwen3-8B`

- Apache-2.0, native tool calling in template, hybrid reasoning. Solid general fallback but not security-specialized; GGUF available for llama.cpp serving.

### Recommended inference architecture (documented recommendation, not yet implemented)

1. **Primary:** `soc-analyst-tool-use` via a **Transformers backend** (merged safetensors) with a Qwen2.5 tool-call parser adapter isolated from investigation logic.
2. **Fallback:** the already-running llama.cpp OpenAI-compatible server (`fdtn-ai/Foundation-Sec-8B-Instruct` on :8000) — zero new GPU cost, but no native tool calls.
3. Wrap both behind an abstract inference backend (`generate` / `generate_structured` / `health_check` / `get_model_metadata`) with mock-first testing.

---

## 4. AGNTCY research findings (verified from GitHub/docs)

- AGNTCY is a Linux Foundation project ("Internet of Agents"). Key components: **SLIM** (Secure Low-Latency Interactive Messaging, Rust with Python bindings), **DIR** (Agent Directory — discovery/registration), **Identity** (verifiable credentials), **OASF** (schema framework), **Observe SDK**, **SHADI**.
- **CoffeeAGNTCY** (`agntcy/coffeeAgntcy`, Python, Apache-2.0) is the official reference app:
  - **Corto** — minimal two-agent setup: A2A messaging over SLIM transport, LangGraph orchestration. Best starting pattern for our forensics agent.
  - **Lungo** — advanced MAS: pub/sub A2A over NATS or group communication over SLIM, streaming, MCP tool integration, observability, identity. Matches our multi-agent council debate topology.
  - Pinned versions: App SDK v0.5.5, SLIM v1.4.0, A2A v0.3.20, LangGraph v1.2.11.
- `agntcy/agntcy-contrib` does **not exist** (404) — the real repos are `agntcy/slim`, `agntcy/slim-bindings`, `agntcy/app-sdk`, `agntcy/coffeeAgntcy`, `agntcy/dir`.
- **Not yet verified:** whether the SLIM Python package installs/works on aarch64 Linux + Python 3.12. This is the main remaining AGNTCY risk. **No AGNTCY packages are currently installed.**

**Recommended topology (planned, not built):** forensics agent joins a SLIM channel per incident; council messages (`INCIDENT_ALERT`, `FINDING`, `CHALLENGE`, `VOTE`, etc.) as A2A payloads with correlation IDs; LangGraph-driven rounds; DIR/Identity optional for Stage B; plain-HTTP fallback if SLIM proves unusable on GB10.

---

## 5. Bonus context from the track PDFs (extracted with pdftotext)

- Our team is in the **ASUS Local AI Track**: projects **must run locally on the ASUS Ascent GX10** (NVIDIA GB10, 128 GB unified memory) — this machine is exactly that hardware, resolving the "expected GB300" discrepancy: GB10 is correct for the track.
- Judging: 3-min pitch + 3-min Q&A starting 2:00 PM Sunday; Devpost submissions due 1:30 PM Sunday; borrowed hardware must be returned by 3:45 PM Sunday.

---

## 6. Remaining Stage A work (not yet started)

1. Create `/home/asus/forensics-agent` repo + `pyproject.toml` + venv (pydantic, pytest, ruff, mypy).
2. Implement and freeze the shared Pydantic contracts (incident, evidence, messages, investigation, inference, tools).
3. Build the SQLite coding-agent message bus (`coordination/` package, stdlib-only) at `/home/asus/forensics-agent-coordination/coordination.db` (outside worktrees), with WAL + busy timeout, 7 registered agent identities, CLI (`python -m coordination.cli`), and tests.
4. Two-process cross-worktree smoke test of the message bus.
5. Docs: `ENVIRONMENT_AUDIT.md`, `MODEL_RESEARCH.md`, `AGNTCY_INTEGRATION.md`, `CODING_AGENT_COMMUNICATION.md`, `ARCHITECTURE.md`, `CONTRACTS.md`, `OWNERSHIP.md`, `STAGE_B_HANDOFF.md`.
6. Six Stage B branches + worktrees from the validated foundation commit (3 logical commits total).

---

*Generated after live inspection of the machine. Every value above was produced by an executed command or a fetched upstream page; nothing is assumed.*

