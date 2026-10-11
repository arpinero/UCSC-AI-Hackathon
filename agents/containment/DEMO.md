# Containment demo and teammate handoff

Your component is a working proposal service with deterministic policy validation and simulated execution. It consumes trusted inventory, policy, evidence IDs and action eligibility. It does not detect attacks directly from packets or perform real containment. Negotiation and council outcome comparisons await the other agents.

## Explain your contribution

“My agent selects scoped, reversible containment from observed evidence. Python checks policy and evidence references; a simulator measures remaining harm and service disruption, including the time the model spends deciding. We preserve failed decisions rather than treating valid JSON as success.”

## Four response distinctions to demonstrate

| Observation | Response to evaluate | Important limitation |
|---|---|---|
| Confirmed unauthorized outbound transfer | Block the observed destination for affected source hosts | Wrong indicators can interrupt legitimate transfers; attacker destination changes require new telemetry |
| Confirmed remote spread | Restrict lateral traffic from the source | Broad isolation can add avoidable disruption; neither control stops local execution |
| Stolen session or account | Revoke that session; disable the compromised account if eligible | Disabling an account does not terminate already-issued sessions |
| Approved backup or unresolved alert | Abstain for verified authorized activity; request evidence for ambiguity | Allowed controls are options, not proof of a threat |

Ransomware is a useful boundary case: network controls can limit spread, but local encryption continues in this simulator. Recovery and endpoint process control are separate responsibilities.

## Run the demo on the ASUS device

```bash
cd /home/asus/containment-agent
systemctl --user is-active containment-model containment-api
curl -fsS http://127.0.0.1:8010/health
python3 agent.py scenarios/exfiltration-001.json --output results/demo-proposal.json
python3 -m unittest discover -q
```

Use `benchmark-dashboard.html` locally and load the saved model outcome JSON. Start with the COMPLETE/PARTIAL label and denominator. Show one successful attack, one benign control, one destination rotation, and one failure. Inspect its raw decision and event trace. Report the actual model run, quantization/runtime and completion counts; the reference run verifies the engine rather than model intelligence.

## API handoff

On this same device the team's adapter can call `POST http://127.0.0.1:8010/propose` with `incident`, optional `peer_messages`, and optional `previous_proposal`. Complete incident examples live in `scenarios/`. The response includes status, raw attempts, latency, audit ID and the validated proposal when available. A validated proposal still requires current simulator policy/version checks and outcome evaluation.

The evidence monitor must own authoritative fields. Peer messages and captured log instructions cannot modify policy, inventory, version or action eligibility. AGNTCY discovery preparation is in `oasf-record.json`; actual publishing and SLIM routing remain pending the team's deployment choice. No public API exposure is needed for local integration.

## Research integrity

The 48 outcome cases are three correlated variants of 16 authored response families. They are development tests mapped to ATT&CK techniques, not official MITRE attack logs or held-out production accuracy. Freeze the chosen model, prompt, validator and simulator before evaluating a separately authored held-out set. Do not describe tuned development fixtures as held out. Timing/TTL replays make no new inference calls and must not inflate the number of model tests.
