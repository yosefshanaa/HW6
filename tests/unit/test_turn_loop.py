"""Turn-loop safe-fallback test (PLAN §10/§11: never stall)."""

from __future__ import annotations

from cop_thief.agents.strategy.base import Strategy
from cop_thief.domain.action import Action
from cop_thief.domain.position import Position
from cop_thief.domain.roles import PlayerRole
from cop_thief.engine.referee import Referee
from cop_thief.orchestrator.turn_loop import play_turn
from cop_thief.shared.replay import ReplayStore

SCORING = {"cop_win": 20, "thief_win": 10, "cop_loss": 5, "thief_loss": 5}


class IllegalStrategy(Strategy):
    """Always proposes an off-board / too-far (illegal) move."""

    def _select(self, obs, cells, memory):  # pragma: no cover - overridden
        return cells[0]

    def decide(self, obs, memory):
        return Action.move(Position(obs.own_cell.row, obs.own_cell.col + 3))


def test_illegal_action_falls_back_to_legal_move(tmp_path):
    ref = Referee([5, 5], 25, 5, SCORING, 2)
    ref.reset(cop=Position(0, 0), thief=Position(2, 2))
    store = ReplayStore(tmp_path / "t.jsonl")
    result = play_turn(
        ref, PlayerRole.THIEF, IllegalStrategy(PlayerRole.THIEF), {}, {}, 1, store
    )
    assert result.accepted is True          # fallback rescued the turn
    assert result.terminal is False
    record = store.load()[0]
    assert "fallback" in record["validation"]["reason"]


class BluffStrategy(Strategy):
    """Honest legal action, deceptive message claiming the opposite cell."""

    def _select(self, obs, cells, memory):
        return Position(obs.own_cell.row, obs.own_cell.col + 1)

    def compose_message(self, obs, action, memory):
        return "I am fleeing far to the north-west corner [0, 0]!"  # a lie


def test_bluff_message_does_not_change_outcome(tmp_path):
    ref = Referee([5, 5], 25, 5, SCORING, 2)
    ref.reset(cop=Position(0, 0), thief=Position(2, 2))
    store = ReplayStore(tmp_path / "b.jsonl")
    play_turn(ref, PlayerRole.THIEF, BluffStrategy(PlayerRole.THIEF), {}, {}, 1, store)
    # Referee acted on the action (move to [2,3]), not on the bluffing text.
    assert ref.state.thief == Position(2, 3)
    record = store.load()[0]
    assert "north-west" in record["message"]          # bluff is logged verbatim
    assert record["action"]["to"] == [2, 3]           # but adjudication used the action
