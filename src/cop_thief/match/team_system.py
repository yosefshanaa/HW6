"""One team's independent system (PRD_bonus_match §2).

A :class:`TeamSystem` is a self-contained peer: it fields a strategy for
whichever role it plays in a sub-game and owns its own :class:`Referee`
instance — authoritative when it is the cop side, a mirror when it is the
thief side. Two of these, wired by :class:`LocalMatch`, stand in for the two
friendly teams during the loopback dry-run.
"""

from __future__ import annotations

from cop_thief.agents.strategy.base import Strategy
from cop_thief.agents.strategy.heuristic import make_strategy
from cop_thief.domain.roles import PlayerRole
from cop_thief.engine.referee import Referee


class TeamSystem:
    """A named peer with a strategy per role and its own engine."""

    def __init__(self, name: str, config) -> None:
        self.name = name
        self.config = config
        self._strategies: dict[PlayerRole, Strategy] = {
            PlayerRole.COP: make_strategy(
                PlayerRole.COP, config.get("agents.cop_strategy", "heuristic"), config=config
            ),
            PlayerRole.THIEF: make_strategy(
                PlayerRole.THIEF, config.get("agents.thief_strategy", "heuristic"), config=config
            ),
        }
        self.memory: dict[PlayerRole, dict] = {PlayerRole.COP: {}, PlayerRole.THIEF: {}}

    def new_referee(self, vision_radius: int | None = None) -> Referee:
        """A fresh engine instance owned by this team for one sub-game.

        ``vision_radius`` overrides the config default (the bonus match runs at
        the agreed radius even when the local series default is lower).
        """
        referee = Referee.from_config(self.config)
        if vision_radius is not None:
            referee.vision_radius = int(vision_radius)
        return referee

    def strategy_for(self, role: PlayerRole) -> Strategy:
        """The strategy this team uses when playing ``role``."""
        return self._strategies[role]

    def start_role(self, role: PlayerRole, max_barriers: int) -> dict:
        """Reset and return fresh per-sub-game memory for ``role``."""
        seed = {"max_barriers": max_barriers} if role is PlayerRole.COP else {}
        self.memory[role] = seed
        return self.memory[role]
