"""Grid position with [row, col] convention (PLAN §5, shared rules §2.3)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from cop_thief.constants import KING_MOVES


@dataclass(frozen=True)
class Position:
    """A cell on the grid. Origin [0,0] top-left; rows down, cols right."""

    row: int
    col: int

    def chebyshev(self, other: Position) -> int:
        """King-move (Chebyshev) distance to another position."""
        return max(abs(self.row - other.row), abs(self.col - other.col))

    def in_bounds(self, grid_size: Sequence[int]) -> bool:
        """Whether this cell lies inside ``grid_size`` = [rows, cols]."""
        rows, cols = grid_size[0], grid_size[1]
        return 0 <= self.row < rows and 0 <= self.col < cols

    def neighbors8(self) -> list[Position]:
        """The eight king-move neighbours (unfiltered by bounds/barriers)."""
        return [Position(self.row + dr, self.col + dc) for dr, dc in KING_MOVES]

    def is_king_step_to(self, other: Position) -> bool:
        """True iff ``other`` is exactly one king move away (not equal)."""
        return self != other and self.chebyshev(other) == 1

    def as_list(self) -> list[int]:
        """Serialize to ``[row, col]``."""
        return [self.row, self.col]

    @classmethod
    def from_list(cls, pair: Sequence[int]) -> Position:
        """Build from a ``[row, col]`` pair."""
        return cls(int(pair[0]), int(pair[1]))
