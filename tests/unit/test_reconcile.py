"""Mirror-and-flag reconciliation tests (PRD_bonus_match T3/T6)."""

from __future__ import annotations

from cop_thief.match.reconcile import diff_state


def _snap(**over):
    base = {
        "cop": [0, 0], "thief": [4, 4], "barriers": [],
        "thief_moves": 3, "turn": "thief", "status": "ongoing",
    }
    base.update(over)
    return base


def test_identical_snapshots_agree():
    assert diff_state(_snap(), _snap()) == []


def test_position_divergence_is_flagged():
    flags = diff_state(_snap(thief=[4, 4]), _snap(thief=[4, 3]))
    assert len(flags) == 1
    assert "thief" in flags[0]


def test_multiple_field_divergence_all_flagged():
    flags = diff_state(
        _snap(),
        _snap(thief_moves=4, status="cop_win", barriers=[[1, 1]]),
    )
    assert len(flags) == 3
