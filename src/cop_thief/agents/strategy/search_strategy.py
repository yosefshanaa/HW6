"""Search-driven strategy: minimax picks the move, optional LLM writes the bluff.

The strongest, match-ready agent. The MOVE comes from a bounded minimax over the
real rules (``search``) whenever the opponent is visible, and from the belief-based
heuristic under fog — both are legal by construction, so the agent can never
forfeit with an illegal action. The natural-language MESSAGE comes from an injected
``messenger`` (an LLM bluff) when present, falling back to the heuristic bluff on
any error, so a flaky model can never affect the move or stall the turn.
"""

from __future__ import annotations

from collections.abc import Callable

from cop_thief.agents.strategy.base import Strategy
from cop_thief.agents.strategy.search import search_action
from cop_thief.constants import ActionType
from cop_thief.domain.action import Action
from cop_thief.domain.observation import Observation
from cop_thief.domain.position import Position
from cop_thief.domain.roles import PlayerRole
from cop_thief.shared.logging_setup import get_logger

_log = get_logger("search_strategy")

Messenger = Callable[[Observation, Action, dict], str]


class SearchStrategy(Strategy):
    """Minimax move + heuristic fog fallback; bluff via ``messenger`` or heuristic."""

    def __init__(
        self,
        role: PlayerRole,
        *,
        config,
        fallback: Strategy,
        messenger: Messenger | None = None,
    ) -> None:
        super().__init__(role)
        self._fallback = fallback
        self._messenger = messenger
        self._depth = int(config.get("search.depth", 6))
        self._max_moves = int(config.get("max_moves"))
        self._max_barriers = int(config.get("max_barriers"))

    def decide(self, obs: Observation, memory: dict) -> Action:
        """Search the move when the opponent is visible, else use the heuristic."""
        action: Action | None = None
        if obs.visible_opponent is not None:
            action = search_action(
                self.role, obs, memory,
                max_moves=self._max_moves, max_barriers=self._max_barriers, depth=self._depth,
            )
            if action is not None and action.type is ActionType.BARRIER:
                memory["barriers_placed"] = memory.get("barriers_placed", 0) + 1
        if action is None:
            action = self._fallback.decide(obs, memory)  # fog / boxed: belief heuristic
        if action.type is ActionType.BARRIER:
            memory.setdefault("placed_barriers", []).append(action.to)
        return action

    def _select(self, obs: Observation, cells: list[Position], memory: dict) -> Position:
        """ABC hook (unused on the search path); defer to the heuristic."""
        return self._fallback._select(obs, cells, memory)

    def compose_message(self, obs: Observation, action: Action, memory: dict) -> str:
        """An LLM bluff when a messenger is wired, else the heuristic's bluff."""
        if self._messenger is not None:
            try:
                say = self._messenger(obs, action, memory)
                if say:
                    return say
            except Exception as exc:  # noqa: BLE001 - bluff must never break the turn
                _log.warning("LLM bluff failed (%s); using heuristic message", exc)
        return self._fallback.compose_message(obs, action, memory)
