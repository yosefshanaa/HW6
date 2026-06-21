"""Player roles (PLAN §5)."""

from __future__ import annotations

from enum import Enum


class PlayerRole(str, Enum):
    """The two agents. Thief moves first each round."""

    COP = "cop"
    THIEF = "thief"

    @property
    def opponent(self) -> PlayerRole:
        """The other role."""
        return PlayerRole.THIEF if self is PlayerRole.COP else PlayerRole.COP
