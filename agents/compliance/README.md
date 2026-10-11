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

On the GX10 (address in team chat, not here: the repo is public; folder `~/compliance-agent`), the agent uses Ollama's OpenAI-compatible API:

```bash
python3 -m unittest -v test_agent            # offline, 26 tests
python3 agent.py scenarios/legal-hold-reimage-001.json --output results/hold.json
python3 evaluate.py                          # live smoke suite
cd realworld && python3 evaluate.py --suite attack --output results/attack.json   # 21 ATT&CK cases
```

The `attack` suite reuses Containment's 21 ATT&CK fixtures (`realworld/mitre-fixtures.json`, copied from the `containment` branch) and adds a compliance block to each: a fictional organization, the data at risk, and one evidence line on data impact. Containment's expected action is the peer proposal. Containment's actions are all reversible, so four confirmed cases add a Recovery peer proposing `reimage_host` under legal hold. Three of those should be vetoed and one should not, because the disk was already imaged. Authorized variants should come back not triggered. `realworld/test_attack.py` checks the cases offline.

Overrides: `COMPLIANCE_ENDPOINT` (default `http://127.0.0.1:11434/v1`), `COMPLIANCE_MODEL` (default `gemma4:26b`). The request sets `reasoning_effort: none`. With thinking on, gemma4 burned the token budget and returned empty or looping JSON. qwen3.6:35b ignored the schema, so don't use it for this seat.

Python calls `agent.propose(incident, peers=messages, previous=prev, peer_proposals=proposals)`.

## Calling it from the council

`python3 server.py` starts a loopback API on `127.0.0.1:8020` (`COMPLIANCE_PORT` to change). It works like Containment's `/propose` on :8010.

```bash
curl -s localhost:8020/health
curl -s -X POST localhost:8020/review -H 'Content-Type: application/json' \
  -d '{"incident": {...}, "peer_proposals": [{"role": "containment", "proposal": {"actions": [{"kind": "isolate_host", "target_id": "web-01"}]}}], "peer_messages": []}'
```

- `incident` is the same shape as in Input above, including the `compliance` block. Containment's `/propose` output can go straight into `peer_proposals` as `{"role": "containment", "proposal": <its output>}`.
- The response is the full result: `status`, `proposal` (obligations, action_reviews), `deadlines`, `escalation`. Read `escalation.required` first: if it's true, the council must not decide alone.
- `status` other than `validated` still returns 200, with `escalation.required: true` (fail closed). Bad input returns 400 with `{"error": ...}`.
- A call takes 20–100 s on the GX10 and can take up to about 8 minutes in the worst case (two attempts with a 240 s limit each). Set the client timeout to at least 600 s.

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

Final run on commit 7c9e58e, gemma4:26b on the GX10, one pass each:

- ATT&CK suite (MITRE technique scenarios, shared with Containment): **21/21**, all schema-valid on the first try, mean 9.3 s.
- Real-world suite (cases modeled on public breaches): **25/25**, all schema-valid on the first try, mean 11.6 s.

The earlier run on 63bcfff scored 20/21 and 24/25. The two misses were NIS2 ransomware (T1486) and a HIPAA case with an encrypted laptop. Both came from the rule text the model saw, not from a model change. The fix was to quote NIS2 Art. 23(3) and HIPAA 164.402 (the unsecured-PHI definition) in `rules.py`. Each quote is checked against a published copy of the law. No scenarios were edited to make them pass.

Model choice: a sweep of the same real-world cases over other local models kept gemma4:26b as the default (`COMPLIANCE_MODEL`). In the partial results, gemma4:26b had a 96% pass rate at 23 s. The QAT build tied it on accuracy but was slower (31 s). Every other model scored lower. Cisco's Foundation-Sec-8B and granite4.2:8b each scored 16%.

These suites are still limited:

- The model reports 100% confidence on nearly every call, so the low-confidence escalation rarely fires on its own.
- The scenarios supply clean, trusted data classes and jurisdictions.
- There's one seed at temperature 0.
- We wrote the suites ourselves while building the agent, so they are not held out. A perfect score shows the agent does what we designed it to do. It does not show that it generalizes.

To make it a real benchmark, add held-out scenarios, repeated seeds, and a council-vs-single-agent comparison.
