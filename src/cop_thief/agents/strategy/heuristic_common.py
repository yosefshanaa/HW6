"""Shared belief/anti-oscillation helpers for the heuristic Cop & Thief.

Kept in one place so the Cop and Thief strategies (split across
``heuristic_cop`` / ``heuristic_thief``) reuse the exact same belief logic
without duplication (guidelines §4.2). Re-exported for the public names the
rest of the codebase imports via :mod:`cop_thief.agents.strategy.heuristic`.
"""

from __future__ import annotations

import re

from cop_thief.agents.strategy.base import mobility, on_edge
from cop_thief.domain.observation import Observation
from cop_thief.domain.position import Position

# Re-exported under the historical private names used throughout the strategies.
_mobility = mobility
_on_edge = on_edge

_COORD_RE = re.compile(r"\[(\d+),\s*(\d+)\]")


def _reference(obs: Observation, memory: dict) -> Position | None:
    """Best estimate of the opponent: visible cell, else last-known from memory."""
    if obs.visible_opponent is not None:
        return obs.visible_opponent
    return memory.get("last_known_opponent")


def _nearest_barrier_dist(cell: Position, obs: Observation) -> int:
    """Chebyshev distance to the closest visible barrier (board span when none seen)."""
    if not obs.visible_barriers:
        return obs.grid_size[0] + obs.grid_size[1]
    return min(cell.chebyshev(b) for b in obs.visible_barriers)


def _message_hint(memory: dict) -> Position | None:
    """A coarse, *untrusted* belief of the opponent's cell, parsed from its last
    natural-language message. The Thief uses it only as a last resort under fog
    (no sighting, no remembered position); a real observation always overrides it,
    so a bluff can mislead at most when the Thief is otherwise totally blind.
    """
    msgs = memory.get("received_messages")
    if not msgs:
        return None
    m = _COORD_RE.search(msgs[-1])
    return Position(int(m.group(1)), int(m.group(2))) if m else None


def _track(obs: Observation, memory: dict) -> Position | None:
    """Record this agent's path; return the cell it stood on last move-turn.

    Used to avoid immediate two-cell oscillation (the ``c != prev`` tie-break),
    the loop that previously let a blind Cop bounce on one pair forever.
    """
    prev = memory.get("here")
    memory["here"] = obs.own_cell
    return prev
