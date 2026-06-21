"""Movement helper tests (PRD_game_engine §2.2)."""

from __future__ import annotations

from cop_thief.domain.barrier import Barrier
from cop_thief.domain.position import Position
from cop_thief.domain.roles import PlayerRole
from cop_thief.engine.movement import legal_move_targets
from cop_thief.engine.referee import Referee

SCORING = {"cop_win": 20, "thief_win": 10, "cop_loss": 5, "thief_loss": 5}


def test_corner_has_three_targets():
    state = Referee([5, 5], 25, 5, SCORING, 2).reset(Position(0, 0), Position(4, 4))
    targets = legal_move_targets(state, Position(0, 0))
    assert len(targets) == 3
    assert set(targets) == {Position(0, 1), Position(1, 0), Position(1, 1)}


def test_barriers_excluded_from_targets():
    state = Referee([5, 5], 25, 5, SCORING, 2).reset(Position(0, 0), Position(4, 4))
    state.barriers = [Barrier(Position(0, 1), PlayerRole.COP, 0)]
    targets = legal_move_targets(state, Position(0, 0))
    assert Position(0, 1) not in targets
    assert len(targets) == 2
