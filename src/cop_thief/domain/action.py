"""Structured action: the authoritative half of a turn (PLAN §5, ADR-003)."""

from __future__ import annotations

from dataclasses import dataclass

from cop_thief.constants import ActionType
from cop_thief.domain.position import Position


@dataclass(frozen=True)
class Action:
    """A committed action: a move to a cell, or (Cop only) a barrier placement."""

    type: ActionType
    to: Position

    def as_dict(self) -> dict:
        """Serialize to the wire shape ``{"type": ..., "to": [row, col]}``."""
        return {"type": self.type.value, "to": self.to.as_list()}

    @classmethod
    def from_dict(cls, data: dict) -> Action:
        """Build from a wire ``{"type", "to"}`` mapping."""
        return cls(type=ActionType(data["type"]), to=Position.from_list(data["to"]))

    @classmethod
    def move(cls, to: Position) -> Action:
        """Convenience constructor for a move action."""
        return cls(type=ActionType.MOVE, to=to)

    @classmethod
    def barrier(cls, to: Position) -> Action:
        """Convenience constructor for a barrier action."""
        return cls(type=ActionType.BARRIER, to=to)
