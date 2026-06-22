"""CLI: run the local inter-group match dry-run and emit the §9.2 JSON report.

Usage (uv only):
    uv run cop-thief-match
    uv run cop-thief-match --results-dir results

Models two friendly teams on one machine over the loopback MCP transport
(Phase 12 de-risking). The §9.2 bonus report is written to
``<series>/bonus_report.json`` and printed as JSON to stdout.
"""

from __future__ import annotations

import argparse
import json

from cop_thief.sdk.sdk import CopThiefSDK
from cop_thief.shared.config import load_config
from cop_thief.shared.logging_setup import get_logger, setup_logging


def main() -> None:
    """Parse args, play the local match, print the §9.2 JSON report."""
    parser = argparse.ArgumentParser(
        description="Cop & Thief — local inter-group match dry-run."
    )
    parser.add_argument("--config", default=None, help="path to config.yaml")
    parser.add_argument("--results-dir", default=None, help="output directory for logs/report")
    args = parser.parse_args()

    setup_logging()
    log = get_logger("cop_thief.match")
    sdk = CopThiefSDK(load_config(args.config))
    log.info("Cop & Thief v%s — local inter-group match dry-run", sdk.version())

    outcome, series_dir = sdk.run_local_match(results_dir=args.results_dir)
    report = sdk.build_bonus_report(outcome)
    (series_dir / "bonus_report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )

    if outcome.flags:
        log.warning("engine reconciliation flags: %d (see sub-game logs)", len(outcome.flags))
    else:
        log.info("engines reconciled cleanly across all sub-games")
    log.info("totals by group: %s", report["totals_by_group"])
    print(json.dumps(report))


if __name__ == "__main__":
    main()
