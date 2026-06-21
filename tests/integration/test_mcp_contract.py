"""MCP tool contract tests (PRD_mcp_servers §5)."""

from __future__ import annotations

import jsonschema

from cop_thief.agents.agent_client import AgentClient, InProcessTransport
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
