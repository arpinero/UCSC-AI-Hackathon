# Architecture (Stage A foundation)

## System context

The Forensics / Investigation Agent is one of four council agents
(Forensics, Containment, Recovery, Compliance) that investigate synthetic
cyber incidents, exchange evidence, debate containment proposals, and vote.
At runtime they communicate via AGNTCY-style messaging (A2A over SLIM or a
fallback transport — see AGNTCY_INTEGRATION.md).

## Repository layers

    contracts/           FROZEN v1 Pydantic schemas (wire format for everything)
    src/forensics/
      inference/         abstract InferenceBackend + mock (Stage B: transformers, llamacpp)
      tools/             abstract ForensicTool + registry + 7 mock tools
      messaging/         Stage B: runtime council transport (AGNTCY engineer)
      reasoning/         Stage B: investigation & debate logic (reasoning engineer)
      api/               Stage B: optional local service surface
    coordination/        CODING-AGENT SQLite message bus (development only!)
    simulations/         Stage B: synthetic scenarios + ground truth
    tests/               contracts / unit / coordination / integration / e2e

## Key design rules

1. **Contracts first.** Everything crossing a component boundary is a typed
   Pydantic model from `contracts/` (strict, extra=forbid, UTC timestamps,
   confidence in [0,1], JSON-Schema exportable). Frozen at v1.
2. **Model isolation.** Chat templates and tool-call parsing live in
   `forensics.inference` adapters; `forensics.reasoning` consumes only typed
   results. The mock backend lets all workstreams develop without a GPU.
3. **Tool audit.** Every tool call returns a `ToolInvocation` record
   (arguments, result, referenced evidence, error, duration). All tools are
   read-only except `submit_incident_report`.
4. **Two message systems, never mixed.**
   - Runtime council messages: `contracts/messages.py` (CouncilMessage).
   - Development coordination: the SQLite `coordination/` bus.
5. **Evidence provenance.** Evidence has stable IDs + source + collection
   time; findings cite evidence IDs; positions cite evidence IDs; revisions
   link previous position -> new position with triggering evidence.

## Data flow (target, Stage B)

Incident arrives (INCIDENT_ALERT) -> tools investigate read-only synthetic
evidence -> findings published with cited evidence -> containment proposal
arrives -> forensics publishes DebatePosition -> challenge/revise via
PositionRevision -> vote -> report via submit_incident_report. Correlation
IDs thread every exchange; the debate history is auditable end to end.

## Deviations from the original layout

- `contracts/common.py` added for shared enums/validators (documented
  deviation for clean packaging).
- `coordination/__main__.py` added so `python -m coordination` also works.
- Everything else matches the prescribed structure.
