"""Networked match driver test: a full series across two in-memory MCP servers.

Exercises the exact RemoteMatch path used against live Cloud Run servers, but with
the FastMCP in-memory transport (no socket). Proves the two referees stay in sync
(zero reconcile flags) and a clean series + report-ready outcome is produced.
"""

from __future__ import annotations

import copy

import pytest

from cop_thief.agents.agent_client import AgentClient, HttpTransport
from cop_thief.domain.roles import PlayerRole
from cop_thief.match.remote_match import RemoteMatch
from cop_thief.mcp.server_app import build_app
from cop_thief.shared.config import Config, load_config

# Needs the optional ``mcp`` extra at runtime (build_app + HttpTransport use FastMCP).
pytest.importorskip("fastmcp")


def _match_config(num_games: int = 2):
    cfg = load_config()
    d = copy.deepcopy(cfg.data)
    d["vision_radius"] = 2
    d["agents"] = {"cop_strategy": "search", "thief_strategy": "search"}  # deterministic, no API
    d["num_games"] = num_games
    d["search"] = {"depth": 4}
    d["start_distance_min"] = None
    d["start_distance_max"] = None
    return Config(data=d, rate_limits=cfg.rate_limits)


def test_remote_match_full_series_over_in_memory_servers(tmp_path):
    cfg = _match_config(num_games=2)
    cop_t = HttpTransport(build_app("cop", cfg))
    thief_t = HttpTransport(build_app("thief", cfg))
    try:
        match = RemoteMatch(
            cfg, AgentClient(cop_t, "cop"), AgentClient(thief_t, "thief"),
            results_dir=tmp_path, group_1="us", group_2="them",
        )
        outcome = match.play_series()
    finally:
        cop_t.close()
        thief_t.close()

    assert len(outcome.results) == 2
    assert all(r.winner in (PlayerRole.COP, PlayerRole.THIEF) for r in outcome.results)
    assert all(1 <= r.moves_played <= cfg.get("max_moves") for r in outcome.results)
    assert outcome.flags == []                       # the two referees never diverged
    assert set(outcome.totals_by_group) == {"us", "them"}
    # Replay logs were written for each sub-game.
    assert len(list((tmp_path).glob("remote-*/sub_game_*.jsonl"))) == 2
