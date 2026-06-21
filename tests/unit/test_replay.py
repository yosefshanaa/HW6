"""Replay store tests (PRD_gui_and_logs §5)."""

from __future__ import annotations

from cop_thief.domain.records import TurnRecord
from cop_thief.domain.roles import PlayerRole
from cop_thief.shared.replay import ReplayStore


def make_record(n: int) -> TurnRecord:
    return TurnRecord(
        timestamp="2026-06-21T00:00:00+00:00",
        sub_game=1,
        move_number=n,
        role=PlayerRole.THIEF,
        message="heading north",
        action={"type": "move", "to": [n, n]},
        observation={"own_cell": [n, n]},
        validation={"accepted": True, "reason": "", "capture": False},
        resulting_state={"thief_moves": n},
    )


def test_append_and_load_roundtrip(tmp_path):
    store = ReplayStore(tmp_path / "series" / "sub_game_1.jsonl")
    store.append(make_record(1))
    store.append(make_record(2))
    loaded = store.load()
    assert len(loaded) == 2
    assert loaded[0]["role"] == "thief"
    assert loaded[1]["move_number"] == 2


def test_load_missing_file_is_empty(tmp_path):
    assert ReplayStore(tmp_path / "nope.jsonl").load() == []
