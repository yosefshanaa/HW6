"""Audit + result records (PLAN §5, §16)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from cop_thief.domain.roles import PlayerRole


@dataclass(frozen=True)
class TurnRecord:
    """One timestamped turn for logging/replay (PRD §16)."""

    timestamp: str
    sub_game: int
    move_number: int
    role: PlayerRole
    message: str
    action: dict[str, Any]
    observation: dict[str, Any]
    validation: dict[str, Any]
    resulting_state: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-ready mapping."""
        return {
            "timestamp": self.timestamp,
            "sub_game": self.sub_game,
            "move_number": self.move_number,
            "role": self.role.value,
            "message": self.message,
            "action": self.action,
            "observation": self.observation,
            "validation": self.validation,
            "resulting_state": self.resulting_state,
        }


@dataclass
class SubGameResult:
    """Outcome of a single sub-game."""

    index: int
    winner: PlayerRole
    moves_played: int
    cop_score: int
    thief_score: int
    technical_loss: bool = False
    reason: str = ""
    turns: list[TurnRecord] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        """Serialize the per-sub-game record used inside reports."""
        return {
            "index": self.index,
            "winner": self.winner.value,
            "moves_played": self.moves_played,
            "cop_score": self.cop_score,
            "thief_score": self.thief_score,
            "technical_loss": self.technical_loss,
        }
