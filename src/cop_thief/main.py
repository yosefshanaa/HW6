"""CLI entry point: run a full series and emit the JSON report (PLAN §3).

Usage (uv only):
    uv run cop-thief
    uv run cop-thief --results-dir results
    uv run cop-thief --send            # also email the JSON report (needs credentials.json)
The report is written to ``<series>/report.json`` and printed as JSON to stdout
(the JSON-only body that the Gmail reporter emails).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from cop_thief.sdk.sdk import CopThiefSDK
from cop_thief.shared.config import load_config
from cop_thief.shared.logging_setup import get_logger, setup_logging


def main() -> None:
    """Parse args, play a series, print the JSON report, optionally email it."""
    parser = argparse.ArgumentParser(description="Cop & Thief — run a full series.")
    parser.add_argument("--config", default=None, help="path to config.yaml")
    parser.add_argument("--results-dir", default=None, help="output directory for logs/report")
    parser.add_argument(
        "--send", action="store_true",
        help="email the JSON report via the Gmail API (requires credentials.json)",
    )
    args = parser.parse_args()

    setup_logging()
    log = get_logger("cop_thief")
    sdk = CopThiefSDK(load_config(args.config))
    log.info("Cop & Thief v%s — starting series", sdk.version())

    reporter = _make_reporter(sdk, log) if args.send else None
    report = sdk.play_and_report(results_dir=args.results_dir, reporter=reporter)

    totals = report["totals"]
    log.info("series complete — totals cop=%s thief=%s", totals["cop"], totals["thief"])
    print(json.dumps(report))


def _make_reporter(sdk: CopThiefSDK, log):
    """Build a Gmail reporter when credentials exist; otherwise warn and skip."""
    creds = sdk.config.get("report.credentials_file", "credentials.json")
    if not Path(creds).exists():
        log.error("--send set but %s not found; writing report without sending", creds)
        return None
    log.info("emailing report to %s", sdk.config.get("report.recipient"))
    return sdk.gmail_reporter()


if __name__ == "__main__":
    main()
