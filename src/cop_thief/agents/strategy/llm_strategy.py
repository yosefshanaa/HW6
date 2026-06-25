"""Hybrid LLM strategy: the model drives, a search-backed guard keeps it strong.

One LLM call per turn yields both the move and a (bluff-capable) message. The
guard then does a light, one-ply search via the wrapped heuristic so the move is
*strong*, not merely legal:

* Cop — a capture that is available this turn is always taken (the model can
  never miss it); a herding barrier is placed only when the heuristic's gate
  agrees; otherwise the model's cell is kept when it is distance-optimal and
  replaced with the closest legal cell when it is not.
* Thief — the model's cell is kept when it is a best evasion (uncapturable next
  turn, most escape routes); a cell the Cop could capture next turn is vetoed in
  favour of a safe one whenever a safe one exists.

If the model errors, returns unparseable output, or omits a move, the heuristic
supplies the move. The model's message is always kept (even when its move is
overridden) so the natural-language / bluff channel stays live.
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
        """Ask the model, then return a strong, legal action via the search guard."""
        cells = legal_neighbor_cells(obs)
        move: Position | None = None
        barrier = False
        say: str | None = None
        try:
            raw = self._client.complete(
                build_user_prompt(self.role, obs, memory), system=self._system
            )
            move, barrier, say = self._parse(raw)
        except Exception as exc:  # noqa: BLE001 - any failure must not stall the turn
            _log.warning("LLM turn failed (%s); using heuristic guard", exc)
        action = self._guard(move, barrier, obs, cells, memory)
        if say is None:
            say = self._fallback.compose_message(obs, action, memory)
        memory["_llm_say"] = say
        return action

    def _parse(self, raw: str) -> tuple[Position | None, bool, str | None]:
        """Pull the proposed move, barrier flag, and message out of the model's JSON."""
        data = _extract_json(raw)
        if data is None:
            return None, False, None
        say = (str(data.get("say") or "")).strip() or None
        barrier = self.role is PlayerRole.COP and bool(data.get("barrier"))
        return _to_pos(data.get("move")), barrier, say

    def _guard(
        self,
        move: Position | None,
        barrier: bool,
        obs: Observation,
        cells: list[Position],
        memory: dict,
    ) -> Action:
        """Light one-ply search: keep the model's move when strong, else override."""
        f = self._fallback
        if not cells:
            return Action.move(obs.own_cell)  # boxed in; referee replaces it
        if self.role is PlayerRole.COP:
            capture = f.capture_move(obs)
            if capture is not None:
                return Action.move(capture)  # never miss a capture
            if barrier and f.wants_barrier(obs, memory, cells, obs.visible_opponent):
                bcell = f.barrier_cell(obs)
                if bcell is not None:
                    memory["barriers_placed"] = memory.get("barriers_placed", 0) + 1
                    return Action.barrier(bcell)
        best = f.best_move(obs, cells, memory)  # also advances anti-oscillation memory
        if move is not None and move in cells and f.accepts_move(move, obs, cells, memory):
            return Action.move(move)  # model's pick is already a best move — keep it
        return Action.move(best)

    def _select(self, obs: Observation, cells: list[Position], memory: dict) -> Position:
        """ABC hook (unused on the LLM path); defer to the heuristic guard."""
        return self._fallback._select(obs, cells, memory)

    def compose_message(self, obs: Observation, action: Action, memory: dict) -> str:
        """Return the message the model produced in :meth:`decide` (may bluff)."""
        say = memory.pop("_llm_say", None)
        return say or self._fallback.compose_message(obs, action, memory)
