"""Baseline heuristic Cop/Thief strategies (PRD_agent_strategy §2.2)."""

from __future__ import annotations

from cop_thief.agents.strategy.base import Strategy, grid_center, legal_neighbor_cells
from cop_thief.constants import ActionType
from cop_thief.domain.action import Action
from cop_thief.domain.observation import Observation
from cop_thief.domain.position import Position
from cop_thief.domain.roles import PlayerRole


def _reference(obs: Observation, memory: dict) -> Position | None:
    """Best estimate of the opponent: visible cell, else last-known from memory."""
    if obs.visible_opponent is not None:
        return obs.visible_opponent
    return memory.get("last_known_opponent")


def _on_edge(pos: Position, grid_size: list[int]) -> bool:
    """Whether ``pos`` sits on a board edge (row/col is first or last)."""
    return pos.row in (0, grid_size[0] - 1) or pos.col in (0, grid_size[1] - 1)


def _mobility(cell: Position, obs: Observation) -> int:
    """Count of legal king-moves out of ``cell`` (open space = more escape routes)."""
    blocked = set(obs.visible_barriers)
    return sum(
        1 for n in cell.neighbors8() if n.in_bounds(obs.grid_size) and n not in blocked
    )


def _nearest_barrier_dist(cell: Position, obs: Observation) -> int:
    """Chebyshev distance to the closest visible barrier (board span when none seen)."""
    if not obs.visible_barriers:
        return obs.grid_size[0] + obs.grid_size[1]
    return min(cell.chebyshev(b) for b in obs.visible_barriers)


class HeuristicCop(Strategy):
    """Pursuit with tactical barriers: capture > wall (herd) > close distance."""

    def __init__(self) -> None:
        super().__init__(PlayerRole.COP)

    def decide(self, obs: Observation, memory: dict) -> Action:
        cells = legal_neighbor_cells(obs)
        thief = obs.visible_opponent
        if thief is not None and obs.own_cell.is_king_step_to(thief):
            return Action.move(thief)  # capture wins — never give it up
        if self._should_barrier(obs, memory, cells, thief):
            memory["barriers_placed"] = memory.get("barriers_placed", 0) + 1
            return Action.barrier(obs.own_cell)
        if not cells:
            return Action.move(obs.own_cell)
        return Action.move(self._select(obs, cells, memory))

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
        a distance-2 Thief, so it places no barriers and plays pure pursuit — a
        balanced ~67% Cop. Barriers are thus a visibility-gated tool, not an
        always-on win button (see docs/EXPERIMENTS.md).
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

    def _select(self, obs: Observation, cells: list[Position], memory: dict) -> Position:
        target = _reference(obs, memory) or grid_center(obs.grid_size)
        return min(cells, key=lambda c: (c.chebyshev(target), c.row, c.col))

    def compose_message(self, obs: Observation, action: Action, memory: dict) -> str:
        if action.type is ActionType.BARRIER:
            return f"Cop walls off {action.to.as_list()} to corner the thief."
        return f"Cop closing in toward {action.to.as_list()}."


class HeuristicThief(Strategy):
    """Mobility-aware evasion: stay uncapturable, then keep open space and dodge walls.

    The old "maximise distance" rule fled straight into corners and self-trapped —
    that, not the barriers, is what let the Cop win nearly every game. Instead the
    Thief first keeps a safe gap (≥2 from the Cop, so it cannot be captured next turn),
    then prefers cells with the most escape routes, the greatest clearance from
    barriers, the greatest raw distance, and finally the most central spot — a sound,
    deterministic evasion. At radius 2 (the agreed bonus-match value) the Cop can
    track and barrier-herd it to a near-certain capture; at the radius-1 local
    default the fog lets it break contact and escape ~1/3 of sub-games (see
    docs/EXPERIMENTS.md).
    """

    def __init__(self) -> None:
        super().__init__(PlayerRole.THIEF)

    def _select(self, obs: Observation, cells: list[Position], memory: dict) -> Position:
        ref = _reference(obs, memory)
        center = grid_center(obs.grid_size)
        if ref is None:
            # Blind: head for open space near the centre to keep escape routes open.
            return max(cells, key=lambda c: (_mobility(c, obs), -c.chebyshev(center), c.row, c.col))
        return max(
            cells,
            key=lambda c: (
                min(c.chebyshev(ref), 2),
                _mobility(c, obs),
                _nearest_barrier_dist(c, obs),
                c.chebyshev(ref),
                -c.chebyshev(center),
                c.row,
                c.col,
            ),
        )

    def compose_message(self, obs: Observation, action: Action, memory: dict) -> str:
        # Bluff: name a plausible but different corner to mislead the Cop.
        decoy = Position(0, 0) if action.to.row > 0 else Position(obs.grid_size[0] - 1, 0)
        return f"Thief slipping toward {decoy.as_list()}."


def make_strategy(role: PlayerRole, name: str = "heuristic") -> Strategy:
    """Factory for a strategy by role and name."""
    if name != "heuristic":
        raise ValueError(f"unknown strategy: {name}")
    return HeuristicCop() if role is PlayerRole.COP else HeuristicThief()
