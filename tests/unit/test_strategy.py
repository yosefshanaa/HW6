"""Heuristic strategy + Q-table tests (PRD_agent_strategy §5)."""

from __future__ import annotations

import pytest

from cop_thief.agents.strategy.heuristic import make_strategy
from cop_thief.agents.strategy.q_table import QTable
from cop_thief.constants import ActionType
from cop_thief.domain.observation import Observation
from cop_thief.domain.position import Position
from cop_thief.domain.roles import PlayerRole
from cop_thief.engine.referee import Referee

SCORING = {"cop_win": 20, "thief_win": 10, "cop_loss": 5, "thief_loss": 5}


def obs(role, own, opponent=None, barriers=None, radius=2):
    return Observation(
        role=role,
        own_cell=own,
        move_number=0,
        vision_radius=radius,
        grid_size=[5, 5],
        visible_opponent=opponent,
        visible_barriers=barriers or [],
    )


def test_cop_closes_distance_when_opponent_visible():
    # Opponent two cells away in open space (not on an edge) -> pursue, not wall.
    o = obs(PlayerRole.COP, Position(1, 1), opponent=Position(3, 3))
    action = make_strategy(PlayerRole.COP).decide(o, {})
    assert action.type is ActionType.MOVE
    assert action.to.chebyshev(Position(3, 3)) < Position(1, 1).chebyshev(Position(3, 3))


def test_cop_places_barrier_to_herd_edge_pinned_thief():
    o = obs(PlayerRole.COP, Position(4, 2), opponent=Position(4, 4))  # thief on edge, d=2
    memory = {"max_barriers": 5}
    action = make_strategy(PlayerRole.COP).decide(o, memory)
    assert action.type is ActionType.BARRIER
    assert action.to == Position(4, 2)              # barrier is on the Cop's own cell
    assert memory["barriers_placed"] == 1
    # ...and the engine agrees it is a legal action.
    ref = Referee([5, 5], 25, 5, SCORING, 2)
    ref.reset(cop=Position(4, 2), thief=Position(4, 4))
    valid, _ = ref.validate(PlayerRole.COP, action)
    assert valid is True


def test_cop_prefers_capture_over_barrier():
    o = obs(PlayerRole.COP, Position(4, 3), opponent=Position(4, 4))  # adjacent + edge
    action = make_strategy(PlayerRole.COP).decide(o, {"max_barriers": 5})
    assert action.type is ActionType.MOVE
    assert action.to == Position(4, 4)              # capture, never wall away a win


def test_cop_moves_when_barrier_not_useful_open_board():
    o = obs(PlayerRole.COP, Position(1, 1), opponent=Position(3, 3))  # d=2 but not on edge
    action = make_strategy(PlayerRole.COP).decide(o, {"max_barriers": 5})
    assert action.type is ActionType.MOVE


def test_cop_no_barrier_when_budget_exhausted():
    o = obs(PlayerRole.COP, Position(4, 2), opponent=Position(4, 4))
    action = make_strategy(PlayerRole.COP).decide(o, {"max_barriers": 5, "barriers_placed": 5})
    assert action.type is ActionType.MOVE


def test_cop_no_barrier_when_it_would_self_trap():
    # Only one legal exit -> placing a barrier on our cell would risk a trap; move instead.
    o = obs(PlayerRole.COP, Position(0, 0), opponent=Position(0, 2),
            barriers=[Position(0, 1), Position(1, 1)])
    action = make_strategy(PlayerRole.COP).decide(o, {"max_barriers": 5})
    assert action.type is ActionType.MOVE


def test_thief_opens_distance_when_opponent_visible():
    o = obs(PlayerRole.THIEF, Position(2, 2), opponent=Position(2, 1))
    action = make_strategy(PlayerRole.THIEF).decide(o, {})
    assert action.to.chebyshev(Position(2, 1)) > Position(2, 2).chebyshev(Position(2, 1))


def test_decision_is_always_legal():
    barriers = [Position(1, 1), Position(1, 2), Position(2, 1)]
    o = obs(PlayerRole.THIEF, Position(2, 2), opponent=Position(0, 0), barriers=barriers)
    action = make_strategy(PlayerRole.THIEF).decide(o, {})
    assert action.to.in_bounds([5, 5])
    assert action.to not in barriers


def test_blind_agent_still_returns_legal_move():
    o = obs(PlayerRole.COP, Position(0, 0))  # no opponent visible, no memory
    action = make_strategy(PlayerRole.COP).decide(o, {})
    assert action.to in Position(0, 0).neighbors8()


def test_cop_uses_last_known_from_memory_when_blind():
    o = obs(PlayerRole.COP, Position(0, 0))
    memory = {"last_known_opponent": Position(4, 4)}
    action = make_strategy(PlayerRole.COP).decide(o, memory)
    assert action.to.chebyshev(Position(4, 4)) < Position(0, 0).chebyshev(Position(4, 4))


def test_unknown_strategy_raises():
    with pytest.raises(ValueError):
        make_strategy(PlayerRole.COP, "deep-rl")


def test_q_table_bellman_update():
    q = QTable(num_actions=4, learning_rate=0.1, discount_factor=0.9)
    new = q.update(state=0, action=1, reward=1.0, next_state=2, done=False)
    assert new == pytest.approx(0.1)
    # With a non-zero next-state value, the target grows by gamma * best_next.
    q.q[(2, 0)] = 1.0
    new2 = q.update(state=0, action=1, reward=1.0, next_state=2, done=False)
    assert new2 > new
    assert q.best_action(2) == 0
