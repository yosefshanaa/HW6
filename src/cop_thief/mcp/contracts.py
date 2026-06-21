"""MCP payload schemas (PLAN §9, PRD_mcp_servers §2.2)."""

from __future__ import annotations

ACTION_SCHEMA = {
    "type": "object",
    "required": ["type", "to"],
    "properties": {
        "type": {"enum": ["move", "barrier"]},
        "to": {"type": "array", "items": {"type": "integer"}, "minItems": 2, "maxItems": 2},
    },
}

TURN_PAYLOAD_SCHEMA = {
    "type": "object",
    "required": ["sub_game", "move_number", "role", "action"],
    "properties": {
        "sub_game": {"type": "integer"},
        "move_number": {"type": "integer"},
        "role": {"enum": ["cop", "thief"]},
        "message": {"type": "string"},
        "action": ACTION_SCHEMA,
    },
}

OBSERVATION_SCHEMA = {
    "type": "object",
    "required": ["role", "own_cell", "move_number", "vision_radius", "grid_size"],
    "properties": {
        "role": {"enum": ["cop", "thief"]},
        "own_cell": {"type": "array", "items": {"type": "integer"}},
        "move_number": {"type": "integer"},
        "vision_radius": {"type": "integer"},
        "grid_size": {"type": "array"},
        "visible_opponent": {"type": ["array", "null"]},
        "visible_barriers": {"type": "array"},
    },
}
