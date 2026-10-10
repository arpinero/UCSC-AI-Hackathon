# Fixing agent (Aidan)

Restores files and system state after Compliance approves, and debates Compliance over details first. This folder currently holds the **model setup and test fixtures only**. The agent itself (proposal and debate logic) and the test runner are not written yet.

## Status

| Item | State |
|---|---|
| Model downloaded and served | Done |
| Synthetic MITRE-mapped fixtures and scorer | Done, 10 unit tests pass |
| Runner that sends fixtures to the model | Not started |
| Debate loop with Compliance | Not started |
| Results showing the model fixes systems correctly | None yet |

## Model

Cisco's `fdtn-ai/Foundation-Sec-8B-Reasoning`, Q8_0 GGUF from `fdtn-ai/Foundation-Sec-8B-Reasoning-Q8_0-GGUF`.

- File: `foundation-sec-8b-reasoning-q8_0.gguf`, 8,540,948,640 bytes.
- SHA-256: `cd21e8dbb0f3b66156c864e2c33b4edc390070a142e6fab82bc0f61fa157c5f4` (matches the Hugging Face listing).
- Licence: Llama 3.1 Community License, with Cisco's changes under Apache 2.0 (see the model's `NOTICE.md`).
- Served by llama.cpp's `llama-server` on `127.0.0.1:8001`, with `--ctx-size 32768 --parallel 2`. Containment uses port 8000 and its API uses 8010.
- The chat template is Cisco's own, saved as `chat-template.jinja`. It ends the prompt with `<think>`, so the server returns reasoning in `reasoning_content` and the answer in `content`.

The weights are not in git. Download them with:

```bash
HF_HOME="$PWD/model-cache" hf download \
  fdtn-ai/Foundation-Sec-8B-Reasoning-Q8_0-GGUF \
  foundation-sec-8b-reasoning-q8_0.gguf --local-dir /home/asus/fixing-agent/models
sha256sum /home/asus/fixing-agent/models/foundation-sec-8b-reasoning-q8_0.gguf
```

Start and check the server (set `FIXING_MODEL_DIR` if the weights are elsewhere):

```bash
bash serve-model.sh
curl -fsS http://127.0.0.1:8001/health
python3 smoke_test.py
```

On the GX10 the model ran at about 8 tokens per second while sharing the GPU with Containment's server and an Ollama model. Expect slow debate rounds when several models are loaded.

## Tests

```bash
python3 -m unittest -v test_fixing_scenarios
```

`fixing_specs.py` holds author-created data for seven ATT&CK techniques: T1053.005, T1547.001, T1543.003, T1136.001, T1505.003, T1490 and T1486. The IDs were checked against MITRE Enterprise ATT&CK 19.2, the same release Containment uses. MITRE supplies the taxonomy only. The observations, artifacts and expected answers are author-created, and nothing executes an attack.

`fixing_scenarios.py` builds 21 cases, three per technique:

- `approved`: Compliance has cleared restoration, so the agent must fix the real problem.
- `hold`: a legal hold is in place, so the agent must defer and change nothing.
- `authorized`: the activity is a verified legitimate change, so the agent must not touch it.

Expected answers are returned separately from the incident, so they never enter model context. The scorer fails missed fixes, removal of benign lookalikes, restoring from a contaminated backup (T1486 `file-payroll`), changing state during a hold, and deferring when approved.

## Known issue to resolve before relying on the model

One probe used schema-constrained JSON at temperature 0 with a legal hold in place. The model's reasoning concluded it should not restore, but its JSON verdict was `restore_now`. This is a single sample. Before building the debate loop, compare schema orderings (`reason` before `verdict`) and, if the contradiction persists, evaluate `qwen3.6:35b` as the fallback. Keep agent code model-agnostic so the swap is a config change.

## Limits

- The model card lists autonomous remediation without testing, autonomous security decisions without human review, and legal advice as out of scope. Compliance should own legal and deadline arguments. The Fixing agent should argue the technical side and validate against simulated state before declaring anything restored.
- The fixtures are a small development suite, not evidence of real-world readiness. Freeze them before creating a separate held-out set.
