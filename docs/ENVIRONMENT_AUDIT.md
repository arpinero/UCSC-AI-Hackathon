# Environment Audit (verified 2026-10-10)

All values below were produced by commands actually executed on the machine.
This machine is the ASUS Local AI track hardware; the track statement requires
projects to run on the ASUS Ascent GX10, which is this machine.

## Hardware

| Item | Value |
|---|---|
| Machine | ASUS Ascent GX10 (NVIDIA DGX Spark class, **GB10 Grace Blackwell**) — NOT GB300 |
| Architecture | aarch64 (ARM64), 20 CPU cores (Cortex-X925 + A725) |
| GPU | NVIDIA GB10, driver 580.142, CUDA 13.0, unified memory |
| RAM | 121 GiB total; ~78 GiB available at audit time |
| Disk | 916 GB NVMe (ext4), 607 GB free |
| OS | Ubuntu 24.04.4 LTS, kernel 6.17.0-1014-nvidia |

## Running GPU workloads (DO NOT DISTURB)

| Process | PID | GPU memory |
|---|---|---|
| `ollama` (port 11434) | 86296 | 24.2 GB |
| `llama-server` (llama.cpp, port 8000, OpenAI-compatible `/v1`) | 89752 | 12.2 GB |

The llama-server already serves `fdtn-ai/Foundation-Sec-8B-Instruct`
(GGUF, 8.03B params, 128K context). Ollama holds: gemma4:26b,
nemotron-3-super (123.6B), nemotron3:33b, qwen3.6:35b.

## Software

| Item | Status |
|---|---|
| Python | 3.12.3 system; project-local `.venv` with pydantic/pytest/ruff/mypy |
| Git | 2.43.0 with worktree support |
| Docker | 29.2.1 installed, **permission denied** for this user (no sudo assumed) |
| CUDA toolkit | nvcc 13.0 |
| SQLite | 3.45.1 (WAL verified working on local ext4) |
| torch / transformers / vLLM / AGNTCY | **Not installed** anywhere on the machine |
| Network | Wi-Fi 169.233.72.113; SSH :22; ollama :11434; llama-server :8000; DGX dashboard :11000 |

## Constraints and implications

1. **ARM64**: standard PyPI wheels for torch are CPU-only on this platform;
   GPU builds must come from NVIDIA's GB10-specific distributions. vLLM on
   GB10 is unverified and must not be assumed.
2. **Docker unusable** for this user → no containerized SLIM deployment;
   plan for native Python processes.
3. ~36 GB of GPU memory is already committed by teammates' model servers;
   our Stage B model budget must stay small (the 1.5B SOC model fits).
4. Everything else (RAM, disk, SQLite on local ext4) is comfortably sufficient.
