"""CLI entry point: run a full series and emit the JSON report (PLAN §3).

Usage (uv only):
    uv run cop-thief
    uv run cop-thief --results-dir results
The report is written to ``<series>/report.json`` and printed as JSON to stdout
(the JSON-only body that the Gmail reporter would email).
"""

from __future__ import annotations

import argparse
import json

from cop_thief.sdk.sdk import CopThiefSDK
from cop_thief.shared.config import load_config
from cop_thief.shared.logging_setup import get_logger, setup_logging


def main() -> None:
    """Parse args, play a series, and print the JSON report."""
    parser = argparse.ArgumentParser(description="Cop & Thief — run a full series.")
    parser.add_argument("--config", default=None, help="path to config.yaml")
    parser.add_argument("--results-dir", default=None, help="output directory for logs/report")
    args = parser.parse_args()

    setup_logging()
    log = get_logger("cop_thief")
    sdk = CopThiefSDK(load_config(args.config))
    log.info("Cop & Thief v%s — starting series", sdk.version())

    report = sdk.play_and_report(results_dir=args.results_dir)

    totals = report["totals"]
    log.info("series complete — totals cop=%s thief=%s", totals["cop"], totals["thief"])
    print(json.dumps(report))


if __name__ == "__main__":
    main()
