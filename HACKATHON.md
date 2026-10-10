# Hackathon deliverables and acceptance criteria

Each item is labeled by source. **Verified** means it was read on hackdev.org. **Secondhand** means it came from a teammate's pasted pitch and has not been checked against an official doc. **Ours** means the team chose it. Replace the secondhand items with the real rubric as soon as someone gets it (Discord, the Cisco/Outshift slides, or a mentor).

## Event (verified, hackdev.org, 2026-10-10)

- **What:** UCSC AI Hackathon, an SF Tech Week event run by hack.dev, UCSC GenAI and Baskin Engineering. UCSC Silicon Valley campus, Santa Clara.
- **When:** Sat Oct 10 to Sun Oct 11, 2026, a 24h build. The venue closes at 10 PM Saturday; Discord has the Sunday reopen time.
- **Teams:** 1 to 4 people.
- **Judging:** "Judging by partner engineers. Winners same day, done by 5pm." "Every team gets the floor to demo at the end."
- **Published criteria:** none. The site lists no judging criteria, demo length, submission format, or per-track prizes ($11K+ total).
- **Tracks:**
  - Cloud AI: agentic workflows, orchestration, multi-agent.
  - **Local AI (ours):** "Models on 128GB or less — DGX Spark, Strix Halo, your laptop. Pick this if latency, privacy, or working with no network is the point rather than a constraint."
  - Physical AI.
- **Sponsors:** Cisco, ASUS and AMD are the track sponsors. NVIDIA, n8n, Beeceptor, ElevenLabs and PerceptEye are community sponsors.
- **Hardware:** ASUS Ascent GX10 (GB10, 128GB unified memory), 28 units, limit 1 per person. Ours is `asus@169.233.72.113`.
- **Credits:** NVIDIA Brev $25 (redeem by Oct 12), ElevenLabs Creator 1 month, n8n Cloud Pro 1 month, Beeceptor $25. Don't post the codes.

## Cisco / AGNTCY challenge (secondhand, unverified)

The source is the pitch pasted into the team chat. Cisco/Outshift presented AGNTCY at the event (agntcy.org, github.com/agntcy), but we have not seen the level definitions in writing.

- **Level 1-2:** extend the coffeeAGNTCY demo (Lungo/Corto). Level 2 includes discovering agents through the AGNTCY Agent Directory.
- **Level 3:**
  - Agents with competing objectives reach decisions without a supervisor.
  - The team shows evidence that they decide better together than alone, using a baseline comparison.
  - "Consensus is not always correct": the system should know when not to decide.
- **Rubric categories mentioned:** "Innovation", "Learning and Evidence". No weights given.
- **Required:** say explicitly what you added versus what came from coffeeAGNTCY.
- **Open question:** whether Local-track teams are eligible for the Cisco challenge.

## Team deliverables (ours)

1. **Live demo:** the incident response council (Containment, Forensics, Compliance, and possibly Fixing) handles a simulated intrusion on the GX10. New information is injected mid-deliberation, and at least one case escalates to a human instead of being forced through by vote.
2. **Evidence slide:** council vs single-agent baseline on the same scenarios, with numbers.
3. **Architecture slide:** a fixed round protocol, models per seat, and what came from coffeeAGNTCY/AGNTCY vs what we built.
4. **Repo:** one folder per seat under `agents/`, each with a README, tests and an eval script.
5. **Honesty notes:** scenarios are simulated (real procedure text, fake hosts and timestamps), this is not legal advice, and MITRE ATT&CK attribution goes in the README.

## Compliance seat acceptance criteria (ours, `agents/compliance/`)

| # | Criterion | Check | Status 2026-10-10 |
|---|---|---|---|
| C1 | Every candidate regime gets triggered / not_triggered / needs_determination, with cited evidence | `validate_proposal` | done |
| C2 | Deadlines are computed in code from verified rules, never by the model | `rules.py` + unit tests | done |
| C3 | SEC materiality is always left to a human | validator + test | done |
| C4 | Vetoes only under legal hold, only on unpreserved hosts, and only for non-allowlisted (destructive or unknown) actions | validator + tests | done |
| C5 | Escalation is deterministic and doesn't depend on the model's stance (deadline passed or short, low confidence, legal-hold conflict, model unavailable or invalid) | `escalation()` + tests | done |
| C6 | Resists prompt injection in logs and peer pressure | `injection-001`, `peer-pressure-001` | pass |
| C7 | Smoke suite 9/9 | `evaluate.py` | pass (gemma4:26b) |
| C8 | Real-world suite: at least 90% scenario pass, 100% valid JSON | `realworld/evaluate.py` | gemma4:26b 96% |
| C9 | Under 30s per decision on the GX10 | eval latency | gemma4:26b about 23s mean |
| C10 | Model chosen by a measured sweep across families and optimized variants | `realworld/sweep.py` → `results/sweep/summary.md` | running |
| C11 | Accepts Aidan's ATT&CK/D3FEND scenarios plus the `compliance` block, with no code change | integration run | waiting on data |
| C12 | Plugs into the council transport (AGNTCY/SLIM or HTTP) | team protocol | not started |

## Still needed from organizers

- **Rubric:** the written judging rubric and weights, and whether there is a separate Cisco rubric.
- **Format:** demo length and format, and the submission method (Devpost? repo link?).
- **Eligibility:** whether Local-track teams can enter the Cisco/AGNTCY challenge.
- **Hardware:** the GX10 return time, and whether it can be reached remotely after 10 PM.
