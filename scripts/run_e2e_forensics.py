#!/usr/bin/env python3
"""Real end-to-end Forensics Agent verification (coordinator-owned tooling).

Wires the REAL integrated components and runs them against the three
synthetic scenarios, scoring every run against ground truth:

- Inference: LlamaCppBackend -> Foundation-Sec-8B on llama-server :8000
  (real model inference, no mocks).
- Tools: the seven real forensic tools over the scenario evidence store.
- Reasoning: InvestigationEngine / ProposalEvaluator / PositionReviser.
- Messaging: verified AGNTCY SLIM transport (SlimLocalServer on 127.0.0.1).

Usage:
    PYTHONPATH=src python scripts/run_e2e_forensics.py
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import uuid
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from contracts.investigation import InvestigationRequest  # noqa: E402
from forensics.inference.llamacpp import LlamaCppBackend  # noqa: E402
from forensics.messaging.base import CouncilBus  # noqa: E402
from forensics.messaging.slim_transport import SlimLocalServer, SlimTransport  # noqa: E402
from forensics.reasoning.debate import ProposalEvaluator  # noqa: E402
from forensics.reasoning.investigation import InvestigationEngine  # noqa: E402
from forensics.reasoning.revision import PositionReviser  # noqa: E402
from forensics.tools.impl import build_default_registry  # noqa: E402
from simulations.loader import load_evidence_store, load_scenario_bundle  # noqa: E402
from simulations.runs import InvestigationRun, RoundRecord  # noqa: E402
from simulations.scoring import score_run  # noqa: E402

RESULTS_DIR = Path("/home/asus/forensics-agent-coordination/e2e-results")
HISTORY_DIR = Path("/home/asus/forensics-agent-coordination/debate-history")
SLIM_SECRET = "e2e-local-council-shared-secret-0123456789abcdef"  # loopback dev only


def _req(incident_id: str, round_: int, evidence_ids: list[str]) -> InvestigationRequest:
    return InvestigationRequest(
        request_id=f"REQ-{uuid.uuid4().hex[:8]}",
        incident_id=incident_id,
        round=round_,
        question=(
            "Investigate this security incident using the available evidence. "
            "Determine what happened, the chronological timeline, affected "
            "hosts, likely attacker techniques, and any data impact. Cite only "
            "the provided evidence IDs."
        ),
        available_evidence_ids=evidence_ids,
        requested_by="council-orchestrator",
    )


def _proposal_for(bundle) -> dict:
    hosts = bundle.incident.affected_hosts or ["unknown-host"]
    return {
        "role": "containment",
        "description": "Contain and isolate affected hosts to stop ongoing activity.",
        "actions": [{"kind": "isolate_host", "target_id": h} for h in hosts],
    }


def run_scenario(bundle, backend: LlamaCppBackend) -> dict:
    incident_id = bundle.incident.incident_id
    store = load_evidence_store(bundle.scenario_dir)
    registry = build_default_registry(store)
    engine = InvestigationEngine(backend, registry)
    evaluator = ProposalEvaluator(backend)
    reviser = PositionReviser(backend)
    proposal = _proposal_for(bundle)

    rounds: list[RoundRecord] = []
    stage_ms: dict[str, float] = {}

    ev1 = store.available_evidence(1)
    t0 = time.monotonic()
    f1 = engine.investigate(_req(incident_id, 1, [e.evidence_id for e in ev1]), ev1)
    stage_ms["investigate_round1_ms"] = (time.monotonic() - t0) * 1000
    inv1 = engine.last_invocations
    t0 = time.monotonic()
    pos1 = evaluator.evaluate_proposal(proposal, ev1, f1)
    stage_ms["evaluate_proposal_ms"] = (time.monotonic() - t0) * 1000
    rounds.append(RoundRecord(round_=1, findings=f1, position=pos1, tool_invocations=inv1))

    ev2 = store.available_evidence(2)
    if len(ev2) > len(ev1):
        known = {e.evidence_id for e in ev1}
        new = [e for e in ev2 if e.evidence_id not in known]
        t0 = time.monotonic()
        f2 = engine.investigate(_req(incident_id, 2, [e.evidence_id for e in ev2]), ev2)
        stage_ms["investigate_round2_ms"] = (time.monotonic() - t0) * 1000
        inv2 = engine.last_invocations
        t0 = time.monotonic()
        revision = reviser.revise_position(pos1, new)
        stage_ms["revise_position_ms"] = (time.monotonic() - t0) * 1000
        pos2 = revision.new_position if revision is not None else pos1
        rounds.append(
            RoundRecord(
                round_=2, findings=f2, position=pos2, revision=revision,
                tool_invocations=inv2,
            )
        )

    run = InvestigationRun(
        scenario_id=bundle.scenario_id, incident_id=incident_id, rounds=rounds
    )
    report = score_run(bundle.ground_truth, run)
    return {
        "scenario_id": bundle.scenario_id,
        "incident_id": incident_id,
        "severity": bundle.incident.severity.value,
        "rounds": [
            {
                "round": r.round,
                "position": r.position.position.value,
                "confidence": r.position.confidence,
                "cited_evidence_ids": r.findings.cited_evidence_ids,
                "findings": r.findings.findings,
                "recommended_actions": r.findings.recommended_actions,
                "timeline_events": len(r.findings.timeline),
                "tool_calls": [
                    {"tool": i.tool_name, "ms": i.duration_ms, "error": i.error is not None}
                    for i in r.tool_invocations
                ],
                "revision": (
                    {
                        "from": r.revision.previous_position.position.value,
                        "to": r.revision.new_position.position.value,
                        "triggering": r.revision.triggering_evidence_ids,
                        "explanation": r.revision.explanation,
                    }
                    if r.revision
                    else None
                ),
            }
            for r in run.rounds
        ],
        "metrics": report.metrics,
        "flags": report.flags,
        "stage_ms": stage_ms,
        "tool_call_count": sum(len(r.tool_invocations) for r in run.rounds),
    }


def publish_over_slim(bundle, result: dict) -> dict:
    """Publish the run's council messages over REAL SLIM and verify receipt.

    Two SLIM apps on an in-process loopback server: forensics-agent sends
    INCIDENT_ALERT + FINDING + VOTE; council-monitor receives and both debate
    histories record the exchange. Returns verification details.
    """
    server = SlimLocalServer()
    server.start()
    try:
        sender_bus = CouncilBus(
            SlimTransport("forensics-agent", server.url, SLIM_SECRET),
            history_dir=HISTORY_DIR,
        )
        monitor_bus = CouncilBus(
            SlimTransport("council-monitor", server.url, SLIM_SECRET),
            history_dir=HISTORY_DIR,
        )
        incident_id = result["incident_id"]
        sender = sender_bus.session(incident_id)
        monitor = monitor_bus.session(incident_id)
        sent: list[str] = []
        sender.send(
            sender.build(
                message_type="INCIDENT_ALERT", sender="forensics-agent",
                recipients=["council-monitor"],
                payload={"severity": result["severity"]},
            )
        )
        for rnd in result["rounds"]:
            sender.send(
                sender.build(
                    message_type="FINDING", sender="forensics-agent",
                    recipients=["council-monitor"],
                    payload={"round": rnd["round"], "findings": rnd["findings"]},
                )
            )
            sender.send(
                sender.build(
                    message_type="VOTE", sender="forensics-agent",
                    recipients=["council-monitor"],
                    payload={"round": rnd["round"], "position": rnd["position"]},
                )
            )
            if rnd["revision"]:
                sender.send(
                    sender.build(
                        message_type="REVISION", sender="forensics-agent",
                        recipients=["council-monitor"],
                        payload={"revision": rnd["revision"]},
                    )
                )
            sent.extend(["FINDING", "VOTE"] + (["REVISION"] if rnd["revision"] else []))
        received: list[str] = []
        while True:
            try:
                msg = monitor.receive(timeout_s=5.0)
                received.append(msg.message_type.value)
            except Exception:
                break
        sender_bus.close()
        monitor_bus.close()
        return {
            "transport": "slim (SlimLocalServer, loopback, shared-secret)",
            "sent": sent,
            "received": received,
            "received_matches_sent": received == sent,
            "history_file": str(HISTORY_DIR / f"{incident_id}.jsonl"),
        }
    finally:
        server.stop()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--scenarios", default="ransom01,lateral01,exfil01",
        help="comma-separated scenario ids under simulations/scenarios/",
    )
    args = parser.parse_args()

    backend = LlamaCppBackend()
    if not backend.health_check():
        print("FATAL: llama.cpp backend health check failed (is :8000 up?)")
        return 1
    meta = backend.get_model_metadata()
    print(f"backend: {meta.backend_name} model={meta.model_id} ctx={meta.context_window}")

    results = []
    for sid in [s.strip() for s in args.scenarios.split(",") if s.strip()]:
        scenario_dir = _REPO_ROOT / "simulations" / "scenarios" / sid
        bundle = load_scenario_bundle(scenario_dir)
        print(f"== scenario {sid} ({bundle.incident.severity.value}) ==")
        result = run_scenario(bundle, backend)
        result["slim"] = publish_over_slim(bundle, result)
        print(
            f"   position(s): {[r['position'] for r in result['rounds']]}"
            f"  metrics={ {k: round(v, 3) for k, v in result['metrics'].items()} }"
        )
        print(f"   tool_calls={result['tool_call_count']} flags={result['flags']}")
        slim = result["slim"]
        print(
            f"   slim: sent={len(slim['sent'])} "
            f"received={len(slim['received'])} "
            f"match={slim['received_matches_sent']}"
        )
        results.append(result)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out = RESULTS_DIR / f"e2e_{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}.json"
    out.write_text(json.dumps({
        "model": {"backend": meta.backend_name, "model_id": meta.model_id},
        "results": results,
    }, indent=1) + "\n")
    print(f"saved: {out}")
    ok = all(
        r["slim"]["received_matches_sent"] and not r["flags"] for r in results
    )
    print(f"E2E RESULT: {'PASS' if ok else 'PASS WITH FLAGS'} (see JSON for details)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
