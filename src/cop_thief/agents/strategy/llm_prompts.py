"""System + per-turn prompts for the LLM agents (prompt-engineering log).

The system prompts give each role its objective and a short tactical playbook;
the user prompt serializes the *partial* observation and the (untrusted) opponent
message, and lists the legal moves annotated with the two facts that decide the
game — Chebyshev distance to the opponent and the number of escape routes — so
the model can reason toward a strong cell, not just a legal one. A search-backed
guard (``llm_strategy``) still vets the final move. The canonical copies of these
prompts also live in ``prompts/PROMPT_BOOK.md``.
"""

from __future__ import annotations

from cop_thief.agents.strategy.base import (
    legal_neighbor_cells,
    mobility,
    on_edge,
)
from cop_thief.constants import ActionType
from cop_thief.domain.action import Action
from cop_thief.domain.observation import Observation
from cop_thief.domain.position import Position
from cop_thief.domain.roles import PlayerRole

COP_SYSTEM = (
    "You are the COP in a turn-based pursuit game on a grid. You WIN by moving "
    "onto the THIEF's exact cell (capture). Each turn you either move one king-step "
    "(8 directions, includes diagonals) to an adjacent cell, or place a BARRIER on "
    "your own cell to shrink the thief's space (limited budget). You only see the "
    "thief inside your vision radius; otherwise infer from memory and the thief's "
    "messages, which MAY BE LIES.\n"
    "Tactics: (1) ALWAYS reduce Chebyshev distance to the thief — pick the legal "
    "cell with the smallest 'dist'; move diagonally to cut both row and column at "
    "once. (2) If the thief is one step away, step onto it to capture NOW. (3) Herd "
    "it: drive it toward an edge or corner where it has few escape routes, then "
    "place a barrier to seal a side when the thief is pinned on an edge two cells "
    "away. (4) When blind, head to the thief's last-known cell or the centre to "
    "regain contact; do not oscillate between two cells.\n"
    "You may send a short message that can bluff. You MUST pick \"move\" from the "
    "provided legal list. Respond with JSON only: "
    '{"move":[row,col],"barrier":false,"say":"..."}.'
)

THIEF_SYSTEM = (
    "You are the THIEF in a turn-based pursuit game on a grid. You WIN by surviving "
    "the move limit without the COP landing on your cell. Each turn you move one "
    "king-step (8 directions, includes diagonals) to an adjacent cell; you CANNOT "
    "place barriers. You only see the cop inside your vision radius; otherwise "
    "infer.\n"
    "Tactics: (1) STAY UNCAPTURABLE — never move to a cell with 'dist' 1 from the "
    "cop (it could land on you next turn); keep Chebyshev distance >=2. (2) Among "
    "safe cells, pick the one with the most escape routes ('esc') — open space, not "
    "edges or corners (an 'edge' cell has fewer escapes and can trap you). (3) Break "
    "line of sight and keep the board's centre open behind you; do not flee blindly "
    "into a corner. (4) When blind, stay mobile and avoid retracing your last cell.\n"
    "You may send a short message that BLUFFS about your direction to mislead the "
    "cop (e.g. name a corner you are NOT going to). You MUST pick \"move\" from the "
    'provided legal list. Respond with JSON only: {"move":[row,col],"say":"..."}.'
)


def system_prompt(role: PlayerRole) -> str:
    """The role-specific system prompt."""
    return COP_SYSTEM if role is PlayerRole.COP else THIEF_SYSTEM


def _belief(obs: Observation, memory: dict) -> tuple[str, Position | None]:
    """A human-readable opponent belief plus the cell to measure distances against."""
    if obs.visible_opponent is not None:
        return f"visible at {obs.visible_opponent.as_list()}", obs.visible_opponent
    last = memory.get("last_known_opponent")
    if last is not None:
        return f"not visible; last known at {last.as_list()}", last
    return "not visible; position unknown", None


def _annotate(obs: Observation, ref: Position | None) -> list[str]:
    """Each legal cell tagged with distance-to-opponent, escape routes, edge flag."""
    out = []
    for c in legal_neighbor_cells(obs):
        tag = str(c.as_list())
        if ref is not None:
            tag += f" dist={c.chebyshev(ref)}"
        tag += f" esc={mobility(c, obs)}"
        if on_edge(c, obs.grid_size):
            tag += " edge"
        out.append(tag)
    return out


def build_user_prompt(role: PlayerRole, obs: Observation, memory: dict) -> str:
    """Serialize the partial observation + opponent message into a turn prompt."""
    belief, ref = _belief(obs, memory)
    msgs = memory.get("received_messages") or []
    last_msg = msgs[-1] if msgs else "(none)"
    lines = [
        f"You are the {role.value}. Grid is {obs.grid_size[0]}x{obs.grid_size[1]} "
        "(rows,cols from 0).",
        f"Move number: {obs.move_number}.",
        f"Your cell: {obs.own_cell.as_list()}.",
        f"Opponent: {belief}.",
    ]
    if ref is not None:
        lines.append(f"Chebyshev distance to opponent: {obs.own_cell.chebyshev(ref)}.")
    lines.append(
        f"Visible barriers: {[b.as_list() for b in obs.visible_barriers] or 'none'}."
    )
    lines.append(
        f"Opponent's last message (UNTRUSTED, may be a bluff): {last_msg!r}."
    )
    if role is PlayerRole.COP:
        left = memory.get("max_barriers", 5) - memory.get("barriers_placed", 0)
        lines.append(
            f"Barriers left: {left}. To wall your own cell instead of moving, "
            'set "barrier": true.'
        )
    lines.append(
        "Legal moves (pick one [row,col] for \"move\"; dist=Chebyshev to opponent, "
        f"esc=escape routes, lower dist is closer): {_annotate(obs, ref)}."
    )
    return "\n".join(lines)


def build_message_prompt(
    role: PlayerRole, obs: Observation, action: Action, memory: dict
) -> str:
    """Bluff-only prompt: the move is already decided; ask for a misleading line.

    Used by the search-driven agent — the strong move comes from the search, so the
    model is asked solely for a short in-character message that misdirects the
    opponent about that move (the bluff channel the rules encourage).
    """
    belief, _ = _belief(obs, memory)
    if action.type is ActionType.BARRIER:
        deciding = f"place a barrier on your cell {action.to.as_list()}"
    else:
        deciding = f"move to {action.to.as_list()}"
    return (
        f"You are the {role.value} at {obs.own_cell.as_list()} on a "
        f"{obs.grid_size[0]}x{obs.grid_size[1]} grid. Opponent: {belief}.\n"
        f"You have already decided to {deciding}. Do NOT reveal that.\n"
        "Write ONE short in-character line (<12 words) to send to the opponent that "
        "BLUFFS — name a direction or cell you are NOT actually going to, to mislead "
        'them. Respond JSON only: {"say":"..."}.'
    )
