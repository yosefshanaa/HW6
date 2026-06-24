"""Bounded minimax search over the *real* Cop & Thief rules (strong + legal).

The search drives the move for the competitive agents: the Cop maximizes (capture
fast, herd with barriers), the Thief minimizes (maximize survival time). Every
action it can return is legal by construction — moves are in-bounds, non-barrier
king steps and the only barrier offered is the Cop walling its own cell within
budget — so the search can never forfeit a sub-game with an illegal action.

It mirrors the engine exactly (``engine.rules`` / ``engine.referee``): thief moves
first, either player landing on the other's cell is a Cop win (a Thief stepping
onto the Cop loses), a barrier consumes the Cop's turn, and the Thief wins once it
has made ``max_moves`` moves and survived the Cop's reply. Search is only used
when the opponent is visible (perfect local info); under fog the caller falls back
to the belief-based heuristic.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from cop_thief.agents.strategy.base import on_edge
from cop_thief.constants import ActionType
from cop_thief.domain.action import Action
from cop_thief.domain.observation import Observation
from cop_thief.domain.position import Position
from cop_thief.domain.roles import PlayerRole

_WIN = 10_000
_INF = 1 << 30

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
        acts.append(Action.barrier(sim.cop))  # wall own cell (always legal here)
    return acts


def _apply(sim: _Sim, act: Action) -> tuple[_Sim, str | None]:
    """Advance one ply. Returns (next_sim, terminal) with terminal in {cop,thief,None}."""
    if act.type is ActionType.BARRIER:
        nxt = replace(
            sim, barriers=sim.barriers | {sim.cop}, placed=sim.placed + 1, turn=PlayerRole.THIEF
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


def _search(sim: _Sim, depth: int, alpha: int, beta: int) -> int:
    """Alpha-beta value of a non-terminal node (Cop maximizes, Thief minimizes)."""
    if depth == 0:
        return _evaluate(sim)
    acts = _legal(sim)
    if not acts:  # boxed in -> the side to move loses
        return -(_WIN + depth) if sim.turn is PlayerRole.COP else (_WIN + depth)
    maximizing = sim.turn is PlayerRole.COP
    best = -_INF if maximizing else _INF
    for a in _ordered(sim, acts):
        nxt, terminal = _apply(sim, a)
        if terminal == "cop":
            v = _WIN + depth
        elif terminal == "thief":
            v = -(_WIN + depth)
        else:
            v = _search(nxt, depth - 1, alpha, beta)
        if maximizing:
            if v > best:
                best = v
            alpha = max(alpha, best)
        else:
            if v < best:
                best = v
            beta = min(beta, best)
        if alpha >= beta:
            break
    return best


def _root(sim: _Sim, depth: int) -> Action | None:
    """Pick the best legal action for the side to move (None if boxed in)."""
    acts = _ordered(sim, _legal(sim))
    if not acts:
        return None
    maximizing = sim.turn is PlayerRole.COP
    best_v = -_INF if maximizing else _INF
    best_a = acts[0]
    alpha, beta = -_INF, _INF
    for a in acts:
        nxt, terminal = _apply(sim, a)
        if terminal == "cop":
            v = _WIN + depth
        elif terminal == "thief":
            v = -(_WIN + depth)
        else:
            v = _search(nxt, depth - 1, alpha, beta)
        if maximizing and v > best_v or not maximizing and v < best_v:
            best_v, best_a = v, a
        if maximizing:
            alpha = max(alpha, best_v)
        else:
            beta = min(beta, best_v)
    return best_a


def search_action(
    role: PlayerRole,
    obs: Observation,
    memory: dict,
    *,
    max_moves: int,
    max_barriers: int,
    depth: int,
) -> Action | None:
    """Best legal action for ``role`` via minimax; None when the opponent is unseen.

    Barriers known to the search are the visible ones plus any the Cop has placed
    (tracked in ``memory['placed_barriers']``), so the Cop searches with full
    knowledge of its own walls even after they leave its vision.
    """
    opp = obs.visible_opponent
    if opp is None:
        return None
    own = obs.own_cell
    barriers = frozenset(set(obs.visible_barriers) | set(memory.get("placed_barriers", [])))
    sim = _Sim(
        cop=own if role is PlayerRole.COP else opp,
        thief=own if role is PlayerRole.THIEF else opp,
        barriers=barriers,
        thief_moves=int(obs.move_number),
        placed=int(memory.get("barriers_placed", 0)),
        turn=role,
        grid=(obs.grid_size[0], obs.grid_size[1]),
        max_moves=int(max_moves),
        max_barriers=int(max_barriers),
    )
    return _root(sim, max(1, int(depth)))
