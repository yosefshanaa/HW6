"""Strategy base class (Template Method) + shared helpers (PRD_agent_strategy)."""

from __future__ import annotations

from abc import ABC, abstractmethod

from cop_thief.domain.action import Action
from cop_thief.domain.observation import Observation
from cop_thief.domain.position import Position
from cop_thief.domain.roles import PlayerRole


def legal_neighbor_cells(obs: Observation) -> list[Position]:
    """In-bounds king neighbours of the own cell that are not visible barriers."""
    blocked = set(obs.visible_barriers)
    return [
        c
        for c in obs.own_cell.neighbors8()
        if c.in_bounds(obs.grid_size) and c not in blocked
    ]


def grid_center(grid_size: list[int]) -> Position:
    """Centre cell of the grid (used as a default search target)."""
    return Position(grid_size[0] // 2, grid_size[1] // 2)


def mobility(cell: Position, obs: Observation) -> int:
    """Count of legal king-moves out of ``cell`` (open space = more escape routes)."""
    blocked = set(obs.visible_barriers)
    return sum(
        1 for n in cell.neighbors8() if n.in_bounds(obs.grid_size) and n not in blocked
    )


def on_edge(pos: Position, grid_size: list[int]) -> bool:
    """Whether ``pos`` sits on a board edge (row/col is first or last)."""
    return pos.row in (0, grid_size[0] - 1) or pos.col in (0, grid_size[1] - 1)


class Strategy(ABC):
    """Decides a legal action from a partial observation.

    ``decide`` is a Template Method: it computes legal neighbours and delegates
    the choice to ``_select`` (implemented per role). It always returns an
    action; if the agent is fully boxed in it moves onto its own cell, which the
    referee treats as illegal and the orchestrator replaces with a safe move.
    """

    def __init__(self, role: PlayerRole) -> None:
        self.role = role

    def decide(self, obs: Observation, memory: dict) -> Action:
        """Return a legal-by-construction move action."""
        cells = legal_neighbor_cells(obs)
        if not cells:
            return Action.move(obs.own_cell)
        return Action.move(self._select(obs, cells, memory))

    @abstractmethod
    def _select(self, obs: Observation, cells: list[Position], memory: dict) -> Position:
        """Choose a target cell among the legal ``cells``."""

    def compose_message(self, obs: Observation, action: Action, memory: dict) -> str:
        """A short natural-language message accompanying the action."""
        return f"{self.role.value} to {action.to.as_list()}."
