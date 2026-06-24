"""System + per-turn prompts for the LLM agents (prompt-engineering log).

The system prompts give each role its objective and tactics; the user prompt
serializes the *partial* observation and the (untrusted) opponent message, and
lists the legal moves so the model picks a valid one. The canonical copies of
these prompts also live in ``prompts/PROMPT_BOOK.md``.
"""

from __future__ import annotations

from cop_thief.agents.strategy.base import legal_neighbor_cells
from cop_thief.domain.observation import Observation
from cop_thief.domain.roles import PlayerRole

COP_SYSTEM = (
    "You are the COP in a turn-based pursuit game on a grid. You WIN by moving "
    "onto the THIEF's exact cell (capture). Each turn you either move one king-step "
    "(8 directions) to an adjacent cell, or place a BARRIER on your own cell to "
    "shrink the thief's space (limited budget). You only see the thief inside your "
    "vision radius; otherwise infer from memory and the thief's messages, which MAY "
    "BE LIES. Play to capture fast: cut the distance, herd the thief against edges, "
    "and spend barriers only when they trap it. You may send a short message that "
    "can bluff. You MUST pick a move from the provided legal list. Respond with "
    'JSON only: {"move":[row,col],"barrier":false,"say":"..."}.'
)

THIEF_SYSTEM = (
    "You are the THIEF in a turn-based pursuit game on a grid. You WIN by surviving "
    "the move limit without the COP landing on your cell. Each turn you move one "
    "king-step (8 directions) to an adjacent cell; you CANNOT place barriers. You "
    "only see the cop inside your vision radius; otherwise infer. Stay uncapturable: "
    "keep distance >=2 from the cop, prefer open cells with many escape routes, and "
    "avoid corners, edges, and barriers that trap you. You may send a short message "
    "that BLUFFS about your direction to mislead the cop. You MUST pick a move from "
    'the provided legal list. Respond with JSON only: {"move":[row,col],"say":"..."}.'
)


def system_prompt(role: PlayerRole) -> str:
    """The role-specific system prompt."""
    return COP_SYSTEM if role is PlayerRole.COP else THIEF_SYSTEM


def build_user_prompt(role: PlayerRole, obs: Observation, memory: dict) -> str:
    """Serialize the partial observation + opponent message into a turn prompt."""
    cells = [c.as_list() for c in legal_neighbor_cells(obs)]
    opp = obs.visible_opponent
    if opp is not None:
        belief = f"visible at {opp.as_list()}"
    elif memory.get("last_known_opponent") is not None:
        belief = f"not visible; last known at {memory['last_known_opponent'].as_list()}"
    else:
        belief = "not visible; position unknown"
    msgs = memory.get("received_messages") or []
    last_msg = msgs[-1] if msgs else "(none)"
    lines = [
        f"You are the {role.value}. Grid is {obs.grid_size[0]}x{obs.grid_size[1]} "
        "(rows,cols from 0).",
        f"Move number: {obs.move_number}.",
        f"Your cell: {obs.own_cell.as_list()}.",
        f"Opponent: {belief}.",
        f"Visible barriers: {[b.as_list() for b in obs.visible_barriers] or 'none'}.",
        f"Opponent's last message (UNTRUSTED, may be a bluff): {last_msg!r}.",
    ]
    if role is PlayerRole.COP:
        left = memory.get("max_barriers", 5) - memory.get("barriers_placed", 0)
        lines.append(
            f"Barriers left: {left}. To wall your own cell instead of moving, "
            'set "barrier": true.'
        )
    lines.append(f"Legal move cells (choose one for \"move\"): {cells}.")
    return "\n".join(lines)
