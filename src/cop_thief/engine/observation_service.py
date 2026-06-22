"""Partial observation + start placement (PRD_partial_observability)."""

from __future__ import annotations

import random
from collections.abc import Sequence

from cop_thief.domain.game_state import GameState
from cop_thief.domain.observation import Observation
from cop_thief.domain.position import Position
from cop_thief.domain.roles import PlayerRole


def compute_observation(state: GameState, role: PlayerRole, vision_radius: int) -> Observation:
    """Return the legal fog-of-war view for ``role``.

    Own cell is always known; the opponent and barriers are included only
    within ``vision_radius`` (Chebyshev). Never leaks hidden entities.
    """
    own = state.position_of(role)
    opp = state.position_of(role.opponent)
    visible_opponent = opp if own.chebyshev(opp) <= vision_radius else None
    visible_barriers = [
        b.cell for b in state.barriers if own.chebyshev(b.cell) <= vision_radius
    ]
    return Observation(
        role=role,
        own_cell=own,
        move_number=state.thief_moves,
        vision_radius=vision_radius,
        grid_size=list(state.grid_size),
        visible_opponent=visible_opponent,
        visible_barriers=visible_barriers,
    )


def all_cells(grid_size: Sequence[int]) -> list[Position]:
    """Every cell of the grid."""
    return [Position(r, c) for r in range(grid_size[0]) for c in range(grid_size[1])]


def random_start(
    grid_size: Sequence[int],
    vision_radius: int,
    rng: random.Random,
    max_distance: int | None = None,
) -> tuple[Position, Position]:
    """Pick a Cop/Thief pair that is distinct and outside each other's radius.

    Chosen jointly (not Cop-then-Thief) so a centre cell with no out-of-radius
    partner can never dead-end the placement. ``max_distance`` optionally caps
    the Chebyshev start separation (local balance: avoids pathological
    far-corner starts on a small board); when omitted, behaviour is unchanged.
    """
    cells = all_cells(grid_size)
    pairs = [
        (a, b)
        for a in cells
        for b in cells
        if vision_radius < a.chebyshev(b) and (max_distance is None or a.chebyshev(b) <= max_distance)
    ]
    if not pairs:
        raise ValueError(
            f"no valid start pair for vision_radius={vision_radius}, max_distance={max_distance}"
        )
    return rng.choice(pairs)


def fixed_start(fixed_cfg: dict) -> tuple[Position, Position]:
    """Read fixed Cop/Thief start cells from config."""
    return Position.from_list(fixed_cfg["cop"]), Position.from_list(fixed_cfg["thief"])
