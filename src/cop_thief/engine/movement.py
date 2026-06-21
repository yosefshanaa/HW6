"""8-directional movement helpers (PRD_game_engine §2.2)."""

from __future__ import annotations

from cop_thief.domain.game_state import GameState
from cop_thief.domain.position import Position


def legal_move_targets(state: GameState, frm: Position) -> list[Position]:
    """King-move neighbours of ``frm`` that are in bounds and not barriers.

    A cell occupied by the opponent is included (moving onto it is a capture);
    legality of capture is decided by the referee, not here.
    """
    targets = []
    for cell in frm.neighbors8():
        if cell.in_bounds(state.grid_size) and not state.is_barrier(cell):
            targets.append(cell)
    return targets
