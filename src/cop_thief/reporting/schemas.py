"""JSON schemas for the report shapes (assignment §9.1 / §9.2)."""

from __future__ import annotations

SUB_GAME_SCHEMA = {
    "type": "object",
    "required": ["index", "winner", "moves_played", "cop_score", "thief_score"],
    "properties": {
        "index": {"type": "integer"},
        "winner": {"enum": ["cop", "thief"]},
        "moves_played": {"type": "integer"},
        "cop_score": {"type": "integer"},
        "thief_score": {"type": "integer"},
        "technical_loss": {"type": "boolean"},
    },
}

INTERNAL_SCHEMA = {
    "type": "object",
    "required": [
        "group_name", "students", "github_repo", "cop_mcp_url",
        "thief_mcp_url", "timezone", "sub_games", "totals",
    ],
    "properties": {
        "group_name": {"type": "string"},
        "students": {"type": "array"},
        "github_repo": {"type": "string"},
        "cop_mcp_url": {"type": "string"},
        "thief_mcp_url": {"type": "string"},
        "timezone": {"type": "string"},
        "sub_games": {"type": "array", "items": SUB_GAME_SCHEMA},
        "totals": {
            "type": "object",
            "required": ["cop", "thief"],
            "properties": {"cop": {"type": "integer"}, "thief": {"type": "integer"}},
        },
    },
}

BONUS_SCHEMA = {
    "type": "object",
    "required": [
        "report_type", "groups", "github_repo_group_1", "github_repo_group_2",
        "mcp_url_group_1_cop", "mcp_url_group_1_thief", "mcp_url_group_2_cop",
        "mcp_url_group_2_thief", "timezone", "students_group_1",
        "students_group_2", "sub_games", "totals_by_group", "bonus_claim",
        "mutual_agreement",
    ],
    "properties": {
        "report_type": {"const": "bonus_game"},
        "groups": {"type": "object"},
        "timezone": {"type": "string"},
        "sub_games": {"type": "array"},
        "totals_by_group": {"type": "object"},
        "bonus_claim": {"type": "object"},
        "mutual_agreement": {"type": "boolean"},
    },
}
