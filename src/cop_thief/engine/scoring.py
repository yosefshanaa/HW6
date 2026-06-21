"""Sub-game scoring (PRD §8, config-driven)."""

from __future__ import annotations

from cop_thief.domain.roles import PlayerRole


def score_sub_game(scoring: dict[str, int], winner: PlayerRole) -> tuple[int, int]:
    """Return ``(cop_score, thief_score)`` for a sub-game ``winner``.

    Cop win → Cop ``cop_win`` / Thief ``thief_loss``.
    Thief win → Cop ``cop_loss`` / Thief ``thief_win``.
    """
    if winner is PlayerRole.COP:
        return int(scoring["cop_win"]), int(scoring["thief_loss"])
    return int(scoring["cop_loss"]), int(scoring["thief_win"])
