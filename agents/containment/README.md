# Containment agent

Foundation-Sec-8B-Instruct proposes reversible containment controls for the hackathon simulator. The Python validator rejects unsupported actions before returning an accepted proposal. There is no real firewall, endpoint, account, or shell executor in this package.

## Device and inference

Remote folder: `/home/asus/containment-agent` on `asus@169.233.72.113`.
Model API: `http://127.0.0.1:8000/v1` on the remote device.
Proposal API: `http://127.0.0.1:8010` when `api.py` is running.

Runtime: existing CUDA-enabled llama.cpp on ARM64/GB10, with Cisco's own Q8_0 GGUF release of Foundation-Sec-8B-Instruct. Quantized model revision: `16deb1934d4b1d28769f7020c15ae018aa537d1f`. The model is aliased to the original Hugging Face model ID for client compatibility; the alias does not mean the weights are BF16. Context is 16,384 tokens per slot, two concurrent model slots, and two simultaneous proposal API requests. GPU memory is unified with CPU memory.

Connect from your laptop:

```powershell
ssh -L 8000:127.0.0.1:8000 -L 8010:127.0.0.1:8010 asus@169.233.72.113
```

Run on the device:

```bash
cd ~/containment-agent
curl -fsS http://127.0.0.1:8000/health
python3 agent.py scenarios/exfiltration-001.json --output results/proposal.json
python3 evaluate.py --output results/evaluation.json
python3 -m unittest -v test_agent
```

Model operations:

```bash
systemctl --user status containment-model containment-api
journalctl --user -u containment-model -n 50 --no-pager
systemctl --user stop containment-model containment-api
systemctl --user start containment-model containment-api
```

`finish-setup.sh` waits for the model file, installs the included user service definitions, starts both endpoints, waits for model health, and runs the tests and live smoke suite. User services are enabled for future user sessions; boot without a user login depends on the device's user-manager configuration. `serve-model.sh` is the foreground model launcher. Model and API services survive SSH disconnect while the user's manager remains running.

The initial BF16 weights and vLLM container downloads were stopped to prioritize startup with the installed runtime. Partial caches remain on the device. `serve-bf16.sh` is an optional alternative launcher, not the active deployment. It requires completing the container and original-weight downloads, verifying GPU compatibility, and stopping the Q8 service to free port 8000 first. NVIDIA CDI metadata was generated under `/var/run/cdi/containment-nvidia.yaml`; the active llama.cpp deployment does not use Docker.

The launcher explicitly applies `chat-template.jinja`, matching the original model's `<|system|>`, `<|user|>`, and `<|assistant|>` role delimiters. The GGUF's fallback chat format was unsuitable in the initial live test. The containment client always supplies its own system prompt.

To download the selected weights into a deployment folder:

```bash
python3 -m venv .venv
.venv/bin/pip install huggingface_hub==2.2.0
HF_HOME="$PWD/model-cache" .venv/bin/hf download \
  fdtn-ai/Foundation-Sec-8B-Instruct-Q8_0-GGUF \
  foundation-sec-8b-instruct-q8_0.gguf \
  --revision 16deb1934d4b1d28769f7020c15ae018aa537d1f --local-dir models
bash finish-setup.sh
```

## Team integration

Call `agent.propose(incident, peers=peer_messages, previous=previous_proposal)` from your AGNTCY message handler, or POST an envelope to `/propose`:

```json
{"incident": {"...": "complete scenario object"}, "peer_messages": [], "previous_proposal": null}
```

Example input objects are in `scenarios/`. The API writes input and raw model output to `results/audit/`. It returns `validated`, `rejected`, or `unavailable`; only `validated` includes an accepted proposal. A failed validation receives one correction attempt. The agent does not establish council consensus or register itself in the AGNTCY directory yet; those require the team's transport configuration and shared decision protocol.

Use `--peers peers.json --previous previous.json` in the CLI to evaluate an objection. `previous.json` contains only the proposal object, not the surrounding audit result. Peers supply observations, objections, and suggested tradeoffs; their messages cannot bypass the validator.

## Trust boundary

The evidence monitor and simulator policy builder must construct trusted `assets`, `policy`, and each evidence record's `actionable_for` list. These eligibility lists are deliberately explicit. Do not let a model, attacker-controlled log, or peer modify them. Eligibility means an action may be considered; it does not mean the action is required or optimal. Free-text observations and peer messages remain untrusted input.

The decoder compiles trusted eligibility into action/target alternatives and constrains IDs and syntax. The model chooses a subset and supplies reasons and uncertainties. Python rechecks target types, evidence eligibility, protected targets/channels, TTLs, duplicates, and telemetry version. Python replaces model rollback text with a canonical inverse operation and returns authoritative `asset_facts` alongside the proposal. These checks do not prove that a rationale is true or that a proposal contains every necessary action. The simulator must revalidate against its current state immediately before applying a council decision, and implement the actual preservation exceptions, rollback and expiration. Reject stale proposals after new telemetry arrives.

The API is unauthenticated and bound only to loopback. Use SSH forwarding for access. Do not expose it publicly without authentication. Audit files contain scenario data; avoid supplying real secrets.

## Evaluation limits

Run `python3 mitre_eval.py` for 21 author-created synthetic tests mapped to ten Enterprise ATT&CK techniques: ten confirmed attacks, ten verified authorized counterparts, and one multi-technique chain. It verifies technique IDs against official MITRE Enterprise ATT&CK 19.2 STIX and records source URL, source SHA256, STIX IDs and modification dates in `mitre-provenance.json`. Scoring expectations stay outside inference input. Authorized counterparts retain the same eligible disruptive controls, so grammar alone cannot make abstention pass. The suite never executes attacks or malware. MITRE supplies the taxonomy, not these observations, expected answers, certification, or endorsement.

Every evidence record must receive a `contain`, `investigate`, or `no_action` review. Python requires controls for the model's `contain` decisions and evidence requests for `investigate`; this makes omissions explicit but does not prove the decisions are correct. Evaluate attack coverage and authorized-activity false positives separately. A safe rejection is still an effectiveness failure. Do not interpret a finite synthetic pass rate as perfect inference. Freeze this development suite before creating a separate held-out test set; do not call prompt-tuned fixtures held-out.

`evaluate.py` checks eight small curated scenarios: exfiltration plus lateral movement, lateral spread, ambiguous backup activity, a malicious instruction inside evidence, a stolen session, absent evidence, a protected session, and a peer attempting to override policy. It records accepted actions, raw output, correction attempts, token usage, and elapsed time. This is a smoke suite, not evidence of real-world readiness or council superiority. The scenarios explicitly supply action eligibility, so results measure selection among allowed controls rather than raw telemetry interpretation.

Expand with realistic telemetry, changing evidence, protected infrastructure, mistaken indicators, account dependencies, alternative attacker paths, delays, and repeated seeds. Compare identical simulator scenarios for containment alone versus the actual council; include compromised hosts, bytes lost, downtime, preserved evidence, and decision latency. Freeze weights and prompts before a held-out evaluation.

## Outcome simulation and judge evidence

Read `BENCHMARK.md` for the new deterministic simulator and 48-case outcome benchmark. It measures simulated exfiltration, spread, identity abuse, downtime, residual local damage and inference latency, with no-response and fixture-reference counterfactuals. Run `outcome_benchmark.py` against the chosen model; inspect the generated JSON/Markdown or load JSON in `benchmark-dashboard.html`. Reference verification is separate from model results. The deployed `containment-outcomes` user service produces `results/outcome-foundation-v2.json`, then `results/outcome-qwen-v2.json`, and resumes compatible checkpoints after reboot. Preserved v1 failures remain separate.

`oasf-record.json` is a schema-validated directory record prepared independently of teammates. It is not published and does not establish working AGNTCY messaging. Council negotiation remains deferred until the other agents are ready.

## Sources

- [Cisco model card](https://huggingface.co/fdtn-ai/Foundation-Sec-8B-Instruct)
- [Cisco's own Q8 release](https://huggingface.co/fdtn-ai/Foundation-Sec-8B-Instruct-Q8_0-GGUF)
- [NVIDIA Spark serving instructions](https://build.nvidia.com/spark/vllm/instructions)
- [NVIDIA container release](https://docs.nvidia.com/deeplearning/frameworks/vllm-release-notes/rel-26-01.html)
- [vLLM structured outputs](https://docs.vllm.ai/en/v0.11.1/features/structured_outputs/)
