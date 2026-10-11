# Containment inference research notebook

Date: 2026-10-10. Project: UCSC Cyber Incident Response Council. Scope: one containment agent that proposes reversible simulator controls. Branch: [containment](https://github.com/arpinero/UCSC-AI-Hackathon/tree/containment).

## Research question and claims

Can a locally served model select evidence-supported containment controls while avoiding unnecessary disruption, preserving policy-required channels, and requesting review when policy prevents action? Compare a domain-specialized 8B model with a larger general model under the same incident contract and Python validator.

These experiments measure planning and control selection over synthetic incident summaries. They do not measure raw intrusion detection, actual firewall enforcement, forensic preservation, legal compliance, production readiness, or multi-agent superiority. No malware or attack commands are executed. A finite pass rate cannot establish perfect inference.

## Device and reproducibility

- Device actually verified: NVIDIA GB10, ARM64, approximately 121 GiB unified system memory; not GB300 and not 128 GiB of separate VRAM. DGX Spark OS 7.5.0, Python 3.12.3, NVIDIA driver 580.142, CUDA toolkit 13.0.
- Deployment directory: `/home/asus/containment-agent`. Separate source checkout: `/home/asus/containment-agent/repo`; shared team checkout remains separate.
- Foundation runtime: preinstalled CUDA llama.cpp version 8999, commit `b97ebdc98`; all 33 layers offloaded. Context 32,768 across two slots, 16,384 per slot. Observed early decode throughput around 27 tokens/second; concurrent workloads affect latency.
- Requested model: `fdtn-ai/Foundation-Sec-8B-Instruct`. Actual active weights: Cisco's `fdtn-ai/Foundation-Sec-8B-Instruct-Q8_0-GGUF`, revision `16deb1934d4b1d28769f7020c15ae018aa537d1f`, file `foundation-sec-8b-instruct-q8_0.gguf`. Quantized results cannot be assumed equivalent to original BF16.
- Original BF16 snapshot inspected: `aa13cb996e7fc700e7efd6b7367992f14cf349c0`. BF16/container downloads were stopped in favor of the installed CUDA runtime; partial caches remain. BF16 has not been evaluated here.
- Alternative: existing local Ollama `qwen3.6:35b`, reported 36.0B Q4_K_M, digest `07d35212591fc27746f0a317c975a6d68754fb38e9053d82e25f06057af28522`. Upstream model family: [Qwen3.6-35B-A3B](https://huggingface.co/Qwen/Qwen3.6-35B-A3B). Ollama quantization/package is distinct from upstream weights.
- Existing Ollama reported version 0.23.2. Native requests with `format` initially produced action/target pairs excluded by that schema. This is an observed integration limitation; the cause was not established. Native comparison was revised to include the incident-bound legal choices in prompt text as well as `format`, following [Ollama's recommendation to include schema text](https://docs.ollama.com/capabilities/structured-outputs). Python validation remains required. Do not infer an enforceable schema guarantee from a submitted `format` parameter.
- Foundation generation: temperature 0, output budget 2,200, one correction attempt, request timeout 240 seconds. Qwen native comparison: temperature 0, thinking disabled, output budget 6,000, context 16,384, same correction allowance and validator. These unequal budgets and different runtimes are confounds; results compare configured systems, not isolated architectures.
- API binds localhost 8010; Foundation model localhost 8000; existing Ollama localhost 11434. Services `containment-model` and `containment-api` use the user manager. Passwords are not stored in artifacts.

## MITRE source and dataset construction

[MITRE's official STIX data](https://attack.mitre.org/resources/attack-data-and-tools/) provides technique identifiers and names. Enterprise ATT&CK 19.2 source URL, downloaded-byte SHA256, STIX identifiers and modification dates are recorded in `mitre-provenance.json`. This is an author-created synthetic suite mapped to MITRE, not an official MITRE attack-log dataset or endorsed evaluation.

`mitre_eval.py` defines 21 cases: ten confirmed attacks, ten verified authorized counterparts with identical eligible control choices, and a two-technique chain. Techniques: T1041, T1071.001, T1021.002, T1021.001, T1210, T1486, T1003.001, T1059.001, T1550.004, T1078. `mitre-fixtures.json` materializes the inputs and expected alternatives for review. Expected scoring alternatives stay outside model messages.

Trusted telemetry eligibility is intentionally supplied in `actionable_for`; the model chooses among allowed controls. This makes the tests substantially easier than interpreting raw telemetry. Narrative summaries explicitly describe malicious or authorized activity. Case identifiers encode technique IDs and authorized variants, another potential cue. Future independent evaluation must use opaque IDs and realistic uncertain telemetry. The six additional cases in `challenge_eval.py` test mixed authorized/malicious evidence, protected C2, critical ransomware, simultaneous session/account compromise, malicious instructions inside evidence, and stale peer objections. These are fresh synthetic challenges, not an independent third-party test set. Once prompts are changed in response to a challenge failure, that case is development data.

## Scoring and audit protocol

A pass requires a validated complete response plus expected control coverage. Authorized cases require zero disruptive controls; an optional non-disruptive evidence request is permitted by scoring. Rejected/unavailable responses count as failures even if they avoid unsafe execution. The chain requires both egress and lateral controls. Challenge cases additionally forbid specific unnecessary or policy-prohibited controls. This action-based score does not grade every narrative claim.

Each result records model, incident ID, proposal, authoritative asset facts, raw attempts, errors, completion reason, token usage, timestamp and elapsed seconds. Incremental result files have `planned` counts; incomplete runs must not be described as full benchmarks. `verification.json` and `RESULTS.md` summarize completed runs when available. The source revision for each experiment is recorded there; later documentation commits do not change the inference experiment.

The early classification suites used no repeated seeds, confidence intervals, paired statistical tests, independent labeling, or production outcome measurements. Temperature zero does not guarantee identical results across runtimes or concurrent workloads. Preserve failed runs; do not cherry-pick successful retries. Results are development evidence for the hackathon. The later outcome simulator adds correlated seed variants and descriptive intervals; those are not population confidence estimates.

## Connectivity and checkpoint recovery

After reconnecting through the tunnel, the model startup journal confirmed 33/33 GPU layers after the reboot. A SHA256 computed from the actual installed GGUF file was `d0072df70235e92bd996d4efd2347b38c9db530ed83df21f6be3f8958a9832d0`, matching the previously retrieved Hugging Face file metadata.

The device became unreachable and rebooted around 14:58 PDT. SSH briefly returned at the same address, `169.233.72.113`, around 15:01 PDT. Both model/API user services were active after boot, verifying service recovery. `nohup` evaluator processes had stopped: nohupped jobs survive SSH loss, not device reboot. The saved policy-filtered checkpoints contained 11/11 Qwen MITRE cases and 8/8 Foundation MITRE cases, with Qwen challenge already complete at 6/6. These were partial benchmarks, not 21-case scores.

`--resume` preserves every recorded completed case, including failures, checks prefix/model/configuration compatibility, and runs only remaining cases. New checkpoints record inference and dataset hashes, use atomic replacement, and flush data. Older pre-manifest checkpoints are explicitly labeled as legacy resumes; configuration is supported by the dispatch history and `validation-regression.json` (70 identical valid-fixture request bodies across input-only hardening). A resumed run spans different uptime/load conditions, so aggregate latency is not a controlled hardware benchmark.

`run-evaluations.sh` and `containment-evaluations.service` provide boot-resumable evaluation after installation. Deployment was pending when SSH became unreachable a second time. Access was restored through VS Code Remote Tunnels using the organizer's `asus-machine` tunnel and user-completed Microsoft account authentication. The shell verified `asus@16RW`, `aarch64`, and approximately one hour uptime. After checking no evaluators were running, the containment checkout was pulled, all 34 unit tests passed on the device, and the evaluation service was enabled and verified running at 15:59:47 PDT. Both model/API services were active, and the API reported inference ready. The next observed checkpoints were Foundation MITRE 9/9 completed of 21 and Qwen MITRE 12/12 completed of 21; Qwen challenge remained complete at 6/6. These observations do not replace archived raw results or imply completed MITRE benchmarks. Tunnel persistence after reboot has not yet been verified.

## Failure history and resulting changes

| Observation | Interpretation | Change |
|---|---|---|
| Initial action fields shared unintended enum constraints | Implementation bug, not model quality | Deep-copy schema fields independently; regression test |
| GGUF fallback ChatML differed from original role delimiters | Serving mismatch | Explicit Foundation chat template |
| Critical web host described as noncritical / availability impact understated | Unsupported rationale despite plausible actions | Authoritative inventory recap, unknown-impact instruction; narrow contradiction regression |
| Evidence-request rollback suggested escalating to isolation | Unsafe free-text rollback | Python canonical inverse-only rollback; simulator executes neither model text nor arbitrary commands |
| Model missed lateral movement while stopping exfiltration | Incomplete threat coverage | Require explicit review of every evidence ID; benchmark checks both controls |
| Authorized RDP/service activity received disruptive controls | False positive; eligibility is not necessity | Explicit authorized-activity abstention; require a contain review supporting every disruptive control |
| Investigate review accompanied isolation | Validator semantic gap | Reject disruption supported only by investigate/no_action reviews |
| Protected target caused omission of eligible review request | Planning inconsistency | Explicitly permit non-disruptive eligible requests on protected assets |
| Qwen OpenAI-compatible output omitted schema fields | Backend integration failure | Native Ollama `format` schema and explicit contract in prompt; not scored as model inferiority |

Early Foundation smoke results were 7/8, with a safe rejection. Subsequent evidence-review development also exposed protected-session and stolen-session rejection failures. The preliminary MITRE run was deliberately stopped after three authorized-activity failures; its partial report is retained. Final comparative numbers belong in `RESULTS.md`, not inferred from this notebook.

## Trust and limitations

Assets, policy, eligibility and version originate with the trusted monitor/simulator. Free-text logs and peer suggestions cannot change those fields. Schema constraints and Python validate known IDs, target types, eligible evidence, protected targets, channels, TTL, duplicate actions and current supplied version. Python canonicalizes rollback and checks consistency between evidence reviews and controls. It cannot establish that supplied telemetry is true, that all required controls were selected, or that reasoning text is factual.

The simulator must revalidate live state and telemetry version immediately before applying a council decision, enforce preservation exceptions and expiry, and implement rollback. This agent does not execute containment against the ASUS host or any real network. AGNTCY directory registration, messaging and council consensus still require the team's shared transport and decision protocol. No evidence that the council beats individual agents exists yet.

## Reproduce and next experiments

```bash
python3 -m unittest discover -q
python3 evaluate.py --output results/smoke.json
python3 mitre_eval.py --output results/mitre-foundation.json
python3 challenge_eval.py --output results/challenge-foundation.json
python3 mitre_eval.py --endpoint http://127.0.0.1:11434/api \
  --model qwen3.6:35b --reasoning-effort none --max-tokens 6000 \
  --output results/mitre-qwen-native.json
python3 challenge_eval.py --endpoint http://127.0.0.1:11434/api \
  --model qwen3.6:35b --reasoning-effort none --max-tokens 6000 \
  --output results/challenge-qwen.json
```

Freeze model digests, prompts, code and scoring before the next held-out set. Add raw telemetry, ambiguous/conflicting observations, opaque IDs, stale/retracted evidence, policy changes, identity dependencies, alternative attacker paths and critical-service downtime costs. Compare independent containment, independent larger model, and the actual council on identical simulator seeds. Measure bytes lost, additional compromised hosts, downtime, preserved evidence, policy violations, false positives, latency and correction rate. Add a reviewer only if a paired experiment demonstrates useful improvement over its latency and complexity costs.

## Outcome simulator development

`BENCHMARK.md` describes 48 opaque-ID cases across 16 response families, modeled attack/control effects and counterfactual outcomes. Eligibility remains shared between benign and malicious counterparts; the model must choose among allowed controls. This exposes failures that the older technique/authorized ID cues could hide. The simulator measures real inference elapsed time as attack time, but the attacks, harm rates and service dependencies remain authored assumptions. Seeds vary IDs, ordering, rates and event schedules; they do not create independent real-world incidents.

Foundation v1 was stopped at 3/7 completed cases passing of 48 planned because redundant broad isolation caused unnecessary disruption. V2 was stopped at 24/30 passing after false positives on approved backups and ambiguous alerts, plus a combined-path failure. A three-case explicit-contract diagnostic improved the remote-exploit choice and avoided disruptive backup containment, but still blocked ambiguous traffic. The diagnostic is development data, not held out. V3 supplies the semantic JSON contract to both serving backends and prioritizes a full Qwen run. No v3 score is inferred from the old results or diagnostic.

The old regression configuration completed Foundation 21/21 MITRE, 6/6 challenge and 7/8 smoke; Qwen completed 21/21, 6/6 and 8/8. These are separate from outcome scores. Current source validation passes 59 tests locally and on the device. The deterministic engine also passed 1,600 generated property cases with zero model calls; that count must not inflate model sample size. Frozen-decision timing/TTL replays have their own explicit no-inference label and retain the original failed proposals. Exact v2 source is archived for reproducibility.

`oasf-record.json` passed official JSON Schema validation for independent AGNTCY discovery preparation. It is not published and does not establish working SLIM messaging. Council comparison remains deferred until the other roles are implemented.
