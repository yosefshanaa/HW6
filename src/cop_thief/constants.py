"""Immutable, non-configurable project constants (guidelines §7.3).

Configurable values (grid size, scoring, radii, …) live in config files, not
here. This module holds only fixed enums/literals that never change.
"""

from __future__ import annotations

from enum import Enum

# The eight king-move offsets (row, col): orthogonal + diagonal.
KING_MOVES: tuple[tuple[int, int], ...] = (
    (-1, -1), (-1, 0), (-1, 1),
    (0, -1),           (0, 1),
    (1, -1),  (1, 0),  (1, 1),
)


class ActionType(str, Enum):
    """The two structured action kinds an agent may commit."""

    MOVE = "move"
    BARRIER = "barrier"


class GameStatus(str, Enum):
    """Lifecycle status of a sub-game."""

    ONGOING = "ongoing"
    COP_WIN = "cop_win"
    THIEF_WIN = "thief_win"


class ReportType(str, Enum):
    """Report schema variants (assignment §9.1 / §9.2)."""

    INTERNAL = "internal"
    BONUS = "bonus_game"
