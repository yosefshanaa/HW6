"""Bounded minimax (alpha-beta) over the *real* Cop & Thief rules (strong + legal).

The search drives the move for the competitive agents: the Cop maximizes (capture
fast, herd with barriers), the Thief minimizes (maximize survival time). Every
action it can return is legal by construction (see :mod:`search_sim`), so the
search can never forfeit a sub-game with an illegal action. Search is only used
when the opponent is visible (perfect local info); under fog the caller falls back
to the belief-based heuristic.

The node model, legal-move generation, ply application, evaluation and ordering
live in :mod:`search_sim`; this module is just the alpha-beta driver and the
public ``search_action`` entry point.
"""

from __future__ import annotations

from cop_thief.agents.strategy.search_sim import (
    _apply,
    _evaluate,
    _legal,
    _ordered,
    _Sim,
)
from cop_thief.domain.action import Action
from cop_thief.domain.observation import Observation
from cop_thief.domain.roles import PlayerRole

__all__ = ["search_action", "_Sim", "_legal"]

_WIN = 10_000
_INF = 1 << 30


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
