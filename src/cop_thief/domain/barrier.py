"""Barrier placed by the Cop (PLAN §5, PRD_game_engine §2.3)."""

from __future__ import annotations

from dataclasses import dataclass

from cop_thief.domain.position import Position
from cop_thief.domain.roles import PlayerRole


@dataclass(frozen=True)
class Barrier:
    """An impassable cell. Placed by the Cop; blocks both players."""

    cell: Position
    placed_by: PlayerRole
    move_number: int
