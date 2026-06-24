"""CLI: play OUR half of the inter-team match against the live MCP servers.

Each team runs this for its own side (``--group group_1`` = us by default). It
connects to all four servers (ours + the partner's), drives our agent for whichever
role we have each sub-game, and dual-submits to both referees. Per-(seed,index)
starts and turn-based coordination keep the two engines in sync. Writes our §9.2
report view to ``<series>/bonus_report.json`` and prints it to stdout.

URLs come from config (``mcp.*`` = ours, ``match.mcp_url_group_2_*`` = partner).
Tokens come from env: ours ``COP_MCP_AUTH_TOKEN`` / ``THIEF_MCP_AUTH_TOKEN``,
partner ``PEER_COP_MCP_AUTH_TOKEN`` / ``PEER_THIEF_MCP_AUTH_TOKEN``.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from cop_thief.agents.agent_client import AgentClient, HttpTransport
from cop_thief.match.remote_side import RemoteSide
from cop_thief.sdk.sdk import CopThiefSDK
from cop_thief.shared.config import load_config
from cop_thief.shared.logging_setup import get_logger, setup_logging


def _require(value, name: str) -> str:
    if not value or str(value).startswith("TODO"):
        sys.exit(f"missing {name} (fill config / env before the match)")
    return str(value)


def main() -> None:
    """Connect to all four servers, play our side, write + print the report."""
    p = argparse.ArgumentParser(description="Cop & Thief — play our half of the match over HTTP.")
    p.add_argument("--config", default="config/config.match.yaml")
    p.add_argument("--group", default="group_1", choices=["group_1", "group_2"],
                   help="which side we are (group_1 = us, the default)")
    p.add_argument("--results-dir", default=None)
    p.add_argument("--send", action="store_true",
                   help="email the §9.2 report via Gmail at the end (needs credentials.json)")
    args = p.parse_args()

    setup_logging()
    log = get_logger("cop_thief.play_side")
    config = load_config(args.config)
    g1, g2 = config.get("match.group_1"), config.get("match.group_2")
    my_group = g1 if args.group == "group_1" else g2

    our_cop = _require(config.get("mcp.cop_url"), "mcp.cop_url")
    our_thief = _require(config.get("mcp.thief_url"), "mcp.thief_url")
    their_cop = _require(config.get("match.mcp_url_group_2_cop"), "match.mcp_url_group_2_cop")
    their_thief = _require(config.get("match.mcp_url_group_2_thief"), "match.mcp_url_group_2_thief")
    if args.group == "group_2":  # running as the partner side (e.g. a self-test): swap ours/theirs
        our_cop, their_cop = their_cop, our_cop
        our_thief, their_thief = their_thief, our_thief

    # One transport per distinct URL (reused across sub-games), torn down at the end.
    transports: dict[str, HttpTransport] = {}

    def client(url: str, role: str, token_env: str) -> AgentClient:
        if url not in transports:
            transports[url] = HttpTransport(url, token=os.environ.get(token_env))
        return AgentClient(transports[url], role)

    our_cop_c = client(our_cop, "cop", "COP_MCP_AUTH_TOKEN")
    our_thief_c = client(our_thief, "thief", "THIEF_MCP_AUTH_TOKEN")
    their_cop_c = client(their_cop, "cop", "PEER_COP_MCP_AUTH_TOKEN")
    their_thief_c = client(their_thief, "thief", "PEER_THIEF_MCP_AUTH_TOKEN")
    half = int(config.get("num_games")) // 2

    def clients_for(index: int):
        cop_group = g1 if index <= half else g2
        thief_group = g2 if index <= half else g1
        auth = our_cop_c if cop_group == my_group else their_cop_c
        mirror = our_thief_c if thief_group == my_group else their_thief_c
        return auth, mirror

    log.info("playing as %s (cop=%s thief=%s | partner cop=%s thief=%s)",
             my_group, our_cop, our_thief, their_cop, their_thief)
    side = RemoteSide(config, my_group, clients_for, group_1=g1, group_2=g2,
                      results_dir=args.results_dir)
    try:
        side.play_series()
    finally:
        for t in transports.values():
            t.close()

    sdk = CopThiefSDK(config)
    report = sdk.build_bonus_report(side.outcome())
    (side.series_dir / "bonus_report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    for r in side.results:
        print(f"  sub-game {r.index}: winner={r.winner.value} moves={r.moves_played} "
              f"cop={r.cop_score} thief={r.thief_score}", file=sys.stderr)
    print(f"  totals: {report['totals_by_group']} | logs: {side.series_dir}", file=sys.stderr)

    if args.send:
        creds = config.get("report.credentials_file", "credentials.json")
        if Path(creds).exists():
            msg_id = sdk.send_report(report, sdk.gmail_reporter())
            print(f"  emailed §9.2 report to {config.get('report.recipient')} (id={msg_id})",
                  file=sys.stderr)
        else:
            print(f"  --send set but {creds} not found; report written but NOT emailed "
                  "(see docs/PRD_gmail_reporting.md to set up OAuth)", file=sys.stderr)

    print(json.dumps(report))


if __name__ == "__main__":
    main()
