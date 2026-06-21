"""GUI text renderer tests (PRD_gui_and_logs)."""

from __future__ import annotations

from cop_thief.gui.app import render_board, render_fog


def test_render_board_places_markers():
    board = render_board(
        {"cop": [0, 0], "thief": [4, 4], "barriers": [[2, 2]]}, [5, 5]
    )
    lines = board.splitlines()
    assert lines[0].startswith("C")
    assert lines[4].endswith("T")
    assert lines[2].split()[2] == "#"


def test_render_fog_hides_outside_radius_and_shows_self():
    obs = {
        "role": "cop",
        "own_cell": [0, 0],
        "vision_radius": 1,
        "grid_size": [5, 5],
        "visible_opponent": None,
        "visible_barriers": [],
    }
    fog = render_fog(obs, [5, 5])
    lines = fog.splitlines()
    assert lines[0][0] == "C"            # own cell
    assert lines[4].split()[4] == "?"    # far corner is unknown
    # cell within radius but empty is "."
    assert lines[1].split()[1] == "."


def test_render_fog_shows_visible_opponent_and_barrier():
    obs = {
        "role": "thief",
        "own_cell": [2, 2],
        "vision_radius": 2,
        "grid_size": [5, 5],
        "visible_opponent": [2, 3],
        "visible_barriers": [[3, 3]],
    }
    fog = render_fog(obs, [5, 5]).splitlines()
    assert fog[2].split()[2] == "T"   # self
    assert fog[2].split()[3] == "C"   # visible opponent
    assert fog[3].split()[3] == "#"   # visible barrier
