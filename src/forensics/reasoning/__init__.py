"""Forensics reasoning: investigation loop, debate, revision, and reporting.

All components receive ``InferenceBackend`` (and, where tools are executed,
``ToolRegistry``) via constructor injection and work with the Stage A mocks
today and real backends after integration. No concrete backend is imported.

Hard rule enforced throughout: findings and positions cite ONLY evidence ids
that were actually provided; violations raise
:class:`forensics.reasoning.validation.EvidenceFabricationError`.
"""

from forensics.reasoning.debate import ProposalEvaluator
from forensics.reasoning.investigation import InvestigationEngine
from forensics.reasoning.report import RecommendedReport, ReportRecommender
from forensics.reasoning.revision import PositionReviser
from forensics.reasoning.validation import (
    EvidenceFabricationError,
    known_evidence_ids,
    validate_cited_evidence_ids,
    validate_findings,
)

__all__ = [
    "EvidenceFabricationError",
    "InvestigationEngine",
    "PositionReviser",
    "ProposalEvaluator",
    "RecommendedReport",
    "ReportRecommender",
    "known_evidence_ids",
    "validate_cited_evidence_ids",
    "validate_findings",
]

