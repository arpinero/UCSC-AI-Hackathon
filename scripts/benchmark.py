#!/usr/bin/env python3
"""Repeatable benchmark CLI for the Forensics / Investigation Agent.

Runs a registered investigator callable against every committed synthetic
scenario and prints a metrics report (findings accuracy, stance accuracy,
tool-call count, mean/max ToolInvocation.duration_ms).

Examples:
    python scripts/benchmark.py
    python scripts/benchmark.py --investigator baseline --json
    python scripts/benchmark.py --scenarios-dir simulations/scenarios
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from simulations.benchmark import (  # noqa: E402
    format_json_report,
    format_text_report,
    get_investigator,
    run_benchmark,
)
from simulations.loader import DEFAULT_SCENARIOS_ROOT  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--scenarios-dir",
        type=Path,
        default=DEFAULT_SCENARIOS_ROOT,
        help="root directory containing scenario folders (default: simulations/scenarios)",
    )
    parser.add_argument(
        "--investigator",
        default="baseline",
        help="registered investigator callable to benchmark (default: baseline)",
    )
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = parser.parse_args(argv)

    investigator = get_investigator(args.investigator)
    report = run_benchmark(
        investigator,
        args.scenarios_dir,
        investigator_name=args.investigator,
    )
    if args.json:
        print(json.dumps(format_json_report(report), indent=2))
    else:
        print(format_text_report(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
