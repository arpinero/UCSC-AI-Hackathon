"""Synthetic simulation package: scenarios, loader, scoring, and benchmark.

Owned by `evaluation-engineer`. See simulations/FORMAT.md for the on-disk
scenario format. The investigator-facing API is `simulations.loader.EvidenceStore`
— it NEVER exposes ground truth; scoring reads ground truth via
`simulations.scoring` only.
"""
