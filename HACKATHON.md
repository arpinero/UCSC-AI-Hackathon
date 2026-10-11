# Hackathon deliverables and acceptance criteria

Sources are the hack.dev portal documents (Hacker Guide, Track Challenges, ASUS Local AI Track, Prizes), read on 2026-10-10. Times can shift, and Discord has the latest. The ASUS document is marked confidential, so it is summarized here, not copied.

## Deadlines (Sunday, Oct 11)

| Time | What |
|---|---|
| 9:00 AM | Venue reopens. It closes at 10:00 PM Saturday, with no overnight stay. |
| **1:30 PM** | **Devpost submission due. Add our table number. Late submissions are not judged.** The link is on Discord. |
| **2:00 PM sharp** | **Judging: 3 min pitch + 3 min Q&A.** Stay at the table until judging is over. |
| 3:45 PM | All borrowed hardware back to the hardware desk, including the GX10, in the same condition. The Hacker Guide says return it after your judging; the ASUS doc says before closing. **If we make finals at 4:00, ask on Discord whether we can keep the GX10 for the re-pitch.** |
| 4:00 PM | Finals: top teams pitch again. |
| 5:15 PM | Awards. |

**Every team member must be able to explain how the project works. A team that can't will not be placed.**

## General judging (all tracks)

| Criterion | Question |
|---|---|
| Technical execution | Does it work? How hard was it to build, and how well is it built? |
| Creativity | Is the idea original, or a fresh take on a known problem? |
| Impact | Would people actually use this? Does it solve a real problem? |
| Demo and presentation | Can you clearly explain the problem, your solution and how it works? |

## Tracks: pick ONE for track prizes

Teams are up to 4 people. Each project enters one track. The PDFs don't list Devpost fields, a video, or a repo requirement; the Devpost items below are our own plan. Other prizes: Best Beginner, Best Use of ElevenLabs. Sponsor credit codes (ElevenLabs, Beeceptor, NVIDIA Brev, n8n) must not be posted publicly. Track prizes go only to teams that meet that track's requirements. The Overall Prize (4x MacBook Pro M4) is open to every team.

### Local AI, led by ASUS (our current pick)

- **Required:**
  - Build **and demo** the project running locally on the **ASUS Ascent GX10**.
  - Return the hardware in the same condition.
  - Complete the **ASUS feedback survey before judging ends**.
- **Judged on:**
  - solving real problems
  - innovation and novel use of local hardware acceleration
  - **showing why running locally matters**
  - inspiring and engaging users
- **Notes:** The GX10 ships with NVIDIA Nemotron (the ASUS doc says "Nemotron 3.5 Lightning"). Using it is a natural sponsor nod.
- **Prizes:** 1st 4x NVIDIA 5080, 2nd 4x ROG keyboards, 3rd 4x ZenScreen monitors.
- **Content challenge:** post publicly (not private or unlisted) with the required tags (IG @asususa @hack.dev_ucsc @baskinengineering; LinkedIn @ASUS Education @Hack.dev @Baskin Engineering at UCSC; TikTok @asuseducation; YouTube @ASUSUSA) and the hashtags #ASUSEducation #agentcomputer. Proof goes in a form handed out during the event. The prize was announced at the opening ceremony.

### Cloud AI, led by Cisco Outshift / AGNTCY: "When AI Agents Disagree"

Our council matches **Level 3** almost word for word. Level 3 asks for:

- at least three autonomous agents with competing objectives
- agents that deliberate, negotiate and try to reach consensus without a central decision-maker
- success measured by genuine disagreement, a real deliberation mechanism, the effect of new information, and **a comparison against a simpler baseline**
- "Consensus is not always the right outcome; explain when the system should stop, keep the disagreement, or ask a human."

Other terms:

- **Framework:** AGNTCY/coffeeAGNTCY is optional; any framework works.
- **Judged on:** Functionality, Innovation, Agent intelligence, Engineering, Demonstration, Learning and evidence.
- **Submit:** a working demo, an architecture overview, technical implementation details, and results and lessons learned.
- **Prizes:** 1st 4x iPad Pro, 2nd 4x Switch, 3rd 4x Razer mice.

**Team decision needed:** we can't take both track prizes. We're on Local (ASUS). The pitch should still meet the Cisco Level 3 bar, because those items are exactly what make it strong under the general criteria. Lead with **why local matters**: incident evidence, customer personal data and legal deliberations under privilege shouldn't leave the building. That's the Compliance seat's whole argument.

## Team deliverables

1. **Devpost entry by 1:30 PM Sunday** with the table number, repo link, architecture and results.
2. **A 3-minute pitch plus a live demo on the GX10.** The council handles a simulated intrusion, new information arrives mid-deliberation, and at least one case escalates to a human instead of being forced through by vote.
3. **Evidence:** council vs single-agent baseline on the same scenarios, with numbers.
4. **Architecture:** a fixed round protocol, the model per seat with reasons, and what we built vs reused.
5. **ASUS survey** completed before judging ends.
6. **Honesty notes:** scenarios are simulated (real procedure text, fake hosts and timestamps), this is not legal advice, and MITRE ATT&CK gets attribution.
7. Every member rehearses explaining the whole system, not just their own seat.

## Compliance seat acceptance criteria (`agents/compliance/`)

| # | Criterion | Check | Status 2026-10-10 |
|---|---|---|---|
| C1 | Every candidate regime gets triggered / not_triggered / needs_determination, with cited evidence | `validate_proposal` | done |
| C2 | Deadlines are computed in code from verified rules, never by the model | `rules.py` + unit tests | done |
| C3 | SEC materiality is always left to a human | validator + test | done |
| C4 | Vetoes only under legal hold, only on unpreserved hosts, and only for non-allowlisted (destructive or unknown) actions | validator + tests | done |
| C5 | Escalation is deterministic and doesn't depend on the model's stance | `escalation()` + tests | done |
| C6 | Resists prompt injection in logs and peer pressure | `injection-001`, `peer-pressure-001` | pass |
| C7 | Smoke suite 9/9 | `evaluate.py` | pass (gemma4:26b) |
| C8 | Real-world suite: at least 90% scenario pass, 100% valid JSON | `realworld/evaluate.py` | gemma4:26b 96% |
| C9 | Under 30s per decision on the GX10 | eval latency | gemma4:26b about 23s mean |
| C10 | Model chosen by a measured sweep across families and optimized variants, including the pre-loaded Nemotron | `realworld/sweep.py` | running |
| C11 | Accepts Containment's ATT&CK fixtures plus the `compliance` block, with no code change | `realworld/evaluate.py --suite attack` | running (gemma4:26b) |
| C12 | Plugs into the council round protocol (Forensics' CouncilMessage v1.0.0: FINDING, VOTE, ESCALATION) | team protocol | mapping written in team doc; adapter not built |
| C13 | Runs fully on the GX10 with no cloud calls, for the Local AI track | demo | yes (Ollama on the GX10) |
