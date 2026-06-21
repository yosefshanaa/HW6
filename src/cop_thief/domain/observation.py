"""Per-agent partial observation (PLAN §5, PRD_partial_observability)."""

from __future__ import annotations

from dataclasses import dataclass, field

from cop_thief.domain.position import Position
from cop_thief.domain.roles import PlayerRole


@dataclass(frozen=True)
class Observation:
    """The legal fog-of-war view returned to a single agent.

    ``visible_opponent`` is ``None`` when the opponent is outside the vision
    radius; ``visible_barriers`` only includes within-radius barriers.
    """

    role: PlayerRole
    own_cell: Position
    move_number: int
    vision_radius: int
    grid_size: list[int]
    visible_opponent: Position | None = None
    visible_barriers: list[Position] = field(default_factory=list)

    def as_dict(self) -> dict:
        """Serialize to a wire mapping (never leaks hidden entities)."""
        return {
            "role": self.role.value,
            "own_cell": self.own_cell.as_list(),
            "move_number": self.move_number,
            "vision_radius": self.vision_radius,
            "grid_size": list(self.grid_size),
            "visible_opponent": (
                self.visible_opponent.as_list() if self.visible_opponent else None
            ),
            "visible_barriers": [b.as_list() for b in self.visible_barriers],
        }
