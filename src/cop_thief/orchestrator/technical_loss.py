"""Technical-Loss void-and-rerun policy (FR-22, shared rules §4)."""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")


class TechnicalLossError(RuntimeError):
    """Raised when a sub-game suffers a technical failure and must be re-run."""


def run_clean(play_once: Callable[[int], T], max_attempts: int = 10) -> tuple[T, int]:
    """Run ``play_once(attempt)`` until it succeeds without a Technical Loss.

    Returns the clean result and the number of voided (technical-loss) attempts.
    """
    voided = 0
    for attempt in range(1, max_attempts + 1):
        try:
            return play_once(attempt), voided
        except TechnicalLossError:
            voided += 1
    raise TechnicalLossError(f"could not obtain a clean run in {max_attempts} attempts")
