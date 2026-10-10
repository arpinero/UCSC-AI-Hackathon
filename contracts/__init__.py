"""Forensics shared contracts (v1, FROZEN).

Cross-team note: these schemas are authoritative inside this repository but
are PROPOSED for cross-team integration until the four human developers
agree on them. See docs/TEAM_INTEGRATION_STAGE_A.md.
"""

from contracts import common

CONTRACTS_VERSION = common.CONTRACTS_VERSION

__all__ = ["CONTRACTS_VERSION", "common"]
