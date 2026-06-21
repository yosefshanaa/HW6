"""Authoritative game state for one sub-game (PLAN §5)."""

from __future__ import annotations

from dataclasses import dataclass, field

from cop_thief.constants import GameStatus
from cop_thief.domain.barrier import Barrier
from cop_thief.domain.position import Position
from cop_thief.domain.roles import PlayerRole


@dataclass
class GameState:
    """Mutable state owned exclusively by the Referee."""

    grid_size: list[int]
    cop: Position
    thief: Position
    max_moves: int
    max_barriers: int
    barriers: list[Barrier] = field(default_factory=list)
    thief_moves: int = 0          # completed Thief moves (= rounds)
    turn: PlayerRole = PlayerRole.THIEF   # Thief moves first
    status: GameStatus = GameStatus.ONGOING

    def position_of(self, role: PlayerRole) -> Position:
        """Current cell of ``role``."""
        return self.cop if role is PlayerRole.COP else self.thief

    def set_position(self, role: PlayerRole, pos: Position) -> None:
        """Move ``role`` to ``pos``."""
        if role is PlayerRole.COP:
            self.cop = pos
        else:
            self.thief = pos

    def barrier_cells(self) -> set[Position]:
        """Set of all impassable cells."""
        return {b.cell for b in self.barriers}

    def is_barrier(self, pos: Position) -> bool:
        """Whether ``pos`` is an impassable barrier cell."""
        return any(b.cell == pos for b in self.barriers)

    def barriers_placed(self) -> int:
        """How many barriers the Cop has placed this sub-game."""
        return len(self.barriers)

    def snapshot(self) -> dict:
        """JSON-ready snapshot of the current state (for logging/replay)."""
        return {
            "cop": self.cop.as_list(),
            "thief": self.thief.as_list(),
            "barriers": [b.cell.as_list() for b in self.barriers],
            "thief_moves": self.thief_moves,
            "turn": self.turn.value,
            "status": self.status.value,
        }
