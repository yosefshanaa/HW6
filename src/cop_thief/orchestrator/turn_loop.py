"""One turn: observe → decide → (validate/fallback) → commit → log (PLAN §10)."""

from __future__ import annotations

from datetime import datetime, timezone

from cop_thief.agents.strategy.base import Strategy
from cop_thief.domain.action import Action
from cop_thief.domain.records import TurnRecord
from cop_thief.domain.roles import PlayerRole
from cop_thief.engine.referee import Referee, TurnResult
from cop_thief.shared.replay import ReplayStore


def play_turn(
    referee: Referee,
    role: PlayerRole,
    strategy: Strategy,
    memory: dict,
    peer_memory: dict,
    sub_game: int,
    store: ReplayStore,
) -> TurnResult:
    """Play one turn for ``role`` and append a :class:`TurnRecord`."""
    obs = referee.observe(role)
    if obs.visible_opponent is not None:
        memory["last_known_opponent"] = obs.visible_opponent

    action = strategy.decide(obs, memory)
    message = strategy.compose_message(obs, action, memory)
    valid, reason = referee.validate(role, action)
    if not valid:
        action, reason = safe_fallback(referee, role, action, reason)

    result = referee.apply(role, action)
    peer_memory.setdefault("received_messages", []).append(message)
    store.append(
        TurnRecord(
            timestamp=datetime.now(timezone.utc).isoformat(),
            sub_game=sub_game,
            move_number=obs.move_number,
            role=role,
            message=message,
            action=action.as_dict(),
            observation=obs.as_dict(),
            validation={"accepted": result.accepted, "reason": result.reason or reason,
                        "capture": result.capture},
            resulting_state=referee.state.snapshot(),
        )
    )
    return result


def safe_fallback(
    referee: Referee, role: PlayerRole, action: Action, reason: str
) -> tuple[Action, str]:
    """Replace an illegal action with a guaranteed-legal move when possible."""
    legal = referee.legal_moves(role)
    if legal:
        return Action.move(legal[0]), f"fallback after invalid ({reason})"
    return action, reason
