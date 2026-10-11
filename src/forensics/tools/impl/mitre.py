"""lookup_mitre_technique: static MITRE ATT&CK table lookup.

The table lives in ``src/forensics/tools/data/mitre.json`` (synthetic,
committed data covering the evaluation scenarios' techniques). Unknown IDs
are never guessed: the tool returns ``found=False``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from contracts.tools import (
    LookupMitreTechniqueArgs,
    LookupMitreTechniqueResult,
    MitreTechniqueInfo,
)
from forensics.tools.base import ForensicTool

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_DEFAULT_MAPPING_PATH = _DATA_DIR / "mitre.json"


class LookupMitreTechnique(ForensicTool):
    """Look up a MITRE ATT&CK technique in the committed static table."""

    name = "lookup_mitre_technique"
    description = (
        "Look up a MITRE ATT&CK technique ID (e.g. T1486, T1566.001) in the "
        "static technique table. Returns found=False for unknown IDs; never "
        "guesses."
    )
    args_model = LookupMitreTechniqueArgs
    result_model = LookupMitreTechniqueResult

    def __init__(self, mapping_path: str | Path | None = None) -> None:
        path = Path(mapping_path) if mapping_path is not None else _DEFAULT_MAPPING_PATH
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"cannot load MITRE mapping {path}: {exc}") from exc
        techniques: dict[str, dict[str, Any]] = {}
        for entry in document.get("techniques", []):
            technique_id = entry["technique_id"]
            if technique_id in techniques:
                raise ValueError(f"duplicate technique_id in {path}: {technique_id}")
            techniques[technique_id] = entry
        self._mapping = techniques

    def run(self, args: LookupMitreTechniqueArgs) -> BaseModel:
        technique_id = args.technique_id.strip().upper()
        entry = self._mapping.get(technique_id)
        if entry is None:
            return LookupMitreTechniqueResult(technique=None, found=False)
        return LookupMitreTechniqueResult(
            technique=MitreTechniqueInfo(
                technique_id=technique_id,
                name=entry["name"],
                tactics=list(entry.get("tactics", [])),
                description=entry["description"],
                platform=list(entry.get("platform", [])),
            )
        )
