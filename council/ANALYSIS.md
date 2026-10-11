# Verified input / branch review — October 11, 2026

## Both supplied PDFs

`/home/runai-home/UCSC-AI-Hackathon/ASUS Local AI Track Statement (Updated Oct 10).pdf`
(two pages, marked confidential) was read locally and is summarized, not reproduced.
It requires building **and demonstrating** locally on GX10, hardware return in the
same condition, and feedback before judging ends. It identifies GB10 and 128 GB
unified memory. Judging emphasizes useful problems, innovation, local-AI value and
engagement. Privacy/offline incident handling is a relevant pitch, but local deployment
alone does not guarantee security. GB300 development is useful; organizer clarification
is advisable if development entirely off GX10 would conflict with the build requirement.

`/home/runai-home/UCSC-AI-Hackathon/Hacker Guide - UCSC AI Hackathon.pdf`
(three pages) specifies October 10–11, 2026; Sunday Devpost deadline 1:30 PM,
judging 2 PM, three-minute pitch plus three-minute Q&A, hardware return 3:45 PM,
finals 4 PM. Times may change via Discord. One prize track, at most four people,
table number on submission, and every member must explain the project. The guide
does not itself contain the detailed Cisco Level 3 criteria; those are recorded in
the team's `/home/runai-home/UCSC-AI-Hackathon/HACKATHON.md`, a secondary team summary.

## Every available branch at inspection

| Branch | Commit | Assessment |
|---|---|---|
| `origin/main` | `5a809bb` | README-only baseline; no agent foundation here. |
| `origin/apinero` | `ad2e1aa` | Aidan model setup, seven Fixing specs / 21 fixtures and scorer; no production proposal/debate agent. |
| `origin/containment` | `3f4707f` | Kaylem's validated proposals, HTTP service, fixtures, deterministic network simulator, research artifacts and tests. |
| `origin/compliance` | `182e7d4` | Soren's validated review service, deterministic deadlines/hold veto/escalation, smoke and ATT&CK/real-world evaluation suites. |
| `origin/council` | `81a2d5a` | Already integrates Containment/Compliance/Fixing fixtures, PDFs and collision-safe source loader; pipeline otherwise unfinished. |
| `origin/forensics` | `53ef420` | Andrew's contracts, coordination, API and 125 mock/contract/integration tests. Snapshot explicitly excludes unfinished production reasoning/tools/inference workstreams. |

Branch trees, documentation, integration contracts and relevant test logic were
inspected; this is not a line-by-line security audit of every research artifact.
Only one worktree was present. Claims about other machines' uncommitted work,
currently running teammate services, GPU contention or current model accuracy
were not assumed. Remote references were inspected as available locally; no fetch,
push, teammate branch edits or commits were performed.

## Integration decisions

- Additive branch `council-pipeline` from existing `origin/council`; no redundant merges.
- Preserve teammate ownership and existing contracts, use optional Forensics HTTP
  adapter instead of merging unfinished workstreams.
- Ground truth, fixture answer keys, simulator events and faults stay outside seat context.
- Never override compliance-required escalation; negotiate safe recovery deferrals.
- No autonomous real remediation. Baseline is a simulator with explicit execution receipts.
- No claim of live multi-agent model success while selected services are unavailable.
- No severity threshold tuning against the same cases used to report accuracy.

## Verification baseline

Initial existing tests: 59 Containment, 32 Compliance, 10 Fixing, all passing.
Forensics branch tested from `/tmp/council-forensics-audit`: 125 tests passed, with
one existing Pydantic protected-namespace warning. New pipeline tests exercise
negotiation, unanimous votes, stale telemetry, new evidence, legal hold, clean-backup
checks, report persistence, outage behavior, criticality and deadlock. See generated
results and test output for current pipeline counts, rather than inherited model claims.