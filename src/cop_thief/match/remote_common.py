"""Shared helpers for the two networked match drivers (RemoteMatch / RemoteSide).

Both drivers run the same 6-sub-game protocol over MCP/HTTP; this module holds the
logic they share verbatim — strategy construction, seeded starts, the role split,
the legality guard, scoring, totals, and the per-turn agent core — so neither file
duplicates it (guidelines §4.2) and both stay under the 150-line gate (§3.2).
"""

from __future__ import annotations

import random

from cop_thief.agents.strategy.base import legal_neighbor_cells
from cop_thief.agents.strategy.heuristic import make_strategy
from cop_thief.constants import ActionType, GameStatus
from cop_thief.domain.action import Action
from cop_thief.domain.observation import Observation
from cop_thief.domain.records import SubGameResult
from cop_thief.domain.roles import PlayerRole
from cop_thief.engine.observation_service import random_start
from cop_thief.engine.scoring import score_sub_game

# A mid-sub-game failure of one of these is a Technical Loss (void + rerun), not a crash.
NETWORK_ERRORS: tuple[type[BaseException], ...] = (ConnectionError, TimeoutError, OSError)
try:  # httpx ships with the mcp extra; widen the net when present
    import httpx

    NETWORK_ERRORS = (*NETWORK_ERRORS, httpx.HTTPError)
except ImportError:  # pragma: no cover
    pass


def build_strategies(config) -> dict[PlayerRole, object]:
    """Cop + Thief strategies from config (same construction in both drivers)."""
    return {
        PlayerRole.COP: make_strategy(
            PlayerRole.COP, config.get("agents.cop_strategy", "heuristic"), config=config
        ),
        PlayerRole.THIEF: make_strategy(
            PlayerRole.THIEF, config.get("agents.thief_strategy", "heuristic"), config=config
        ),
    }


def start_positions(grid_size, vision_radius: int, seed, index: int):
    """Seeded per-(seed, index) start cells — both teams derive the identical pair."""
    rng = random.Random(f"{seed}:{index}")
    return random_start(grid_size, vision_radius, rng)


def role_groups(group_1: str, group_2: str, half: int, index: int) -> tuple[str, str]:
    """(cop_group, thief_group) for ``index`` per the fixed role split."""
    return (group_1, group_2) if index <= half else (group_2, group_1)


def guard_legal(action: Action, obs: Observation) -> Action:
    """Last-ditch legality guard so a turn can never forfeit on an illegal move."""
    if action.type is ActionType.BARRIER:
        return action
    cells = legal_neighbor_cells(obs)
    return action if (action.to in cells or not cells) else Action.move(cells[0])


def result_for(scoring, index: int, status: dict) -> SubGameResult:
    """Score one finished sub-game into a SubGameResult."""
    winner = PlayerRole.COP if status["status"] == GameStatus.COP_WIN.value else PlayerRole.THIEF
    cop_score, thief_score = score_sub_game(scoring, winner)
    return SubGameResult(index, winner, status["thief_moves"], cop_score, thief_score)


def totals_for(results, group_1: str, group_2: str, half: int) -> dict[str, int]:
    """Aggregate per-sub-game role scores into team totals."""
    totals = {group_1: 0, group_2: 0}
    for r in results:
        cop_group, thief_group = role_groups(group_1, group_2, half, r.index)
        totals[cop_group] += r.cop_score
        totals[thief_group] += r.thief_score
    return totals


def run_agent_turn(strategy, role: PlayerRole, *, auth, mirror, index: int, mem: dict):
    """Shared per-turn core: read bluff, observe, decide+guard, compose, dual-submit, deliver.

    ``auth`` is the authoritative Cop-side referee client, ``mirror`` the Thief-side
    mirror; our own view is the Cop server as Cop and the Thief server as Thief, and
    the opponent's inbox is the other one. Returns ``(obs, action, message, res)``;
    the caller does its own logging/reconciliation.
    """
    our_view = auth if role is PlayerRole.COP else mirror
    opp_view = mirror if role is PlayerRole.COP else auth
    inbox = our_view.messages()
    mem["received_messages"] = [
        m["message"] for m in inbox if m.get("from") == role.opponent.value
    ]
    obs = Observation.from_dict(our_view.observe())
    if obs.visible_opponent is not None:
        mem["last_known_opponent"] = obs.visible_opponent
    action = guard_legal(strategy.decide(obs, mem), obs)
    message = strategy.compose_message(obs, action, mem)
    envelope = {
        "sub_game": index, "move_number": obs.move_number, "role": role.value,
        "message": message, "action": action.as_dict(),
    }
    res = auth.submit(envelope)        # authoritative commit
    mirror.submit(envelope)            # mirror commit (kept in sync)
    opp_view.transport.call("receive_message", from_role=role.value, message=message)
    return obs, action, message, res
