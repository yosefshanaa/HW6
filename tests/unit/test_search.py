"""Minimax search tests: strong play + legal-by-construction (no network)."""

from __future__ import annotations

import random

from cop_thief.agents.strategy.search import search_action
from cop_thief.constants import ActionType
from cop_thief.domain.barrier import Barrier
from cop_thief.domain.game_state import GameState
from cop_thief.domain.observation import Observation
from cop_thief.domain.position import Position
from cop_thief.domain.roles import PlayerRole
from cop_thief.engine import rules

KW = {"max_moves": 25, "max_barriers": 5, "depth": 6}


def obs(role, own, opp, barriers=None, mv=0, grid=(5, 5), rad=2):
    return Observation(
        role=role, own_cell=own, move_number=mv, vision_radius=rad,
        grid_size=list(grid), visible_opponent=opp, visible_barriers=barriers or [],
    )


def test_blind_search_returns_none():
    # No visible opponent -> search defers (caller uses the belief heuristic).
    assert search_action(PlayerRole.COP, obs(PlayerRole.COP, Position(0, 0), None),
                         {}, **KW) is None


def test_cop_takes_immediate_capture():
    a = search_action(PlayerRole.COP, obs(PlayerRole.COP, Position(2, 2), Position(3, 3)),
                      {}, **KW)
    assert a.type is ActionType.MOVE and a.to == Position(3, 3)


def test_cop_closes_distance_from_afar():
    a = search_action(PlayerRole.COP, obs(PlayerRole.COP, Position(0, 0), Position(2, 2)),
                      {}, **KW)
    assert a.to.chebyshev(Position(2, 2)) < Position(0, 0).chebyshev(Position(2, 2))


def test_thief_keeps_uncapturable_distance():
    # Cop adjacent: the thief must step to a cell the cop cannot reach next turn.
    a = search_action(PlayerRole.THIEF, obs(PlayerRole.THIEF, Position(2, 2), Position(1, 1)),
                      {}, **KW)
    assert a.to != Position(1, 1)                 # never step onto the cop
    assert a.to.chebyshev(Position(1, 1)) >= 2    # uncapturable next turn


def test_cop_can_place_a_barrier_when_it_is_the_only_legal_action():
    # Cop walled in on all sides but with budget -> the only legal action is a barrier.
    walls = list(Position(2, 2).neighbors8())
    a = search_action(PlayerRole.COP, obs(PlayerRole.COP, Position(2, 2), Position(4, 4),
                                          barriers=walls), {}, **KW)
    assert a is not None and a.type is ActionType.BARRIER and a.to == Position(2, 2)


def _state(cop, thief, barriers, placed, turn):
    st = GameState(grid_size=[5, 5], cop=cop, thief=thief, max_moves=25, max_barriers=5)
    st.barriers = [Barrier(b, PlayerRole.COP, 0) for b in barriers]
    st.turn = turn
    return st


def test_search_actions_are_always_legal():
    # Property test: across random visible positions, every action the search
    # returns passes the referee's own legality rules (never forfeits a sub-game).
    rng = random.Random(7)
    cells = [Position(r, c) for r in range(5) for c in range(5)]
    checked = 0
    for _ in range(300):
        cop, thief = rng.sample(cells, 2)
        if cop.chebyshev(thief) > 2:      # must be visible at r2 for search to engage
            continue
        pool = [c for c in cells if c not in (cop, thief)]
        barriers = rng.sample(pool, rng.randint(0, 4))
        placed = rng.randint(0, 5)
        role = rng.choice([PlayerRole.COP, PlayerRole.THIEF])
        own = cop if role is PlayerRole.COP else thief
        mem = {"barriers_placed": placed}
        a = search_action(role, obs(role, own, cop if role is PlayerRole.THIEF else thief,
                                    barriers=barriers), mem, **KW)
        if a is None:
            continue
        state = _state(cop, thief, barriers, placed, role)
        valid, reason = rules.validate(state, role, a)
        assert valid, f"illegal {a} for {role} ({reason})"
        checked += 1
    assert checked > 50  # sanity: the property actually exercised the search
