"""Baseline heuristic Thief strategy (PRD_agent_strategy §2.2).

Mobility-aware evasion: stay uncapturable, then keep open space and dodge walls.
"""

from __future__ import annotations

from cop_thief.agents.strategy.base import Strategy, grid_center
from cop_thief.agents.strategy.heuristic_common import (
    _message_hint,
    _mobility,
    _nearest_barrier_dist,
    _reference,
    _track,
)
from cop_thief.domain.action import Action
from cop_thief.domain.observation import Observation
from cop_thief.domain.position import Position
from cop_thief.domain.roles import PlayerRole


class HeuristicThief(Strategy):
    """Mobility-aware evasion: stay uncapturable, then keep open space and dodge walls.

    The old "maximise distance" rule fled straight into corners and self-trapped —
    that, not the barriers, is what let the Cop win nearly every game. Instead the
    Thief first keeps a safe gap (≥2 from the Cop, so it cannot be captured next turn),
    then prefers cells with the most escape routes, the greatest clearance from
    barriers, the greatest raw distance, and finally the most central spot — a sound,
    deterministic evasion. Under fog it evades from its remembered last position, or
    failing that from a coarse, *untrusted* belief parsed from the Cop's last message
    (a live sighting always overrides it); with no information at all it stays mobile
    and avoids backtracking rather than marching into the centre (which used to walk it
    into the Cop). At radius 2 the Cop can track and barrier-herd it to a near-certain
    capture; at the radius-1 local default the fog lets it break contact and win
    ~46% of sub-games (see docs/EXPERIMENTS.md).
    """

    def __init__(self) -> None:
        super().__init__(PlayerRole.THIEF)

    def evasion_ref(self, obs: Observation, memory: dict) -> Position | None:
        """The cop the Thief is dodging: sighting > last-known > untrusted message hint."""
        return _reference(obs, memory) or _message_hint(memory)

    def accepts_move(
        self, target: Position, obs: Observation, cells: list[Position], memory: dict
    ) -> bool:
        """Whether ``target`` is a strong evasion (safe first, then open and clear).

        ``min(chebyshev, 2)`` makes *staying uncapturable* (gap >=2, so the Cop
        cannot land on the Thief next turn) the top tie-break: when any safe cell
        exists, a cell the Cop could capture next turn is never accepted. The LLM
        guard uses this to veto the model walking into the Cop, then prefers the
        most escape routes and clearance from barriers — keeping the model's own
        pick whenever it is already among the best.
        """
        ref = self.evasion_ref(obs, memory)
        if ref is None:
            return _mobility(target, obs) == max(_mobility(c, obs) for c in cells)
        # Match the meaningful components of best_move's key (all but the arbitrary
        # row/col tie-break): safety, escape routes, barrier clearance, raw distance,
        # and centrality — so the guard overrides edge/corner-hugging the model favours
        # even when it ties on safety+mobility, keeping the Thief at heuristic strength.
        center = grid_center(obs.grid_size)

        def key(c: Position) -> tuple[int, int, int, int, int]:
            return (
                min(c.chebyshev(ref), 2),
                _mobility(c, obs),
                _nearest_barrier_dist(c, obs),
                c.chebyshev(ref),
                -c.chebyshev(center),
            )

        return key(target) == max(key(c) for c in cells)

    def best_move(self, obs: Observation, cells: list[Position], memory: dict) -> Position:
        """The Thief's strongest legal step (also updates anti-oscillation tracking)."""
        prev = _track(obs, memory)
        # Belief priority: live sighting > remembered last position > a coarse,
        # untrusted hint parsed from the Cop's last message (fog fallback only).
        ref = self.evasion_ref(obs, memory)
        center = grid_center(obs.grid_size)
        if ref is None:
            # Truly blind (no sighting, memory, or message): keep escape routes
            # open and don't backtrack; no march to the dead centre (that walked
            # the Thief straight into a central Cop).
            return max(cells, key=lambda c: (c != prev, _mobility(c, obs), c.row, c.col))
        # Seeing / last-known: original mobility-aware evasion (unchanged so the
        # documented radius-2 behaviour is preserved).
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

    def _select(self, obs: Observation, cells: list[Position], memory: dict) -> Position:
        return self.best_move(obs, cells, memory)

    def compose_message(self, obs: Observation, action: Action, memory: dict) -> str:
        # Bluff: name a plausible but different corner to mislead the Cop.
        decoy = Position(0, 0) if action.to.row > 0 else Position(obs.grid_size[0] - 1, 0)
        return f"Thief slipping toward {decoy.as_list()}."
