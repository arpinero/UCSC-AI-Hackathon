"""submit_incident_report: the ONLY writing tool.

Writes a report JSON artifact to a constructor-injected output directory
(default: /home/asus/forensics-agent-coordination/reports/, outside git).
The returned report_id is the path of the written artifact.
"""

from __future__ import annotations

import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from contracts.tools import SubmitIncidentReportArgs, SubmitIncidentReportResult
from forensics.tools.base import ForensicTool

DEFAULT_REPORT_DIR = Path("/home/asus/forensics-agent-coordination/reports")


class SubmitIncidentReport(ForensicTool):
    """Write the incident report artifact (the only tool that writes)."""

    name = "submit_incident_report"
    description = (
        "Submit the final incident report as a JSON artifact and return its "
        "path (report_id). This is the only tool that writes."
    )
    args_model = SubmitIncidentReportArgs
    result_model = SubmitIncidentReportResult
    read_only = False

    def __init__(self, output_dir: str | Path = DEFAULT_REPORT_DIR) -> None:
        self.output_dir = Path(output_dir)

    def run(self, args: SubmitIncidentReportArgs) -> BaseModel:
        safe_incident = re.sub(r"[^A-Za-z0-9_.-]", "_", args.incident_id)
        report_id = f"RPT-{safe_incident}-{uuid.uuid4().hex[:8]}"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        target = self.output_dir / f"{report_id}.json"
        tmp = target.with_suffix(".json.tmp")

        payload: dict[str, Any] = {
            "report_id": report_id,
            "incident_id": args.incident_id,
            "status": "SUBMITTED",
            "findings_summary": args.findings_summary,
            "cited_evidence_ids": list(args.cited_evidence_ids),
            "confidence": args.confidence,
            "severity_assessment": args.severity_assessment,
            "recommended_actions": list(args.recommended_actions),
            "submitted_at": datetime.now(timezone.utc).isoformat(),
            "generator": "forensics.tools.impl.SubmitIncidentReport",
        }
        tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        os.replace(tmp, target)
        return SubmitIncidentReportResult(
            report_id=str(target),
            incident_id=args.incident_id,
            status="SUBMITTED",
        )
