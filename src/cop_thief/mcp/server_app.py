"""Shared FastMCP app builder for the Cop/Thief servers (PLAN §8).

``fastmcp`` is an optional dependency (``uv sync --extra mcp``); it is imported
lazily so the core package installs and tests run without it.
"""

from __future__ import annotations

import random
from typing import Any

from cop_thief.engine.observation_service import random_start
from cop_thief.engine.referee import Referee
from cop_thief.mcp import tools


def build_app(role: str, config) -> Any:
    """Build a FastMCP app exposing the six tools for ``role``."""
    from fastmcp import FastMCP  # lazy: optional dependency

    referee = Referee.from_config(config)
    cop, thief = random_start(referee.grid_size, referee.vision_radius, random.Random(config.get("seed")))
    referee.reset(cop, thief)
    inbox: list[dict[str, str]] = []
    app = FastMCP(f"cop-thief-{role}")

    @app.tool
    def health_check() -> dict:
        """Liveness + version probe."""
        return tools.health_check()

    @app.tool
    def get_observation() -> dict:
        """Return this agent's legal partial view."""
        return tools.get_observation(referee, role)

    @app.tool
    def validate_action(action: dict) -> dict:
        """Pre-check an action without committing."""
        return tools.validate_action(referee, role, action)

    @app.tool
    def submit_turn(payload: dict) -> dict:
        """Validate the envelope and commit the action."""
        return tools.submit_turn(referee, payload)

    @app.tool
    def receive_message(from_role: str, message: str) -> dict:
        """Deliver an opponent's natural-language message."""
        return tools.receive_message(inbox, from_role, message)

    @app.tool
    def get_match_status() -> dict:
        """Current sub-game status."""
        return tools.get_match_status(referee)

    return app
