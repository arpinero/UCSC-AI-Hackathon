"""Evidence-citation validation shared by all reasoning components.

The single hard rule of the forensics agent: NEVER cite evidence that was not
provided. These helpers enforce that rule and fail loudly (raise
``EvidenceFabricationError``) on any violation.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

from contracts.evidence import Evidence
from contracts.investigation import InvestigationFindings


class EvidenceFabricationError(ValueError):
    """Raised when output cites an evidence id that was never provided."""

    def __init__(self, unknown_ids: list[str], context: str = "") -> None:
        self.unknown_ids = sorted(unknown_ids)
        detail = f"unknown evidence ids cited: {', '.join(self.unknown_ids)}"
        if context:
            detail = f"{context}: {detail}"
        super().__init__(detail)


_WORDS = re.compile(r"[a-z0-9]+")

#: Words that carry no forensic meaning; ignored when matching proposal or
#: condition text against evidence descriptions.
_STOPWORDS = frozenset(
    {
        "the", "a", "an", "and", "or", "of", "to", "in", "on", "at", "by", "for",
        "with", "from", "as", "is", "are", "was", "were", "be", "been", "has",
        "have", "had", "this", "that", "these", "those", "it", "its", "would",
        "will", "should", "could", "can", "may", "might", "not", "no", "yes",
        "evidence", "change", "position", "new", "show", "shows", "showing",
        "indicate", "indicates", "demonstrate", "demonstrates", "any", "all",
        "only", "such", "than", "then", "when", "which", "who", "what", "how",
        "into", "over", "under", "about", "across", "per", "via", "were",
        "there", "their", "they", "them", "your", "you", "are", "our",
    }
)


def keyword_tokens(text: str) -> frozenset[str]:
    """Distinctive lowercase word tokens of ``text`` (stopwords removed)."""
    return frozenset(
        t for t in _WORDS.findall(text.lower()) if len(t) > 3 and t not in _STOPWORDS
    )


def known_evidence_ids(evidence: Iterable[Evidence]) -> frozenset[str]:
    """The set of evidence ids that actually exist in the provided evidence."""
    return frozenset(e.evidence_id for e in evidence)


def unknown_ids(cited: Iterable[str], evidence: Iterable[Evidence]) -> list[str]:
    """Cited ids that do not exist in the provided evidence."""
    known = known_evidence_ids(evidence)
    return [i for i in cited if i not in known]


def validate_cited_evidence_ids(
    cited: Iterable[str], evidence: Iterable[Evidence], *, context: str = ""
) -> None:
    """Raise :class:`EvidenceFabricationError` if any cited id is unknown."""
    missing = unknown_ids(cited, evidence)
    if missing:
        raise EvidenceFabricationError(missing, context=context)


def validate_findings(
    findings: InvestigationFindings, evidence: Iterable[Evidence]
) -> None:
    """Validate every evidence citation inside ``findings`` (incl. timeline).

    Raises :class:`EvidenceFabricationError` listing all unknown ids.
    """
    known = known_evidence_ids(evidence)
    missing = set(unknown_ids(findings.cited_evidence_ids, evidence))
    for event in findings.timeline:
        missing.update(i for i in event.evidence_ids if i not in known)
    if missing:
        raise EvidenceFabricationError(sorted(missing), context="findings")
