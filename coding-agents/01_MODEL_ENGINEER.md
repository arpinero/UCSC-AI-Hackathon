# Stage B Workstream 01 — Model Engineer

> **STATUS: PLACEHOLDER.** The full Stage B prompt will be supplied after
> Stage A review. Do not start until you receive it via the message bus.

- **Identity:** `model-engineer`
- **Branch:** `feat/inference`
- **Worktree:** `/home/asus/forensics-worktrees/model-engineer`
- **Ownership:** `src/forensics/inference/` (nothing else)

## Interfaces you must implement (frozen contracts)

- Abstract backend: `forensics.inference.base.InferenceBackend` —
  `generate`, `generate_structured`, `health_check`, `get_model_metadata`.
- Typed requests/results: `contracts/inference.py` (InferenceRequest,
  InferenceResult, StructuredGenerationRequest, ModelMetadata, ToolSpec,
  ToolCallRequest, FinishReason).
- Existing reference: `src/forensics/inference/mock.py` (MockInferenceBackend)
  — keep it passing; do not change its public behavior.

## Expected deliverables (subject to the full Stage B prompt)

- Transformers backend for `alirezaaminzadeh/soc-analyst-tool-use` (merged
  safetensors), with Qwen2.5 tool-call parsing isolated in an adapter module.
- llama.cpp/OpenAI-compatible fallback backend pointing at the EXISTING
  server on `http://127.0.0.1:8000/v1` (do not restart or reconfigure it).
- Backend factory honoring `FORENSICS_INFERENCE_BACKEND` (mock|transformers|llamacpp).

## Communication rules

- Check `inbox --agent model-engineer` at every checkpoint (see AGENTS.md).
- Contract problems: `CONTRACT_CHANGE_REQUEST` to `coordinator`.
- Report GPU/model blockers immediately via `BLOCKER`.

## Required tests

- Extend `tests/unit/test_inference.py` and add backend-specific tests.
- `pytest`, `ruff check .`, `mypy` must pass before READY_FOR_INTEGRATION.

## Branch and commit rules

- Commit only to `feat/inference` in your worktree. Small, logical commits.
- READY_FOR_INTEGRATION requires `--branch feat/inference --commit <sha>` and
  the structured JSON body defined in `docs/CODING_AGENT_COMMUNICATION.md`.
