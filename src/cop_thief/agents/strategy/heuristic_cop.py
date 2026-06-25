"""Baseline heuristic Cop strategy (PRD_agent_strategy §2.2).

Pursuit with tactical barriers: capture > wall (herd) > close distance.
"""

from __future__ import annotations

from cop_thief.agents.strategy.base import (
    Strategy,
    grid_center,
    legal_neighbor_cells,
)
from cop_thief.agents.strategy.heuristic_common import _on_edge, _track
from cop_thief.constants import ActionType
from cop_thief.domain.action import Action
from cop_thief.domain.observation import Observation
from cop_thief.domain.position import Position
from cop_thief.domain.roles import PlayerRole


class HeuristicCop(Strategy):
    """Pursuit with tactical barriers: capture > wall (herd) > close distance."""

    def __init__(self) -> None:
        super().__init__(PlayerRole.COP)

    def decide(self, obs: Observation, memory: dict) -> Action:
        cells = legal_neighbor_cells(obs)
        cap = self.capture_move(obs)
        if cap is not None:
            return Action.move(cap)  # capture wins — never give it up
        if self.wants_barrier(obs, memory, cells, obs.visible_opponent):
            bcell = self.barrier_cell(obs)
            if bcell is not None:
                memory["barriers_placed"] = memory.get("barriers_placed", 0) + 1
                return Action.barrier(bcell)
        if not cells:
            return Action.move(obs.own_cell)
        return Action.move(self.best_move(obs, cells, memory))

    def barrier_cell(self, obs: Observation) -> Position | None:
        """An empty cell king-adjacent to the Cop to wall (closest to the thief), or None.

        Per the inter-group rule the Cop walls an *adjacent* cell (not its own); pick
        the empty neighbour nearest the thief to cut off its space.
        """
        thief = obs.visible_opponent
        blocked = set(obs.visible_barriers)
        cand = [
            n for n in obs.own_cell.neighbors8()
            if n.in_bounds(obs.grid_size) and n not in blocked and n != thief
        ]
        if not cand:
            return None
        if thief is not None:
            return min(cand, key=lambda c: (c.chebyshev(thief), c.row, c.col))
        return min(cand, key=lambda c: (c.row, c.col))

    def capture_move(self, obs: Observation) -> Position | None:
        """The thief's cell when it is visible and one king-step away, else None.

        The single most important move: a Cop that can capture this turn always
        must. The LLM guard calls this to *force* a capture the model might miss.
        """
        thief = obs.visible_opponent
        if thief is not None and obs.own_cell.is_king_step_to(thief):
            return thief
        return None

    def pursuit_ref(self, obs: Observation, memory: dict) -> Position:
        """Cell the Cop is closing on: the thief if seen, else last-known, else centre."""
        return (
            obs.visible_opponent
            or memory.get("last_known_opponent")
            or grid_center(obs.grid_size)
        )

    def accepts_move(
        self, target: Position, obs: Observation, cells: list[Position], memory: dict
    ) -> bool:
        """Whether ``target`` is distance-optimal (a strong pursuit move, not just legal).

        The LLM guard keeps the model's chosen cell when it ties the closest legal
        cell to the pursuit reference, and overrides it otherwise — so the model
        never throws away a tempo by stepping the wrong way.
        """
        ref = self.pursuit_ref(obs, memory)
        best_d = min(c.chebyshev(ref) for c in cells)
        return target.chebyshev(ref) == best_d

    def wants_barrier(
        self, obs: Observation, memory: dict, cells: list[Position], thief: Position | None
    ) -> bool:
        """Public name for the herding-barrier gate (see :meth:`_should_barrier`)."""
        return self._should_barrier(obs, memory, cells, thief)

    def _should_barrier(
        self, obs: Observation, memory: dict, cells: list[Position], thief: Position | None
    ) -> bool:
        """Wall the Cop's own cell only on a genuine, opportunistic herding chance.

        Deterministic guards: budget left; not already standing on a barrier; Thief
        *currently visible* and exactly two cells away (so no capture is sacrificed
        and we never wall a stale phantom); Thief pinned on a board edge (walling
        shrinks its space); and ≥3 safe exits so the wall can never self-trap.

        The two-cell trigger only fires when the Thief is *visible at distance 2*.
        At radius 2 that is the common case and herding is **decisive** (barrier
        ablation: 0%→100% Cop). At the radius-1 local default the Cop can never see
        a distance-2 Thief, so it places no barriers and plays pure pursuit/search —
        a genuine contest (~54% Cop with distance-3 starts). Barriers are thus a
        visibility-gated tool, not an always-on win button (see docs/EXPERIMENTS.md).
        """
        if thief is None:
            return False
        if memory.get("barriers_placed", 0) >= memory.get("max_barriers", 5):
            return False
        if obs.own_cell in obs.visible_barriers:
            return False
        if obs.own_cell.chebyshev(thief) != 2:
            return False
        if not _on_edge(thief, obs.grid_size):
            return False
        return len(cells) >= 3

    def best_move(self, obs: Observation, cells: list[Position], memory: dict) -> Position:
        """The Cop's strongest legal step (also updates anti-oscillation tracking)."""
        prev = _track(obs, memory)
        if obs.visible_opponent is not None:
            # Fresh sighting: pursue exactly as before (unchanged pursuit strength).
            return min(cells, key=lambda c: (c.chebyshev(obs.visible_opponent), c.row, c.col))
        # Blind, or only a *stale* memory of the Thief: head toward that last-known
        # cell (else the centre) but avoid cells just occupied, so the Cop covers
        # ground instead of bouncing on one pair forever — the loop that let the
        # Thief "win" by repetition while the Cop oscillated near the centre.
        target = memory.get("last_known_opponent") or grid_center(obs.grid_size)
        recent = memory.setdefault("recent", [])
        pick = min(cells, key=lambda c: (c in recent, c == prev, c.chebyshev(target), c.row, c.col))
        recent.append(obs.own_cell)
        del recent[:-4]
        return pick

    def _select(self, obs: Observation, cells: list[Position], memory: dict) -> Position:
        return self.best_move(obs, cells, memory)

    def compose_message(self, obs: Observation, action: Action, memory: dict) -> str:
        if action.type is ActionType.BARRIER:
            return f"Cop walls off {action.to.as_list()} to corner the thief."
        return f"Cop closing in toward {action.to.as_list()}."
