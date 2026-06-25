"""Game-node simulation for the minimax search — mirrors the engine rules exactly.

The immutable :class:`_Sim` node plus legal-move generation, ply application,
static evaluation and move ordering. Kept apart from the alpha-beta driver
(:mod:`search`) so each file stays small and single-purpose (guidelines §3.2).
Mirrors ``engine.rules`` / ``engine.referee``: thief moves first, either player
landing on the other's cell is a Cop win (a Thief stepping onto the Cop loses),
a barrier walls an empty cell king-adjacent to the Cop (the Cop stays put) and
consumes its turn, and the Thief wins once it has made ``max_moves`` moves.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from cop_thief.agents.strategy.base import on_edge
from cop_thief.constants import ActionType
from cop_thief.domain.action import Action
from cop_thief.domain.position import Position
from cop_thief.domain.roles import PlayerRole

# Static-eval weights (Cop's perspective; higher = better for the Cop). Distance
# dominates so the Cop closes in; thief mobility and edge-pinning break ties toward
# herding the Thief into a trap.
_W_DIST = 4
_W_MOB = 1
_W_EDGE = 1


@dataclass(frozen=True)
class _Sim:
    """Immutable game node for search (mirrors GameState's relevant fields)."""

    cop: Position
    thief: Position
    barriers: frozenset[Position]
    thief_moves: int
    placed: int
    turn: PlayerRole
    grid: tuple[int, int]
    max_moves: int
    max_barriers: int


def _legal(sim: _Sim) -> list[Action]:
    """All legal actions for the side to move (matches engine.rules exactly)."""
    pos = sim.cop if sim.turn is PlayerRole.COP else sim.thief
    acts = [
        Action.move(n)
        for n in pos.neighbors8()
        if n.in_bounds(sim.grid) and n not in sim.barriers
    ]
    if sim.turn is PlayerRole.COP and sim.placed < sim.max_barriers:
        acts += [
            Action.barrier(n)  # wall an empty cell adjacent to the cop (cop stays put)
            for n in sim.cop.neighbors8()
            if n.in_bounds(sim.grid) and n not in sim.barriers and n != sim.thief
        ]
    return acts


def _apply(sim: _Sim, act: Action) -> tuple[_Sim, str | None]:
    """Advance one ply. Returns (next_sim, terminal) with terminal in {cop,thief,None}."""
    if act.type is ActionType.BARRIER:
        nxt = replace(
            sim, barriers=sim.barriers | {act.to}, placed=sim.placed + 1, turn=PlayerRole.THIEF
        )
        return (nxt, "thief") if sim.thief_moves >= sim.max_moves else (nxt, None)
    if sim.turn is PlayerRole.COP:
        if act.to == sim.thief:
            return replace(sim, cop=act.to), "cop"  # capture
        nxt = replace(sim, cop=act.to, turn=PlayerRole.THIEF)
        return (nxt, "thief") if sim.thief_moves >= sim.max_moves else (nxt, None)
    # Thief move
    if act.to == sim.cop:
        return replace(sim, thief=act.to), "cop"  # thief stepped onto the cop -> loss
    nxt = replace(sim, thief=act.to, thief_moves=sim.thief_moves + 1, turn=PlayerRole.COP)
    return nxt, None


def _thief_mobility(sim: _Sim) -> int:
    return sum(
        1
        for n in sim.thief.neighbors8()
        if n.in_bounds(sim.grid) and n not in sim.barriers
    )


def _evaluate(sim: _Sim) -> int:
    """Static value at the horizon (Cop's perspective; higher = better for Cop)."""
    return (
        -_W_DIST * sim.cop.chebyshev(sim.thief)
        - _W_MOB * _thief_mobility(sim)
        + _W_EDGE * (1 if on_edge(sim.thief, sim.grid) else 0)
    )


def _ordered(sim: _Sim, acts: list[Action]) -> list[Action]:
    """Order moves to make alpha-beta prune hard: best-looking first."""
    if sim.turn is PlayerRole.COP:
        # Captures / distance-reducing first; barrier last (neutral tempo).
        return sorted(
            acts,
            key=lambda a: (a.type is ActionType.BARRIER, a.to.chebyshev(sim.thief)),
        )
    return sorted(acts, key=lambda a: -a.to.chebyshev(sim.cop))  # thief: farthest first
