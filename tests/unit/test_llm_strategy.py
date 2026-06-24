"""Hybrid LLM strategy tests: the legal-guard + fallback contract (no network)."""

from __future__ import annotations

import json

import pytest

from cop_thief.agents.strategy.base import legal_neighbor_cells
from cop_thief.agents.strategy.heuristic import make_strategy
from cop_thief.agents.strategy.llm_factory import build_llm_strategy
from cop_thief.agents.strategy.llm_strategy import LlmStrategy, _extract_json, _to_pos
from cop_thief.constants import ActionType
from cop_thief.domain.observation import Observation
from cop_thief.domain.position import Position
from cop_thief.domain.roles import PlayerRole
from cop_thief.shared.config import load_config


class StubClient:
    """An ``LlmClient`` stand-in returning a canned reply (or raising)."""

    def __init__(self, reply):
        self.reply = reply
        self.calls: list[tuple] = []

    def complete(self, prompt, system=None):
        self.calls.append((prompt, system))
        if isinstance(self.reply, Exception):
            raise self.reply
        return self.reply


def obs(role, own, opponent=None, barriers=None, radius=2):
    return Observation(
        role=role, own_cell=own, move_number=1, vision_radius=radius,
        grid_size=[5, 5], visible_opponent=opponent, visible_barriers=barriers or [],
    )


def _strat(role, reply):
    return LlmStrategy(role, StubClient(reply), fallback=make_strategy(role))


def test_valid_llm_move_is_used_with_its_message():
    o = obs(PlayerRole.THIEF, Position(2, 2), opponent=Position(0, 0))
    reply = json.dumps({"move": [3, 3], "say": "heading to [0,4]"})  # legal + a bluff
    strat = _strat(PlayerRole.THIEF, reply)
    mem: dict = {}
    action = strat.decide(o, mem)
    assert action.type is ActionType.MOVE
    assert action.to == Position(3, 3)
    assert strat.compose_message(o, action, mem) == "heading to [0,4]"


def test_cop_barrier_decision_consumes_budget():
    o = obs(PlayerRole.COP, Position(2, 2), opponent=Position(4, 2))
    strat = _strat(PlayerRole.COP, json.dumps({"barrier": True, "move": [1, 1], "say": "wall"}))
    mem = {"max_barriers": 5}
    action = strat.decide(o, mem)
    assert action.type is ActionType.BARRIER
    assert action.to == Position(2, 2)
    assert mem["barriers_placed"] == 1


def test_illegal_move_falls_back_but_keeps_message():
    o = obs(PlayerRole.COP, Position(2, 2), opponent=Position(3, 3))
    strat = _strat(PlayerRole.COP, json.dumps({"move": [4, 4], "say": "bluffing"}))  # not adjacent
    mem: dict = {}
    action = strat.decide(o, mem)
    assert action.to in legal_neighbor_cells(o)         # guarded to a legal cell
    assert strat.compose_message(o, action, mem) == "bluffing"  # model's message kept


def test_garbage_reply_uses_full_heuristic_fallback():
    o = obs(PlayerRole.THIEF, Position(2, 2), opponent=Position(1, 1))
    strat = _strat(PlayerRole.THIEF, "not json at all")
    mem: dict = {}
    action = strat.decide(o, mem)
    assert action.type is ActionType.MOVE
    assert action.to in legal_neighbor_cells(o)
    assert isinstance(strat.compose_message(o, action, mem), str)


def test_client_exception_never_stalls_the_turn():
    o = obs(PlayerRole.COP, Position(0, 0), opponent=Position(2, 2))
    strat = _strat(PlayerRole.COP, ConnectionError("boom"))
    action = strat.decide(o, {})
    assert action.to in legal_neighbor_cells(o)


def test_extract_json_tolerates_surrounding_prose():
    assert _extract_json('here you go: {"move": [1, 2]} thanks') == {"move": [1, 2]}
    assert _extract_json("totally not json") is None


def test_to_pos_coercion():
    assert _to_pos([1, 2]) == Position(1, 2)
    assert _to_pos("nope") is None
    assert _to_pos([1, 2, 3]) is None


def test_factory_builds_llm_strategy_offline():
    cfg = load_config()  # config.yaml provider=openai; builds the closure, no network
    strat = build_llm_strategy(PlayerRole.COP, cfg, fallback=make_strategy(PlayerRole.COP))
    assert isinstance(strat, LlmStrategy)
    assert strat.role is PlayerRole.COP


def test_factory_rejects_unknown_provider(monkeypatch):
    cfg = load_config()
    monkeypatch.setitem(cfg.data["llm"], "provider", "nope")
    with pytest.raises(ValueError, match="unsupported llm provider"):
        build_llm_strategy(PlayerRole.THIEF, cfg, fallback=make_strategy(PlayerRole.THIEF))
