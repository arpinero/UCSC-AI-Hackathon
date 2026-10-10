# Containment outcome benchmark

This benchmark tests response planning and simulated containment outcomes after trusted observations arrive. It does not measure discovery of attacks from raw network traffic, real firewall efficacy, or production incident response accuracy. MITRE ATT&CK supplies the technique taxonomy; observations, attack rates, dependencies, events and thresholds are authored here.

## Coverage and execution

48 reproducible cases: 16 families across seeds 17, 29 and 43. Families include exfiltration, SMB/RDP spread, remote-service exploitation, ransomware, credential dumping, malicious PowerShell, stolen sessions, compromised accounts, authorized backups, ambiguous alerts, critical services, protected destinations, combined paths, destination rotation and identity dependencies. The ten individual MITRE technique mappings use the already pinned `mitre-provenance.json`.

Incident, asset and evidence IDs are opaque. Only the incident is sent to inference: family, truth, event schedule, scores, reference controls and dependencies remain with the evaluator. Asset/evidence ordering, IDs, rates and timings vary by seed. Seed 29 inserts attacker instruction text into a log. These are development fixtures; variants of the same template are correlated and not independent real-world attacks. Reusing them for prompt improvement invalidates any held-out claim.

`Simulator` advances along exact event/expiry boundaries. It models outbound byte flows; source-to-peer and peer-to-peer infection paths; identity abuse; local file damage; explicit service dependencies; evidence-channel gaps; TTL expiry; renewal; rollback; and telemetry-version/policy changes. Already-issued sessions survive account disable. Isolation and lateral restriction do not terminate local ransomware. Only current-state validated proposals affect controls. Policy/eligibility changes revalidate active controls and remove controls that lost authority.

Actual measured inference time, including correction attempts, advances the simulated clock before controls apply. A telemetry update can invalidate an in-flight proposal. Destination rotation supplies new observations and triggers a second inference. No sleeps simulate the attack horizon: the event engine computes consequences deterministically. No attacks, firewall changes, or malware execute on the ASUS host.

## Scoring, baselines and limits

Each case runs three counterfactuals: no response, immediate fixture reference, and fixture reference at the same response times as the model. The reference is a privileged scripted plan, not another agent or a proven global optimum. It provides a transparent expected comparison under simulator assumptions.

A case passes only when responses validate and apply, policy rejections/false-positive disruption/evidence gaps are zero, ambiguity receives an evidence request, threat outcomes are at least as good as the latency-matched reference, service disruption does not exceed that reference, and every response arrives within 120 seconds. The 120-second deadline is a predeclared benchmark target, not an industry standard. Instant-reference losses expose latency harm even when the matched-reference comparison passes.

Reports retain separate dimensions rather than hiding tradeoffs inside an arbitrary weighted score:

| Measure | Interpretation |
|---|---|
| Bytes lost / prevented | Simulated data transfer before or outside controls; compares with no response |
| Additional hosts compromised / prevented | Reachable spread events; initial infected host excluded |
| Identity abuse events | Issued-session and new-login paths distinguished |
| Local files damaged | Residual ransomware damage that network controls cannot prevent |
| Service disruption seconds | Sum across explicit affected services; overlapping controls do not double-count a service |
| Evidence gap seconds | Host isolation lacking collector preservation; other forensic losses are not modeled |
| Benign false-positive incidence | Fraction of authorized cases receiving disruptive controls |
| p50 / p95 / maximum latency | Measured end-to-end inference, including corrections; machine/team load can confound comparison |
| Policy rejections / response failures / corrections | Safe failures still reduce successful response coverage |

Each result includes original raw model attempts, simulation traces, controls and every baseline outcome. Reports explicitly label partial runs. Atomic resumable checkpoints refuse changed model settings, datasets, or source hashes. A descriptive Wilson interval is stored with an explicit correlation caveat; do not present it as a population accuracy interval.

## Reproduce

```bash
python3 -m unittest discover -q
# Engine/fixture consistency only: NO MODEL INFERENCE.
python3 outcome_benchmark.py --mode reference --output results/outcome-reference.json
# Actual Foundation inference and simulated effects:
python3 outcome_benchmark.py --resume --output results/outcome-foundation-v2.json
# Actual Qwen comparison:
python3 outcome_benchmark.py --resume --model qwen3.6:35b \
  --endpoint http://127.0.0.1:11434/api --reasoning-effort none \
  --max-tokens 6000 --output results/outcome-qwen-v2.json
```

On the device, `containment-outcomes.service` runs `run-outcomes.sh`. It waits for the existing regression service to finish, then runs the models sequentially. It resumes checkpoints after a reboot. Logs are `logs/outcome-*.log`; raw results and generated tables are `results/outcome-*.json` and `.md`. Unit/reference tests prove engine/fixture consistency; only `mode=model` results establish measured model performance. Completed reference verification is 48/48; model outcome scores must be read from actual completed runs.

## Development findings and revision v2

The first real Foundation outcome run was stopped with 3/7 completed cases passing out of 48 planned, and preserved as `outcome-foundation.json`. SMB, RDP, remote exploitation and ransomware cases blocked spread but selected both lateral restriction and host isolation, causing avoidable simulated service disruption. The old smoke suite separately found duplicate evidence requests in an attacker-log case. These failures motivated an explicit scoped-control preference, a validator rejection of redundant isolation/lateral pairs, and a decoder action-count cap based on legal candidates. Benchmark scoring and fixture truth were not relaxed. Revised model runs use `outcome-foundation-v2.json` and `outcome-qwen-v2.json`; never resume the old checkpoint with revised inference code.

The previous regression configuration completed Foundation 21/21 MITRE, 6/6 challenge and 7/8 smoke; Qwen 21/21, 6/6 and 8/8 respectively. These observations precede v2 and are not v2 regression scores. The current source has 53 passing unit tests. A full v2 outcome report must be read from actual run files, not inferred from the reference or partial development run.

`benchmark-dashboard.html` opens locally without dependencies. Load one or more outcome JSON files to inspect partial/full status, family scores, counterfactual losses, latency and raw traces. Reference mode is prominently labeled as having no model inference.

## Judge-facing claim

Use: “We evaluated containment planning on 48 synthetic ATT&CK-mapped scenarios spanning 16 response families, with simulated outcome measurement, latency costs and benign controls.” State actual completed counts, model/version, failures and assumptions. Avoid “MITRE certified,” “perfect detection,” “production accuracy,” or “council superiority.” A full council comparison is deferred until teammates have working agents.

## AGNTCY boundary

The existing `/propose` API and incident/telemetry-version/action contract are independently ready for an adapter. Actual discovery uses AGNTCY Directory/OASF records; messaging uses SLIM. Those are separate from simulator development. Directory/server identity, credentials, naming and routing must match the team's chosen deployment; publishing guessed endpoints would not create working integration. No team resources were changed and no AGNTCY integration is claimed. Once that deployment is known, a transport adapter should invoke the existing proposal function without admitting peer/model text into authoritative incident fields.

Independent discovery preparation is complete: `oasf-record.json` passed validation against the downloaded official record JSON Schema. `oasf-validation.json` records the schema/record hashes; `research/oasf-record-schema.json` freezes the validation schema. The record uses the catalog's Security Incident Response skill (100703), states simulation-only behavior, and supplies a source locator. It advertises neither an invented public service URL nor working SLIM transport. Publishing it and configuring SLIM remain pending the team's directory/routing choice.

Sources: https://attack.mitre.org/resources/attack-data-and-tools/ ; https://attack.mitre.org/techniques/T1486/ ; https://docs.agntcy.org/

## Timing and expiry sensitivity

`sensitivity_benchmark.py` replays saved model proposals without making new inference calls. It requires matching dataset/source hashes and exactly reproduced observed effects before perturbation. It varies response delay (0, 30, 120, 240 seconds) and control lifetime (1 or 3 minutes), preserving original evidence and telemetry versions. Late stale responses are rejected. Short-lived controls are not automatically renewed. These are correlated counterfactuals, not extra model trials or estimates of how the model would replan. Six additional replay tests bring local validation to 59 tests.

```bash
python3 sensitivity_benchmark.py results/outcome-foundation-v2.json --output results/sensitivity-foundation-v2.json
```

## Explicit-contract revision v3

The v2 Foundation run also produced unsupported containment for approved backup and ambiguous proxy samples. The OpenAI-compatible adapter supplied the JSON schema to the decoder, but did not explicitly put its field contract in the prompt; the native Qwen adapter did. A development probe adds the incident-bound schema and concise field meanings to Foundation's prompt. This is a hypothesis about the integration, not proof that the backend is defective. The revised adapter supplies that guidance to both backends. Old failures remain in their original files. New runs use `outcome-foundation-v3.json` and `outcome-qwen-v3.json`. The diagnostic uses failed development cases and is not held out. Concurrent diagnostic calls also affected v2 machine load; its latency cannot be called an isolated runtime comparison.

For current reproduction, use the commands above with `-v3.json` output filenames. Never resume a v2 checkpoint with revised inference code. Timing replays likewise require the exact source used for their input run; archived v2 replay results were produced before changing that source.
