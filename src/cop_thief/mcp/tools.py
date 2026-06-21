"""Pure MCP tool implementations (PLAN §9, role-parameterized, no transport).

These functions are wrapped by the FastMCP servers and are directly testable
without a network. They validate inbound payloads and reject (never crash) on
malformed input.
"""

from __future__ import annotations

from typing import Any

import jsonschema

from cop_thief.domain.action import Action
from cop_thief.domain.roles import PlayerRole
from cop_thief.engine.referee import Referee
from cop_thief.mcp.contracts import TURN_PAYLOAD_SCHEMA
from cop_thief.shared.version import __version__


def health_check() -> dict[str, Any]:
    """Liveness + version probe."""
    return {"ok": True, "version": __version__}


def get_observation(referee: Referee, role: str) -> dict[str, Any]:
    """Return the legal partial view for ``role`` (never leaks hidden entities)."""
    return referee.observe(PlayerRole(role)).as_dict()


def validate_action(referee: Referee, role: str, action: dict[str, Any]) -> dict[str, Any]:
    """Pre-check an action without committing it."""
    valid, reason = referee.validate(PlayerRole(role), Action.from_dict(action))
    return {"valid": valid, "reason": reason}


def submit_turn(referee: Referee, payload: dict[str, Any]) -> dict[str, Any]:
    """Validate the envelope, then commit the action to the referee."""
    try:
        jsonschema.validate(instance=payload, schema=TURN_PAYLOAD_SCHEMA)
    except jsonschema.ValidationError as exc:
        return {"accepted": False, "reason": f"malformed payload: {exc.message}",
                "capture": False, "terminal": False, "status": _status(referee)}
    result = referee.apply(PlayerRole(payload["role"]), Action.from_dict(payload["action"]))
    return {
        "accepted": result.accepted,
        "reason": result.reason,
        "capture": result.capture,
        "terminal": result.terminal,
        "status": result.status.value,
    }


def receive_message(inbox: list[dict[str, str]], from_role: str, message: str) -> dict[str, Any]:
    """Deliver an opponent's natural-language message into an inbox."""
    inbox.append({"from": from_role, "message": message})
    return {"ack": True, "count": len(inbox)}


def get_match_status(referee: Referee) -> dict[str, Any]:
    """Current sub-game status for the orchestrator / GUI."""
    state = referee.state
    return {
        "status": state.status.value,
        "thief_moves": state.thief_moves,
        "turn": state.turn.value,
        "cop": state.cop.as_list(),
        "thief": state.thief.as_list(),
    }


def _status(referee: Referee) -> str:
    return referee.state.status.value if referee.state else "ongoing"
