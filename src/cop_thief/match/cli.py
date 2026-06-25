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
import sys

from cop_thief.sdk.sdk import CopThiefSDK
from cop_thief.shared.config import load_config
from cop_thief.shared.logging_setup import get_logger, setup_logging


def _print_summary(report: dict, series_dir) -> None:
    """Human-readable per-sub-game + team-total summary (to stderr; stdout stays JSON)."""
    g = report["groups"]
    out = sys.stderr
    print(f"\n=== Two-team bonus dry-run (local loopback) ===\n  {g['group_1']}  vs  {g['group_2']}",
          file=out)
    for sg in report["sub_games"]:
        cop, thief = sg.get("cop_group", "?"), sg.get("thief_group", "?")
        print(f"  sub-game {sg['index']}: Cop={cop:<16} Thief={thief:<16} "
              f"winner={sg.get('winner_group', '?')} ({sg['winner']})  "
              f"scores cop {sg['cop_score']} / thief {sg['thief_score']}", file=out)
    fmt = lambda d: ", ".join(f"{k} {v}" for k, v in d.items())  # noqa: E731
    print(f"  team totals: {fmt(report['totals_by_group'])}", file=out)
    print(f"  series winner: {report['series_winner']}", file=out)
    print(f"  bonus claim: {fmt(report['bonus_claim'])}  (mutual_agreement="
          f"{str(report['mutual_agreement']).lower()})", file=out)
    print(f"  output dir : {series_dir}/  (sub_game_*.jsonl + bonus_report.json)", file=out)


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
    _print_summary(report, series_dir)
    print(json.dumps(report))  # stdout: the §9.2 report (JSON only, last line)


if __name__ == "__main__":
    main()
