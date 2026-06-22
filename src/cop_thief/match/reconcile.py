"""Mirror-and-flag reconciliation (shared spec §2.1, PRD_bonus_match T3/T6).

The non-referee team runs its own engine in parallel; after every committed
turn the two engines' snapshots must agree. Any divergence is *flagged* (not
silently swallowed) so the teams reconcile it together.
"""

from __future__ import annotations

from typing import Any

# Snapshot fields both engines must agree on after each committed turn.
_FIELDS = ("cop", "thief", "barriers", "thief_moves", "turn", "status")


def diff_state(auth: dict[str, Any], mirror: dict[str, Any]) -> list[str]:
    """Return human-readable discrepancies between two engine snapshots.

    An empty list means the authoritative and mirror engines agree.
    """
    flags: list[str] = []
    for field in _FIELDS:
        a, m = auth.get(field), mirror.get(field)
        if a != m:
            flags.append(f"{field}: auth={a} != mirror={m}")
    return flags
