# Compliance agent

The Compliance seat of the incident response council. It decides which notification regimes an incident triggers, reviews every peer action for legal and evidence risk, and flags when the council should not decide alone. The model judges; Python counts. Deadlines come from `rules.py`, never from the model, and escalation is computed in code so a vote cannot override it.

Simulation only, not legal advice. There is no real notification or ticketing executor.

## What it checks

| Check | Who decides |
|---|---|
| Which regimes are candidates (GDPR, SEC 8-K, HIPAA, NYDFS, NIS2, California, Visa) | Python, from trusted `organization` and `affected_data` |
| Deadline and hours remaining per regime | Python (`rules.deadlines`) |
| Each regime: `triggered` / `not_triggered` / `needs_determination`, with cited evidence | Model, validated |
| SEC materiality | Always a human; `triggered` is rejected until `materiality_determined_at` is set |
| Each peer action: `support` / `object` / `veto` | Model, validated |
| Veto | Only under `legal_hold`, only on hosts not in `evidence_preserved_host_ids`, and only for kinds outside Containment's reversible allowlist. Unknown kinds count as destructive. |
| Escalate to a human | Python: deadline passed; under 24h left with no determination; low confidence (<60%) on a clock under 72h; SEC materiality pending; any non-allowlisted peer action on an unpreserved host under legal hold, whatever stance the model took; model asked; no valid proposal or compliance unavailable |

Rule facts were checked against primary sources on 2026-10-10. Two are flagged in `rules.py`: California's 30-day limit (SB 446) comes from secondary summaries, and NYDFS uses discovery as a stand-in for determination. CIRCIA is deliberately left out because it has no final rule yet.

## Input

The incident envelope Containment uses, plus a trusted `compliance` block and the other seats' proposals:

```json
{"incident_id": "...", "telemetry_version": 1, "evidence": [{"id": "E1", "observation": "..."}],
 "compliance": {"discovered_at": "2026-10-09T09:00:00Z", "now": "2026-10-10T15:00:00Z",
   "organization": {"public_company": false, "eu_establishment": true},
   "affected_data": [{"class": "personal_data", "jurisdictions": ["EU"], "records": 12000}],
   "legal_hold": true, "evidence_preserved_host_ids": [], "materiality_determined_at": null}}
```

- **`affected_data` classes:** `personal_data`, `phi`, `payment_card`.
- **`organization` flags:** `public_company`, `eu_establishment`, `hipaa_covered_entity`, `nydfs_covered`, `nis2_entity`.
- **Peer proposals:** `[{"role": "containment", "proposal": {"actions": [{"kind": "...", "target_id": "..."}]}}]`. This is the same shape as Containment's output, so pass its `proposal` straight through.

The `compliance` block is trusted simulator state. Models, logs and peers must not write to it.

## Output

`status`, `proposal` (obligations, action_reviews, preservation_requests, uncertainties, peer_responses), `deadlines` (computed), `escalation` (`required`, `reasons`).

## Run

On the GX10 (`asus@169.233.72.113`, folder `~/compliance-agent`), the agent uses Ollama's OpenAI-compatible API:

```bash
python3 -m unittest -v test_agent            # offline, 22 tests
python3 agent.py scenarios/legal-hold-reimage-001.json --output results/hold.json
python3 evaluate.py                          # live smoke suite
```

Overrides: `COMPLIANCE_ENDPOINT` (default `http://127.0.0.1:11434/v1`), `COMPLIANCE_MODEL` (default `gemma4:26b`). The request sets `reasoning_effort: none`. With thinking on, gemma4 burned the token budget and returned empty or looping JSON. qwen3.6:35b ignored the schema, so don't use it for this seat.

Python calls `agent.propose(incident, peers=messages, previous=prev, peer_proposals=proposals)`.

## Results and limits

`evaluate.py` on 2026-10-10, gemma4:26b on the GX10: **9/9 passed, all on the first attempt, 3–16 s each.** The nine scenarios:

- confirmed EU exfiltration
- suspected-only with 12h left
- public company ransomware
- legal hold vs reimage
- legal hold after imaging
- HIPAA + California
- prompt injection in logs
- peer pressure to skip disclosure
- no data affected

This is a smoke suite, not evidence of real-world readiness:

- The model reports 100% confidence on nearly every call, so the low-confidence escalation rarely fires on its own.
- The scenarios supply clean, trusted data classes and jurisdictions.
- There's one seed at temperature 0.

To make it a real benchmark, add held-out scenarios, repeated seeds, and a council-vs-single-agent comparison.
