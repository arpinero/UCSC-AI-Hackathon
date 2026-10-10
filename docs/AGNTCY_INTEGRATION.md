# AGNTCY Integration (research status — runtime messaging)

## Verified research findings (2026-10-10, from GitHub/docs)

- AGNTCY is a Linux Foundation project. Components: **SLIM** (Secure
  Low-Latency Interactive Messaging; Rust core + language bindings), **DIR**
  (agent directory: discovery/registration), **Identity** (verifiable
  credentials), **OASF** (schema framework), **Observe SDK**, **SHADI**.
- **CoffeeAGNTCY** (`agntcy/coffeeAgntcy`, Python, Apache-2.0) is the official
  reference application:
  - **Corto** — two-agent setup, A2A messaging over SLIM transport, LangGraph
    orchestration. Our minimal starting pattern.
  - **Lungo** — larger MAS: pub/sub A2A over NATS or group communication over
    SLIM, streaming, MCP tools, observability, identity. Matches the council
    debate topology (multiple agents, proposals, challenges, votes).
  - Pinned versions at audit time: app-sdk v0.5.5, SLIM v1.4.0, A2A v0.3.20,
    LangGraph v1.2.11.
- `agntcy/agntcy-contrib` does **not exist** (404). Real repos:
  `agntcy/slim`, `agntcy/slim-bindings`, `agntcy/app-sdk`,
  `agntcy/coffeeAgntcy`, `agntcy/dir`.

## NOT verified (do not assume)

- No AGNTCY package is installed on this machine. SLIM Python bindings on
  **aarch64 + Python 3.12** are unverified. Docker is unusable for this user,
  so containerized SLIM is not an option without human intervention.

## Recommended topology (PROPOSED — implemented in Stage B only)

1. One channel/session per incident; forensics subscribes on incident alert.
2. Every council exchange is a `CouncilMessage` (contracts/messages.py) with
   a correlation ID; thread = correlation ID.
3. Rounds: the council advances `round` on the incident; positions, findings,
   challenges, revisions, votes all carry the round number.
4. Transport decision tree for the AGNTCY engineer:
   a. Try SLIM via `slim-bindings` on ARM64 (verify installability first).
   b. If unusable: A2A protocol messages over plain HTTP between agent
      services (still A2A-compatible envelopes; transport-agnostic adapters).
   c. Either way, keep `forensics.messaging` transport-agnostic with a mock
      transport so the rest of the stack never blocks on transport work.
5. DIR/Identity: optional for a 24-hour hackathon on one machine; defer
   unless trivial. Agent identity for Stage B = configured agent IDs.

## Council capabilities required at runtime

Receive incidents; receive containment proposals; investigate evidence
(read-only synthetic data); publish findings (with cited evidence);
challenge unsupported recommendations; receive additional evidence; revise
positions (explicit PositionRevision audit records); send recommendations
and votes; preserve the full debate history (correlation-threaded).
