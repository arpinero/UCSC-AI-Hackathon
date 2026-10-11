# Cyber Incident Response Council — baseline pipeline

Python 3.10+, standard library only. No UI, cloud telemetry, real attacks, firewall
changes, process termination, or file restoration. All action execution is **simulated**.
The existing teammate modules remain unchanged. Development branch: `council`.

## Run offline

Run from `/home/asus/UCSC-AI-Hackathon`:

```bash
cd /home/asus/UCSC-AI-Hackathon
python3 -m unittest council.test_pipeline -v
python3 -m council.run --list
python3 -m council.run --case mitre-T1041 --output /home/asus/UCSC-AI-Hackathon/reports
python3 -m council.run --case council-critical-impact --output /home/asus/UCSC-AI-Hackathon/reports
python3 -m council.evaluate --mode mock --output /home/asus/UCSC-AI-Hackathon/results/council-mock.json --reports /home/asus/UCSC-AI-Hackathon/reports
```

Reports are JSON + Markdown. Escalations also create a local JSON file in the
report directory's `alerts/` and print **HUMAN REQUIRED**. This is not email, paging,
external disclosure, or a monitored alert service. Save/share reports carefully:
live evidence and transcripts can contain sensitive data.

## What is integrated

- Kaylem: existing proposal validator, MITRE fixtures, network Simulator and seeded
  outcome cases. Its network controls cannot stop local ransomware execution.
- Soren: existing proposal validator, deadline calculator, binding vetoes and
  escalation function, ATT&CK compliance fixtures. Simplified rules are inherited
  unchanged and are **not legal advice** or independently revalidated statutes.
- Aidan: seven technique fixture specifications and deterministic restoration
  scorer. Draft Fixing logic lives in the council seat adapter, not his owned folder.
  Reason precedes verdict. Clean backups and benign-artifact protections are checked.
- Andrew: optional adapter to his committed investigation API (`:8747`), plus an
  explicitly draft in-pipeline evidence-correlation seat. His production reasoning
  engine is not claimed complete. The branch's 125 contract/integration/mock tests
  were run from a temporary archive without merging or modifying his files.

57 composite cases: 21 MITRE containment/compliance cases, 32 seeded network
outcome cases (including prompt-injection payloads and destination rotation),
and four dedicated safety acceptance cases. Original 21 Fixing fixtures remain
available in Aidan's own suite; composite cases reuse all seven technique specs,
not an assertion that every original suite was copied unchanged.

## Fixed protocol, no supervisor model

1. Containment independently proposes controls. Fixing proposes a **non-executing**
   restoration intent; this early intent enables real preservation disagreement.
2. Forensics reviews scope/preservation. Compliance reviews each proposed action.
3. Objections/vetoes enter the transcript. Scoped containment is re-proposed;
   simulated evidence capture has an explicit tool receipt. Under an unfinished
   legal hold, Fixing revises to defer instead of restoring.
4. Repeat at most three rounds. Forensics and Compliance must support; Containment
   and Fixing explicitly vote on the exact shared plan. **All four must support**.
5. Only an accepted plan reaches the Simulator. Recovery additionally requires
   preservation and approval. A contaminated backup stays unrestored and produces
   `CONTAINED_PARTIAL_RECOVERY`, not a false success claim.
6. New telemetry invalidates stale controls, enters the transcript, and requires a
   fresh consensus. Deadlock, unavailable/invalid seats and critical severity alert
   a human. There is no majority override or silent live-to-mock fallback.

The router applies pre-agreed gates; it is not an LLM supervisor. Mock policies
are hand-written vocabulary-based integration stubs. They demonstrate the wiring
and conflict protocol, **not genuine learned reasoning**. Live seats use role-specific
prompts, peers' proposals, and explicit final votes. Calls are sequential to avoid
shared GPU contention; they can later be scheduled concurrently after profiling.

Compliance receives host-normalized recovery targets because Soren's legal-hold
validator tracks preserved **host IDs**, whereas Aidan's actions target files and
artifacts. Reported restoration actions retain their original targets.

## Severity and escalation

The score is 0–100: confirmed compromise 10, exfiltration 15, sensitive data 10,
lateral spread 12, identity compromise 10, privileged identity 20, ransomware 25,
critical asset 15; host spread and record volume each contribute at most 10;
active clock pressure adds 10. Every contribution is reported.

Bands: LOW <25, MEDIUM 25–49, HIGH 50–74, CRITICAL ≥75. Default human threshold
is 75; `--threshold` is configurable. **These weights are uncalibrated demo policy.**
Synthetic impact flags are derived from fixture observations, not ground truth.
A future production ingestion layer must supply authenticated impact facts.

Binding Soren escalations remain binding regardless of numerical score: management
materiality determination, passed/urgent uncertain clocks, low-confidence urgent
calls, and explicit human requests. A legal-hold destructive intent can be negotiated
to a safe deferral **before execution**; an unresolved hold conflict escalates.
Do not weaken these gates merely to reduce alert counts.

## Live services / GX10 handoff

First run the teammate services against their **locally installed** model weights:

```bash
cd /home/asus/UCSC-AI-Hackathon/agents/containment
python3 api.py
# separate terminal
cd /home/asus/UCSC-AI-Hackathon/agents/compliance
python3 server.py
```

Follow their existing model-server READMEs; this pipeline does not download weights
or start/reconfigure another teammate's servers. Verify service health and installed
model names before running. The default council model is `gemma4:26b` (override with
`COUNCIL_MODEL` or `--model`). On the GX10 used for the last live runs, Containment's API ran
`qwen3.6:35b` and Compliance ran `gemma4:26b`, both through Ollama on :11434.

```bash
cd /home/asus/UCSC-AI-Hackathon
# Optional Aidan model; must actually be running on 8001:
export COUNCIL_FIXING_ENDPOINT=http://127.0.0.1:8001/v1
export COUNCIL_FIXING_MODEL=fdtn-ai/Foundation-Sec-8B-Reasoning
# Optional Andrew service with an injected, ready investigation engine:
# export COUNCIL_FORENSICS_URL=http://127.0.0.1:8747
python3 -m council.run --mode live --case mitre-T1041 --endpoint http://127.0.0.1:11434/api --model gemma4:26b --timeout 300
python3 -m council.evaluate --mode live --limit 6 --output /home/asus/UCSC-AI-Hackathon/results/council-live.json --timeout 300
```

Use `COUNCIL_CONTAINMENT_URL` and `COUNCIL_COMPLIANCE_URL` to change local agent
ports. URLs are loopback HTTP only; redirects are rejected. A local SSH tunnel
can support development, but the final local demo must run on the GX10 itself.
Native Ollama `/api` and OpenAI-compatible `/v1` inference are supported.

Andrew's adapter maps mutable fixture IDs to immutable content-addressed Evidence
IDs. Fixtures without event timestamps explicitly use simulated placeholders.
No factual chain-of-custody or real timestamp accuracy is claimed.

Optional `--cache-dir` caches model responses by prompt/model/endpoint; validation
still runs on cache hits. Do not mix cached replay latency with fresh performance.
`evaluate --resume` checks pipeline code, dataset and configuration hashes and
preserves failures. Service-side model/config changes require a **new output**:
the current checkpoint cannot attest remote service weight identity.

## Baseline interpretation

The single-pass baseline receives the same initial case, validators, severity policy,
and simulation settings, but has no peer negotiations or subsequent inference for
new telemetry. In live mode it makes one combined-model call. Mock mode uses a
single-pass policy, **not a measured single LLM**. This is not an equal-token or
equal-compute experiment. Freeze cases, add held-out cases, log every actual model
and weight identity, and measure fresh GX10 runs before making superiority claims.

Fixture scores evaluate proposals, not executed actions. Safe human escalation may
therefore fail a completion-oriented fixture. Partial escalated simulations are
excluded from full-horizon losses; compare outcomes only on shared completed cases.
Citation coverage measures referenced IDs, not forensic factual correctness.
Severity precision/recall is not reported without independent labeled cases.

MITRE ATT&CK supplies the taxonomy, not endorsement or these synthetic observations.
No UI or scalable production deployment is part of this baseline.