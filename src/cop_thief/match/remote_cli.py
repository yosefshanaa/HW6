"""CLI: play the inter-team bonus match against two live MCP servers over HTTP.

Reads URLs from config (``mcp.cop_url`` / ``mcp.thief_url``, override with flags) and
the per-server bearer tokens from the environment. The Cop server is the
authoritative referee; the Thief server is the in-sync mirror. Writes the §9.2
report to ``<series>/bonus_report.json`` and prints it as JSON to stdout.

Usage (tokens in env; default config is the match config):
    uv run cop-thief-remote-match
    uv run cop-thief-remote-match --cop-strategy search --thief-strategy search   # deterministic
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from cop_thief.agents.agent_client import AgentClient, HttpTransport
from cop_thief.match.remote_match import RemoteMatch
from cop_thief.sdk.sdk import CopThiefSDK
from cop_thief.shared.config import load_config
from cop_thief.shared.logging_setup import get_logger, setup_logging


def main() -> None:
    """Parse args, play the series over HTTP, write + print the §9.2 report."""
    p = argparse.ArgumentParser(description="Cop & Thief — play the inter-team match over HTTP.")
    p.add_argument("--config", default="config/config.match.yaml")
    p.add_argument("--cop-url", default=None, help="authoritative Cop server URL (default mcp.cop_url)")
    p.add_argument("--thief-url", default=None, help="Thief server URL (default mcp.thief_url)")
    p.add_argument("--cop-token-env", default="COP_MCP_AUTH_TOKEN")
    p.add_argument("--thief-token-env", default="THIEF_MCP_AUTH_TOKEN")
    p.add_argument("--cop-strategy", default=None, help="override agents.cop_strategy")
    p.add_argument("--thief-strategy", default=None, help="override agents.thief_strategy")
    p.add_argument("--results-dir", default=None)
    args = p.parse_args()

    setup_logging()
    log = get_logger("cop_thief.remote")
    config = load_config(args.config)
    if args.cop_strategy:
        config.data.setdefault("agents", {})["cop_strategy"] = args.cop_strategy
    if args.thief_strategy:
        config.data.setdefault("agents", {})["thief_strategy"] = args.thief_strategy

    cop_url = args.cop_url or config.get("mcp.cop_url")
    thief_url = args.thief_url or config.get("mcp.thief_url")
    if not cop_url or not thief_url or str(cop_url).startswith("TODO"):
        sys.exit("set mcp.cop_url / mcp.thief_url in config (or pass --cop-url/--thief-url)")

    log.info("connecting cop=%s thief=%s", cop_url, thief_url)
    cop_t = HttpTransport(cop_url, token=os.environ.get(args.cop_token_env))
    thief_t = HttpTransport(thief_url, token=os.environ.get(args.thief_token_env))
    try:
        match = RemoteMatch(
            config, AgentClient(cop_t, "cop"), AgentClient(thief_t, "thief"),
            results_dir=args.results_dir,
            group_1=config.get("match.group_1", "group_1"),
            group_2=config.get("match.group_2", "group_2"),
        )
        outcome = match.play_series()
    finally:
        cop_t.close()
        thief_t.close()

    report = CopThiefSDK(config).build_bonus_report(outcome)
    (match.series_dir / "bonus_report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    for r in outcome.results:
        print(f"  sub-game {r.index}: winner={r.winner.value} moves={r.moves_played} "
              f"cop={r.cop_score} thief={r.thief_score}", file=sys.stderr)
    print(f"  totals: {outcome.totals_by_group} | reconcile flags: {len(outcome.flags)} "
          f"| logs: {match.series_dir}", file=sys.stderr)
    print(json.dumps(report))


if __name__ == "__main__":
    main()
