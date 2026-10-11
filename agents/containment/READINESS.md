# Containment handoff

Ready for hackathon integration as a proposal-only containment component. Use the qualified API client; negotiation and shared AGNTCY routing are pending team integration.

## Latest measured results

- Qwen3.6:35b (Ollama Q4_K_M), v3: **44/48 overall** across 16 response families and three seeds. All threat-outcome checks passed; four failures were excess isolation/service disruption.
- Authorized activity: **20/20** correct no-action responses. Challenge suite: **6/6**. These are developer-authored synthetic scenarios, not independent certification.
- Response latency: median **33.947 seconds**, p95 **48.788 seconds**, maximum **56.266 seconds** on the shared GB10.
- **65 unit tests passed on laptop and device**. **1,600 simulator property cases passed**; these do not measure model accuracy.
- Four availability misses: lateral_smb seed29, combined_paths seed29, credential_dump seed43, malicious_powershell seed43. Threat containment succeeded, but scope was broader than the privileged reference.

MITRE ATT&CK supplies technique mappings and provenance, not a turnkey attack dataset. Simulated telemetry and outcome physics are authored here. Results do not establish real-world detection accuracy, production readiness, or multi-agent superiority. Local ransomware execution is not stopped merely by network isolation.

## Team integration

Folder on ASUS: `/home/asus/containment-agent`. Git folder: `agents/containment` on branch `containment`.

The selected profile is `containment-api-qwen.conf`, installed as a user-service drop-in for `containment-api`. Service listens on **127.0.0.1:8010** on the ASUS machine.

```python
from containment_client import propose
result = propose(incident, peer_messages=[], previous_proposal=None)
if result['status'] == 'validated':
    proposal = result['proposal']
```

Run from the containment directory or include it in Python's module path. CLI:

```bash
python3 containment_client.py scenarios/exfiltration-001.json --output results/team-proposal.json
```

HTTP: `POST /propose` with JSON `{"incident": incident, "peer_messages": [], "previous_proposal": null}`. Follow `scenarios/exfiltration-001.json` for inventory, evidence, policy and telemetry schema. `GET /health` reports model readiness. The client rejects transport errors, stale/policy-invalid proposals and an unexpected model. No direct model fallback.

Six supported controls: isolate_host, block_egress, restrict_lateral, revoke_session, disable_account, request_evidence. Proposals carry evidence references, scope, expiry and rollback. Nothing here executes real containment changes. A trusted simulator/executor must recheck current state before applying a proposal.

Direct `agent.py` defaults retain the Foundation-Sec baseline; use `containment_client.py` for this qualified handoff. OASF record is schema-validated but has not been published; SLIM integration remains pending. Remote laptop clients need an authenticated tunnel or team transport; localhost is intentionally not public.

## Evidence

Full outcome and authorized-activity JSON/Markdown are in `research/raw`. Earlier model runs and frozen sources are preserved separately. Smoke results are checkpointed and should be reported only for completed cases, never assumed complete.
