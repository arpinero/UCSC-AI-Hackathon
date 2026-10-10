# Model Research (verified from Hugging Face, 2026-10-10)

## Primary: `alirezaaminzadeh/soc-analyst-tool-use` — Apache-2.0

- **Architecture:** Qwen2.5-1.5B-Instruct base (`Qwen2ForCausalLM`, qwen2),
  QLoRA fine-tune for SOC tool use.
- **Repo contents (verified via HF API):** BOTH a full merged
  `model.safetensors` (3.09 GB, 1.54B BF16 — loads with transformers alone)
  and `adapter/adapter_config.json` + `adapter/adapter_model.safetensors`
  (PEFT QLoRA adapter).
- **Tool calling:** Qwen2.5 chat template; `<tools>` JSON schema injection and
  `[[{"name":..., "arguments":...}]]` XML call convention.
- **Context:** inherits Qwen2.5-1.5B-Instruct (32K). **Memory:** ~3-4 GB —
  fits easily alongside the existing GPU workloads.
- **Risks:** 144 downloads, 0 likes, no published evals; merged weights and
  adapter are both present and may diverge; tool-call reliability UNVERIFIED.
  Not usable with vLLM out of the box, and vLLM on GB10 is unverified anyway.

## Fallback 1: `fdtn-ai/Foundation-Sec-8B-Instruct` — already running here

- Llama-3.1-8B + 5B security tokens (Foundation AI / Cisco). 8.03B BF16
  safetensors (~16 GB); GGUF already served by the llama.cpp server at
  `http://127.0.0.1:8000/v1` with 128K context.
- **No native tool-calling** in its chat template → tool calls must be
  prompt-engineered/JSON-parsed. License "other" (Llama derivative).
- Zero new GPU cost; the strongest security-specialized option we have.

## Fallback 2: `Qwen/Qwen3-8B` — Apache-2.0

- Native tool calling in template, hybrid reasoning, GGUF available. General
  purpose (not security-specialized). Good insurance if the SOC fine-tune
  proves unusable and Foundation-Sec's lack of tool calls hurts too much.

## Recommended inference architecture (documented; NOT implemented — Stage B)

1. **Primary:** Transformers backend loading the merged safetensors of the
   SOC model, with a Qwen2.5 tool-call parser isolated in the inference
   layer (`forensics.inference`), never inside investigation logic.
2. **Fallback:** llama.cpp OpenAI-compatible backend for Foundation-Sec-8B
   via prompt-engineered JSON tool calls (no native tool-call assumptions).
3. Both behind `InferenceBackend.generate / generate_structured /
   health_check / get_model_metadata` with the mock backend as the test double
   and a factory honoring `FORENSICS_INFERENCE_BACKEND`.
4. A functional gate test for the SOC model (tool-call reliability,
   structured output) must run before anyone depends on it.

No weights were downloaded and no model was deployed during Stage A.
