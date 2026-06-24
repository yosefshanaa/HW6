"""Hybrid LLM strategy: the model drives, the heuristic guards (PRD_agent_strategy).

One LLM call per turn yields both the move and a (bluff-capable) message. A
legal-guard clamps the move to a legal cell; if the model errors, returns
unparseable output, or proposes an illegal move, the wrapped heuristic supplies
a guaranteed-legal move so the game never stalls. The model's message is kept
even when the move falls back, so the natural-language channel stays live.
"""

from __future__ import annotations

import json
from typing import Any

from cop_thief.agents.llm_client import LlmClient
from cop_thief.agents.strategy.base import Strategy, legal_neighbor_cells
from cop_thief.agents.strategy.llm_prompts import build_user_prompt, system_prompt
from cop_thief.domain.action import Action
from cop_thief.domain.observation import Observation
from cop_thief.domain.position import Position
from cop_thief.domain.roles import PlayerRole
from cop_thief.shared.logging_setup import get_logger

_log = get_logger("llm_strategy")


def _extract_json(raw: str) -> dict[str, Any] | None:
    """Best-effort parse of the first JSON object in ``raw`` (tolerant of prose)."""
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        start, end = raw.find("{"), raw.rfind("}")
        if start == -1 or end <= start:
            return None
        try:
            return json.loads(raw[start : end + 1])
        except json.JSONDecodeError:
            return None


def _to_pos(value: Any) -> Position | None:
    """Coerce ``[row, col]`` (list/tuple of two ints) into a Position, else None."""
    if isinstance(value, (list, tuple)) and len(value) == 2:
        try:
            return Position(int(value[0]), int(value[1]))
        except (TypeError, ValueError):
            return None
    return None


class LlmStrategy(Strategy):
    """Wraps an :class:`LlmClient`; falls back to ``fallback`` on any failure."""

    def __init__(self, role: PlayerRole, client: LlmClient, *, fallback: Strategy) -> None:
        super().__init__(role)
        self._client = client
        self._fallback = fallback
        self._system = system_prompt(role)

    def decide(self, obs: Observation, memory: dict) -> Action:
        """Ask the model; clamp to a legal action, else use the heuristic guard."""
        cells = legal_neighbor_cells(obs)
        action: Action | None = None
        say: str | None = None
        try:
            raw = self._client.complete(
                build_user_prompt(self.role, obs, memory), system=self._system
            )
            action, say = self._parse(raw, obs, cells, memory)
        except Exception as exc:  # noqa: BLE001 - any failure must not stall the turn
            _log.warning("LLM turn failed (%s); using heuristic guard", exc)
        if action is None:
            action = self._fallback.decide(obs, memory)
            if say is None:
                say = self._fallback.compose_message(obs, action, memory)
        memory["_llm_say"] = say
        return action

    def _parse(
        self, raw: str, obs: Observation, cells: list[Position], memory: dict
    ) -> tuple[Action | None, str | None]:
        """Turn the model's JSON into a legal action; None move -> heuristic guard."""
        data = _extract_json(raw)
        if data is None:
            return None, None
        say = (str(data.get("say") or "")).strip() or None
        if self.role is PlayerRole.COP and data.get("barrier"):
            left = memory.get("max_barriers", 5) - memory.get("barriers_placed", 0)
            if left > 0 and obs.own_cell not in obs.visible_barriers:
                memory["barriers_placed"] = memory.get("barriers_placed", 0) + 1
                return Action.barrier(obs.own_cell), say
        target = _to_pos(data.get("move"))
        if target is not None and target in cells:
            return Action.move(target), say
        return None, say  # illegal/garbage move: keep the message, guard the move

    def _select(self, obs: Observation, cells: list[Position], memory: dict) -> Position:
        """ABC hook (unused on the LLM path); defer to the heuristic guard."""
        return self._fallback._select(obs, cells, memory)

    def compose_message(self, obs: Observation, action: Action, memory: dict) -> str:
        """Return the message the model produced in :meth:`decide` (may bluff)."""
        say = memory.pop("_llm_say", None)
        return say or self._fallback.compose_message(obs, action, memory)
