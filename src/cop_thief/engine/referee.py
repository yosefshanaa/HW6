"""Referee: the single authoritative state machine (PLAN §6-7)."""

from __future__ import annotations

from dataclasses import dataclass

from cop_thief.constants import ActionType, GameStatus
from cop_thief.domain.action import Action
from cop_thief.domain.barrier import Barrier
from cop_thief.domain.game_state import GameState
from cop_thief.domain.observation import Observation
from cop_thief.domain.position import Position
from cop_thief.domain.roles import PlayerRole
from cop_thief.engine import rules
from cop_thief.engine.movement import legal_move_targets
from cop_thief.engine.observation_service import compute_observation


@dataclass(frozen=True)
class TurnResult:
    """Outcome of submitting one action."""

    accepted: bool
    reason: str
    capture: bool
    terminal: bool
    status: GameStatus


class Referee:
    """Owns one sub-game's state; the only writer of game state."""

    def __init__(
        self,
        grid_size: list[int],
        max_moves: int,
        max_barriers: int,
        scoring: dict[str, int],
        vision_radius: int,
    ) -> None:
        self.grid_size = list(grid_size)
        self.max_moves = int(max_moves)
        self.max_barriers = int(max_barriers)
        self.scoring = dict(scoring)
        self.vision_radius = int(vision_radius)
        self.state: GameState | None = None

    @classmethod
    def from_config(cls, config) -> Referee:
        """Build a referee from a :class:`Config`."""
        return cls(
            grid_size=config.get("grid_size"),
            max_moves=config.get("max_moves"),
            max_barriers=config.get("max_barriers"),
            scoring=config.get("scoring"),
            vision_radius=config.get("vision_radius"),
        )

    def reset(self, cop: Position, thief: Position) -> GameState:
        """Start a fresh sub-game with the given start positions."""
        if cop == thief:
            raise ValueError("Cop and Thief cannot start on the same cell")
        self.state = GameState(
            grid_size=self.grid_size,
            cop=cop,
            thief=thief,
            max_moves=self.max_moves,
            max_barriers=self.max_barriers,
        )
        return self.state

    def observe(self, role: PlayerRole) -> Observation:
        """Return the legal partial view for ``role``."""
        return compute_observation(self._require_state(), role, self.vision_radius)

    def validate(self, role: PlayerRole, action: Action) -> tuple[bool, str]:
        """Check legality without committing."""
        return rules.validate(self._require_state(), role, action)

    def legal_moves(self, role: PlayerRole) -> list[Position]:
        """In-bounds, non-barrier king-move targets for ``role`` (full state)."""
        state = self._require_state()
        return legal_move_targets(state, state.position_of(role))

    def apply(self, role: PlayerRole, action: Action) -> TurnResult:
        """Validate and commit ``action`` for ``role``; advance the game."""
        state = self._require_state()
        if state.status is not GameStatus.ONGOING:
            return TurnResult(False, "sub-game already over", False, True, state.status)
        if role is not state.turn:
            return TurnResult(False, "not this role's turn", False, False, state.status)
        valid, reason = rules.validate(state, role, action)
        if not valid:
            return self._lose(role, reason)
        return self._commit(state, role, action)

    def _commit(self, state: GameState, role: PlayerRole, action: Action) -> TurnResult:
        if action.type is ActionType.BARRIER:
            state.barriers.append(Barrier(action.to, role, state.thief_moves))
        else:
            state.set_position(role, action.to)
            if state.cop == state.thief:
                state.status = GameStatus.COP_WIN
                return TurnResult(True, "", True, True, GameStatus.COP_WIN)
        return self._advance(state, role)

    def _advance(self, state: GameState, role: PlayerRole) -> TurnResult:
        if role is PlayerRole.THIEF:
            state.thief_moves += 1
            state.turn = PlayerRole.COP
            return TurnResult(True, "", False, False, GameStatus.ONGOING)
        if state.thief_moves >= state.max_moves:
            state.status = GameStatus.THIEF_WIN
            return TurnResult(True, "", False, True, GameStatus.THIEF_WIN)
        state.turn = PlayerRole.THIEF
        return TurnResult(True, "", False, False, GameStatus.ONGOING)

    def _lose(self, role: PlayerRole, reason: str) -> TurnResult:
        state = self._require_state()
        winner = role.opponent
        state.status = GameStatus.COP_WIN if winner is PlayerRole.COP else GameStatus.THIEF_WIN
        return TurnResult(False, reason, False, True, state.status)

    def _require_state(self) -> GameState:
        if self.state is None:
            raise RuntimeError("Referee has no active sub-game; call reset() first")
        return self.state
