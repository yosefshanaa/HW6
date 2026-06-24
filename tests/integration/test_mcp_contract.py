"""MCP tool contract tests (PRD_mcp_servers §5)."""

from __future__ import annotations

import jsonschema
import pytest

from cop_thief.agents.agent_client import AgentClient, HttpTransport, InProcessTransport
from cop_thief.constants import GameStatus
from cop_thief.domain.position import Position
from cop_thief.engine.referee import Referee
from cop_thief.mcp import tools
from cop_thief.mcp.contracts import OBSERVATION_SCHEMA

SCORING = {"cop_win": 20, "thief_win": 10, "cop_loss": 5, "thief_loss": 5}


def make_referee(cop=(0, 0), thief=(4, 4)) -> Referee:
    ref = Referee([5, 5], 25, 5, SCORING, 2)
    ref.reset(Position(*cop), Position(*thief))
    return ref


def turn_payload(role, to, kind="move", sub_game=1, move=0):
    return {
        "sub_game": sub_game,
        "move_number": move,
        "role": role,
        "message": "advancing",
        "action": {"type": kind, "to": list(to)},
    }


def test_health_check_reports_version():
    assert tools.health_check() == {"ok": True, "version": "1.00"}


def test_get_observation_matches_schema_and_hides_opponent():
    ref = make_referee(cop=(0, 0), thief=(4, 4))
    obs = tools.get_observation(ref, "cop")
    jsonschema.validate(obs, OBSERVATION_SCHEMA)
    assert obs["visible_opponent"] is None  # outside radius 2


def test_submit_turn_accepts_legal_action():
    ref = make_referee()
    res = tools.submit_turn(ref, turn_payload("thief", (3, 3)))
    assert res["accepted"] is True
    assert res["terminal"] is False


def test_submit_turn_rejects_illegal_action_and_loses():
    ref = make_referee()
    res = tools.submit_turn(ref, turn_payload("thief", (2, 2)))  # too far
    assert res["accepted"] is False
    assert res["status"] == GameStatus.COP_WIN.value


def test_submit_turn_rejects_malformed_payload_without_crashing():
    ref = make_referee()
    res = tools.submit_turn(ref, {"role": "thief"})  # missing required fields
    assert res["accepted"] is False
    assert "malformed payload" in res["reason"]


def test_validate_action_tool():
    ref = make_referee()
    ok = tools.validate_action(ref, "thief", {"type": "move", "to": [3, 3]})
    assert ok["valid"] is True
    bad = tools.validate_action(ref, "thief", {"type": "move", "to": [0, 0]})
    assert bad["valid"] is False


def test_get_match_status_shape():
    ref = make_referee()
    status = tools.get_match_status(ref)
    assert set(status) == {"status", "thief_moves", "turn", "cop", "thief"}


def test_agent_client_round_trip_over_transport():
    ref = make_referee(cop=(0, 0), thief=(2, 2))
    transport = InProcessTransport(ref)
    cop = AgentClient(transport, "cop")
    thief = AgentClient(transport, "thief")
    assert thief.health()["ok"] is True
    # Thief sees the Cop (within radius 2) and submits a legal move.
    assert thief.observe()["visible_opponent"] == [0, 0]
    res = thief.submit(turn_payload("thief", (3, 3)))
    assert res["accepted"] is True
    thief.send_message("you'll never catch me")
    assert transport.inbox[0]["message"] == "you'll never catch me"
    assert cop.status()["turn"] == "cop"


def test_reset_tool_starts_a_new_subgame():
    ref = make_referee(cop=(0, 0), thief=(4, 4))
    tools.submit_turn(ref, turn_payload("thief", (3, 3)))  # dirty the state
    res = tools.reset(ref, [1, 1], [3, 3])
    assert res["ok"] is True
    status = tools.get_match_status(ref)
    assert (status["cop"], status["thief"], status["thief_moves"]) == ([1, 1], [3, 3], 0)


def test_reset_tool_rejects_bad_positions_without_crashing():
    ref = make_referee()
    res = tools.reset(ref, [2, 2], [2, 2])  # same cell is illegal
    assert res["ok"] is False and res["reason"]


def test_get_messages_read_back_and_reset_clears_inbox():
    transport = InProcessTransport(make_referee())
    cop = AgentClient(transport, "cop")
    assert cop.messages() == []                      # empty to start
    cop.transport.call("receive_message", from_role="thief", message="going north")
    assert cop.messages() == [{"from": "thief", "message": "going north"}]
    cop.reset([0, 0], [4, 4])
    assert cop.messages() == []                      # reset wipes the bluff inbox


# --- Networked path: the HTTP client transport against an in-memory FastMCP app ---
fastmcp = pytest.importorskip("fastmcp")


def _app(role: str):
    from cop_thief.mcp.server_app import build_app
    from cop_thief.shared.config import load_config

    return build_app(role, load_config())


def test_http_transport_round_trip_in_memory():
    # Same AgentClient code path as a real URL, but in-memory (no socket).
    transport = HttpTransport(_app("cop"))
    try:
        cop = AgentClient(transport, "cop")
        assert cop.health()["ok"] is True
        assert cop.reset([0, 0], [4, 4])["ok"] is True
        obs = cop.observe()
        assert obs["role"] == "cop" and obs["own_cell"] == [0, 0]
        res = AgentClient(transport, "thief").submit(turn_payload("thief", (3, 4)))
        assert res["accepted"] is True
        assert cop.status()["thief"] == [3, 4]
    finally:
        transport.close()


def test_http_transport_observation_is_role_bound_no_fog_leak():
    # A cop-role server only ever reveals the cop's legal view, even to a thief client.
    transport = HttpTransport(_app("cop"))
    try:
        transport.call("reset", cop=[0, 0], thief=[4, 4])
        assert AgentClient(transport, "thief").observe()["role"] == "cop"
    finally:
        transport.close()


def test_http_transport_rejects_unknown_tool():
    transport = HttpTransport(_app("cop"))
    try:
        with pytest.raises(ValueError, match="unknown tool"):
            transport.call("definitely_not_a_tool")
    finally:
        transport.close()


def test_http_transport_message_channel_round_trip():
    # Deliver a bluff and read it back over the HTTP client (the cross-team path).
    transport = HttpTransport(_app("cop"))
    try:
        transport.call("reset", cop=[0, 0], thief=[4, 4])
        transport.call("receive_message", from_role="thief", message="bluff: heading north")
        assert AgentClient(transport, "cop").messages() == [
            {"from": "thief", "message": "bluff: heading north"}
        ]
        transport.call("reset", cop=[0, 0], thief=[4, 4])      # new sub-game
        assert AgentClient(transport, "cop").messages() == []  # inbox cleared
    finally:
        transport.close()
