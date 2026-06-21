"""Engine rules/movement/scoring/referee tests (PRD_game_engine §5)."""

from __future__ import annotations

from cop_thief.constants import GameStatus
from cop_thief.domain.action import Action
from cop_thief.domain.barrier import Barrier
from cop_thief.domain.position import Position
from cop_thief.domain.roles import PlayerRole
from cop_thief.engine.referee import Referee
from cop_thief.engine.scoring import score_sub_game

SCORING = {"cop_win": 20, "thief_win": 10, "cop_loss": 5, "thief_loss": 5}


def make_referee(grid=(5, 5), max_moves=25, max_barriers=5, vision=2) -> Referee:
    return Referee(list(grid), max_moves, max_barriers, SCORING, vision)


def test_t1_thief_moves_first():
    ref = make_referee()
    ref.reset(cop=Position(0, 0), thief=Position(4, 4))
    # Cop acting first is rejected (out of turn), game not ended.
    res = ref.apply(PlayerRole.COP, Action.move(Position(1, 1)))
    assert res.accepted is False
    assert res.terminal is False


def test_t2_capture_cop_onto_thief():
    ref = make_referee()
    ref.reset(cop=Position(2, 1), thief=Position(2, 2))
    ref.apply(PlayerRole.THIEF, Action.move(Position(3, 2)))  # thief steps away
    res = ref.apply(PlayerRole.COP, Action.move(Position(3, 2)))  # cop captures
    assert res.capture is True
    assert res.status is GameStatus.COP_WIN
    assert score_sub_game(SCORING, PlayerRole.COP) == (20, 5)


def test_t3_thief_survives_25_moves():
    ref = make_referee()
    ref.reset(cop=Position(0, 0), thief=Position(4, 4))
    thief_cells = [Position(4, 3), Position(4, 4)]
    cop_cells = [Position(0, 1), Position(0, 0)]
    status = GameStatus.ONGOING
    for i in range(25):
        assert ref.apply(PlayerRole.THIEF, Action.move(thief_cells[i % 2])).status
        res = ref.apply(PlayerRole.COP, Action.move(cop_cells[i % 2]))
        status = res.status
    assert status is GameStatus.THIEF_WIN
    assert score_sub_game(SCORING, PlayerRole.THIEF) == (5, 10)


def test_t4_diagonal_move_accepted():
    ref = make_referee()
    ref.reset(cop=Position(0, 0), thief=Position(4, 4))
    res = ref.apply(PlayerRole.THIEF, Action.move(Position(3, 3)))
    assert res.accepted is True


def test_t5_two_cell_move_rejected_and_loses():
    ref = make_referee()
    ref.reset(cop=Position(0, 0), thief=Position(4, 4))
    res = ref.apply(PlayerRole.THIEF, Action.move(Position(4, 2)))
    assert res.accepted is False
    assert res.status is GameStatus.COP_WIN  # thief's illegal move loses


def test_t6_sixth_barrier_rejected_and_cop_loses():
    ref = make_referee(max_barriers=5)
    state = ref.reset(cop=Position(2, 2), thief=Position(0, 0))
    state.barriers = [Barrier(Position(4, c), PlayerRole.COP, 0) for c in range(5)]
    state.turn = PlayerRole.COP
    res = ref.apply(PlayerRole.COP, Action.barrier(Position(2, 2)))
    assert res.accepted is False
    assert res.status is GameStatus.THIEF_WIN


def test_t7_thief_cannot_place_barrier():
    ref = make_referee()
    ref.reset(cop=Position(0, 0), thief=Position(4, 4))
    res = ref.apply(PlayerRole.THIEF, Action.barrier(Position(4, 4)))
    assert res.accepted is False
    assert res.status is GameStatus.COP_WIN


def test_t8_step_into_barrier_loses():
    ref = make_referee()
    state = ref.reset(cop=Position(0, 0), thief=Position(2, 2))
    state.barriers = [Barrier(Position(2, 3), PlayerRole.COP, 0)]
    res = ref.apply(PlayerRole.THIEF, Action.move(Position(2, 3)))
    assert res.accepted is False
    assert res.status is GameStatus.COP_WIN


def test_t9_cop_barrier_on_thief_or_existing_rejected():
    ref = make_referee()
    state = ref.reset(cop=Position(2, 2), thief=Position(2, 3))
    state.turn = PlayerRole.COP
    valid, _ = ref.validate(PlayerRole.COP, Action.barrier(Position(2, 3)))
    assert valid is False  # not on own cell / on thief
    state.barriers = [Barrier(Position(2, 2), PlayerRole.COP, 0)]
    valid2, _ = ref.validate(PlayerRole.COP, Action.barrier(Position(2, 2)))
    assert valid2 is False  # already a barrier


def test_t10_adjacent_move_is_not_capture():
    ref = make_referee()
    ref.reset(cop=Position(0, 0), thief=Position(2, 2))
    res = ref.apply(PlayerRole.THIEF, Action.move(Position(1, 1)))
    assert res.capture is False
    assert res.status is GameStatus.ONGOING


def test_t11_off_board_move_rejected_and_loses():
    ref = make_referee()
    ref.reset(cop=Position(0, 0), thief=Position(4, 4))
    res = ref.apply(PlayerRole.THIEF, Action.move(Position(5, 5)))
    assert res.accepted is False
    assert res.status is GameStatus.COP_WIN


def test_cop_barrier_then_must_move_off():
    ref = make_referee()
    ref.reset(cop=Position(2, 2), thief=Position(0, 0))
    ref.apply(PlayerRole.THIEF, Action.move(Position(0, 1)))
    res = ref.apply(PlayerRole.COP, Action.barrier(Position(2, 2)))
    assert res.accepted is True
    assert ref.state.barriers_placed() == 1
    assert ref.state.is_barrier(Position(2, 2))


def test_no_state_raises():
    ref = make_referee()
    try:
        ref.observe(PlayerRole.COP)
    except RuntimeError as exc:
        assert "reset" in str(exc)
    else:
        raise AssertionError("expected RuntimeError")
