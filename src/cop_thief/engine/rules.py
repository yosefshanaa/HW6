"""Action legality rules (PRD_game_engine §2)."""

from __future__ import annotations

from cop_thief.constants import ActionType
from cop_thief.domain.action import Action
from cop_thief.domain.game_state import GameState
from cop_thief.domain.roles import PlayerRole


def validate(state: GameState, role: PlayerRole, action: Action) -> tuple[bool, str]:
    """Return ``(is_legal, reason)`` for ``role`` taking ``action``.

    Reason is empty when legal. An illegal action loses the sub-game for
    ``role`` (the referee enforces that consequence).
    """
    if action is None:
        return False, "no action submitted"
    if action.type is ActionType.BARRIER:
        return _validate_barrier(state, role, action)
    return _validate_move(state, role, action)


def _validate_move(state: GameState, role: PlayerRole, action: Action) -> tuple[bool, str]:
    current = state.position_of(role)
    target = action.to
    if not target.in_bounds(state.grid_size):
        return False, "move off-board"
    if not current.is_king_step_to(target):
        return False, "move must be exactly one king step"
    if state.is_barrier(target):
        return False, "move into a barrier"
    return True, ""


def _validate_barrier(state: GameState, role: PlayerRole, action: Action) -> tuple[bool, str]:
    """A barrier goes on an empty cell king-adjacent to the Cop (it stays put).

    Inter-group agreement (lecturer-confirmed): the Cop walls one of its 8 adjacent
    cells, not its own cell. Impassable for both; max 5 per sub-game.
    """
    if role is not PlayerRole.COP:
        return False, "only the Cop may place barriers"
    if state.barriers_placed() >= state.max_barriers:
        return False, "barrier budget exhausted"
    target = action.to
    if not target.in_bounds(state.grid_size):
        return False, "barrier off-board"
    if not state.cop.is_king_step_to(target):
        return False, "barrier must be on a cell adjacent to the Cop"
    if target == state.thief:
        return False, "cannot place a barrier on the Thief's cell"
    if state.is_barrier(target):
        return False, "cell is already a barrier"
    return True, ""
