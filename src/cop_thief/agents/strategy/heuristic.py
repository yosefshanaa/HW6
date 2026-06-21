"""Baseline heuristic Cop/Thief strategies (PRD_agent_strategy §2.2)."""

from __future__ import annotations

from cop_thief.agents.strategy.base import Strategy, grid_center
from cop_thief.domain.action import Action
from cop_thief.domain.observation import Observation
from cop_thief.domain.position import Position
from cop_thief.domain.roles import PlayerRole


def _reference(obs: Observation, memory: dict) -> Position | None:
    """Best estimate of the opponent: visible cell, else last-known from memory."""
    if obs.visible_opponent is not None:
        return obs.visible_opponent
    last = memory.get("last_known_opponent")
    return last


class HeuristicCop(Strategy):
    """Pursuit: minimise Chebyshev distance to the (believed) Thief cell."""

    def __init__(self) -> None:
        super().__init__(PlayerRole.COP)

    def _select(self, obs: Observation, cells: list[Position], memory: dict) -> Position:
        target = _reference(obs, memory) or grid_center(obs.grid_size)
        return min(cells, key=lambda c: (c.chebyshev(target), c.row, c.col))

    def compose_message(self, obs: Observation, action: Action, memory: dict) -> str:
        return f"Cop closing in toward {action.to.as_list()}."


class HeuristicThief(Strategy):
    """Evasion: maximise Chebyshev distance from the (believed) Cop cell."""

    def __init__(self) -> None:
        super().__init__(PlayerRole.THIEF)

    def _select(self, obs: Observation, cells: list[Position], memory: dict) -> Position:
        ref = _reference(obs, memory)
        if ref is None:
            ref = grid_center(obs.grid_size)  # drift to centre when blind
            return min(cells, key=lambda c: (c.chebyshev(ref), c.row, c.col))
        return max(cells, key=lambda c: (c.chebyshev(ref), -c.row, -c.col))

    def compose_message(self, obs: Observation, action: Action, memory: dict) -> str:
        # Bluff: name a plausible but different corner to mislead the Cop.
        decoy = Position(0, 0) if action.to.row > 0 else Position(obs.grid_size[0] - 1, 0)
        return f"Thief slipping toward {decoy.as_list()}."


def make_strategy(role: PlayerRole, name: str = "heuristic") -> Strategy:
    """Factory for a strategy by role and name."""
    if name != "heuristic":
        raise ValueError(f"unknown strategy: {name}")
    return HeuristicCop() if role is PlayerRole.COP else HeuristicThief()
